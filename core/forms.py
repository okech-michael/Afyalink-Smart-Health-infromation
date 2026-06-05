from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import authenticate

from .models import (
    Consultation,
    DroneDelivery,
    EmergencyAlarm,
    Facility,
    LabResult,
    Prescription,
    Profile,
    Referral,
    Reminder,
    SymptomEntry,
    Visit,
    Vitals,
)


# ── ROLE-BASED LOGIN ──────────────────────────────────────────────────────────

class RoleBasedAuthenticationForm(AuthenticationForm):
    """
    Custom authentication form that includes role selection.
    Validates that the selected role matches the user's profile role.
    """
    ROLE_CHOICES = Profile.ROLE_CHOICES
    
    role = forms.ChoiceField(
        choices=ROLE_CHOICES,
        required=True,
        widget=forms.RadioSelect(
            attrs={'class': 'role-radio'}
        ),
        label='Select your role'
    )

    def clean(self):
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')
        selected_role = self.cleaned_data.get('role')

        if username and password:
            # Authenticate the user first
            self.user_cache = authenticate(
                self.request,
                username=username,
                password=password
            )
            if self.user_cache is None:
                raise forms.ValidationError(
                    "Invalid username or password.",
                    code='invalid_login',
                )
            
            # Check if user has a profile
            if not hasattr(self.user_cache, 'profile'):
                Profile.objects.get_or_create(user=self.user_cache)
            if not hasattr(self.user_cache, 'profile'):
                raise forms.ValidationError(
                    "Your account is not properly configured. Please contact support.",
                    code='no_profile',
                )
            
            # Verify the selected role matches the user's actual role
            user_role = self.user_cache.profile.role
            if user_role != selected_role:
                raise forms.ValidationError(
                    f"Your account is configured as {user_role.title()}, not {selected_role.title()}. "
                    f"Please select the correct role.",
                    code='role_mismatch',
                )
        return self.cleaned_data


# ── PATIENT REGISTRATION ──────────────────────────────────────────────────────

class PatientRegistrationForm(UserCreationForm):
    """
    Extends Django's built-in UserCreationForm with patient-specific fields.
    Creates both the User and their Profile in one save.
    """
    first_name    = forms.CharField(max_length=50,  required=True)
    last_name     = forms.CharField(max_length=50,  required=True)
    date_of_birth = forms.DateField(
        required=True,
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    gender        = forms.ChoiceField(
        choices=[('', 'Select'), ('male', 'Male'), ('female', 'Female'), ('other', 'Other')],
        required=True
    )
    phone_number  = forms.CharField(max_length=20, required=True)
    id_number     = forms.CharField(max_length=30, required=False)
    facility      = forms.ModelChoiceField(
        queryset=Facility.objects.filter(is_active=True).order_by('sub_county', 'name'),
        required=True,
        empty_label='-- Select your nearest facility --'
    )

    class Meta:
        model  = User
        fields = [
            'username', 'first_name', 'last_name',
            'password1', 'password2',
        ]

    def save(self, commit=True):
        user            = super().save(commit=False)
        user.first_name = self.cleaned_data['first_name']
        user.last_name  = self.cleaned_data['last_name']
        if commit:
            user.save()
            # Profile is auto-created by signal; just update it
            profile                = user.profile
            profile.role           = 'patient'
            profile.date_of_birth  = self.cleaned_data['date_of_birth']
            profile.gender         = self.cleaned_data['gender']
            profile.phone_number   = self.cleaned_data['phone_number']
            profile.id_number      = self.cleaned_data.get('id_number', '')
            profile.facility       = self.cleaned_data['facility']
            profile.save()
        return user


# ── SYMPTOM ENTRY ─────────────────────────────────────────────────────────────

class SymptomEntryForm(forms.ModelForm):

    BODY_PART_CHOICES = [
        ('', '-- Select --'),
        ('Head and neck', (
            ('head',   'Head'),
            ('eyes',   'Eyes'),
            ('ears',   'Ears'),
            ('nose',   'Nose'),
            ('throat', 'Throat / mouth'),
            ('neck',   'Neck'),
        )),
        ('Chest and abdomen', (
            ('chest',   'Chest'),
            ('heart',   'Heart / palpitations'),
            ('lungs',   'Lungs / breathing'),
            ('abdomen', 'Abdomen / stomach'),
        )),
        ('Lower body', (
            ('back',   'Back'),
            ('pelvis', 'Pelvis / urinary'),
            ('legs',   'Legs / feet'),
            ('arms',   'Arms / hands'),
        )),
        ('General', (
            ('skin',    'Skin / rash'),
            ('general', 'Whole body / general'),
            ('other',   'Other'),
        )),
    ]

    SEVERITY_CHOICES = [
        ('',         '-- Select --'),
        ('mild',     'Mild — manageable, not stopping daily activities'),
        ('moderate', 'Moderate — affecting daily activities'),
        ('severe',   'Severe — very painful or disabling'),
        ('critical', 'Critical — I need urgent help'),
    ]

    DURATION_UNIT_CHOICES = [
        ('hours',  'Hours'),
        ('days',   'Days'),
        ('weeks',  'Weeks'),
        ('months', 'Months'),
    ]

    body_part     = forms.ChoiceField(choices=BODY_PART_CHOICES, required=True)
    severity      = forms.ChoiceField(choices=SEVERITY_CHOICES,  required=True)
    duration_unit = forms.ChoiceField(choices=DURATION_UNIT_CHOICES, required=True)
    facility      = forms.ModelChoiceField(
        queryset=Facility.objects.filter(is_active=True).order_by('name'),
        required=True
    )
    visit_date    = forms.DateField(
        required=True,
        widget=forms.DateInput(attrs={'type': 'date'})
    )

    class Meta:
        model  = SymptomEntry
        fields = [
            'facility', 'visit_date', 'body_part', 'severity',
            'symptoms', 'duration_value', 'duration_unit',
            'temperature', 'current_medications',
            'known_allergies', 'extra_notes',
        ]
        widgets = {
            'symptoms':            forms.Textarea(attrs={'rows': 4}),
            'current_medications': forms.Textarea(attrs={'rows': 2}),
            'extra_notes':         forms.Textarea(attrs={'rows': 2}),
        }


# ── EMERGENCY ALARM ───────────────────────────────────────────────────────────

class EmergencyAlarmForm(forms.ModelForm):

    class Meta:
        model  = EmergencyAlarm
        fields = [
            'facility', 'condition_type', 'severity',
            'description', 'location_description',
            'latitude', 'longitude',
            'patient_count', 'conscious',
            'response_type', 'contact_number',
        ]
        widgets = {
            'description':          forms.Textarea(attrs={'rows': 3}),
            'location_description': forms.TextInput(),
        }


# ── VITALS ────────────────────────────────────────────────────────────────────

class VitalsForm(forms.ModelForm):

    PRIORITY_CHOICES = [
        ('high',   'High — immediate attention needed'),
        ('medium', 'Medium — seen within the hour'),
        ('low',    'Low — routine'),
    ]

    priority = forms.ChoiceField(choices=PRIORITY_CHOICES, required=True)

    class Meta:
        model  = Vitals
        fields = [
            'blood_pressure', 'temperature', 'pulse',
            'oxygen_saturation', 'weight', 'respiratory_rate',
            'blood_sugar', 'pain_score', 'priority', 'nurse_notes',
        ]
        widgets = {
            'nurse_notes': forms.Textarea(attrs={'rows': 3}),
        }


# ── CONSULTATION ──────────────────────────────────────────────────────────────

class ConsultationForm(forms.ModelForm):

    class Meta:
        model  = Consultation
        fields = [
            'clinical_findings', 'diagnosis', 'icd_code',
            'treatment_plan', 'doctor_notes',
            'followup_date', 'followup_notes',
        ]
        widgets = {
            'clinical_findings': forms.Textarea(attrs={'rows': 4}),
            'treatment_plan':    forms.Textarea(attrs={'rows': 3}),
            'doctor_notes':      forms.Textarea(attrs={'rows': 2}),
            'followup_date':     forms.DateInput(attrs={'type': 'date'}),
        }


class DroneDeliveryForm(forms.ModelForm):
    class Meta:
        model = DroneDelivery
        fields = [
            'package_type', 'item_name', 'description', 'quantity', 'unit',
            'blood_group', 'origin_facility', 'destination_facility',
            'destination_address', 'destination_latitude', 'destination_longitude',
            'expected_arrival',
        ]
        widgets = {
            'description':          forms.Textarea(attrs={'rows': 3}),
            'destination_address':  forms.Textarea(attrs={'rows': 2}),
            'expected_arrival':     forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }

    def __init__(self, *args, **kwargs):
        from .models import DroneDelivery
        super().__init__(*args, **kwargs)
        self.Meta.model = DroneDelivery
        self.fields['blood_group'] = forms.ChoiceField(
            choices=[('', '-- Select blood group --')] + Profile.BLOOD_GROUP_CHOICES,
            required=False,
        )
        self.fields['origin_facility'].queryset = Facility.objects.filter(is_active=True).order_by('name')
        self.fields['destination_facility'].queryset = Facility.objects.filter(is_active=True).order_by('name')
        self.fields['destination_latitude'].required = False
        self.fields['destination_longitude'].required = False
        self.fields['destination_address'].required = False
        self.fields['expected_arrival'].required = False

    def clean(self):
        cleaned_data = super().clean()
        package_type = cleaned_data.get('package_type')
        blood_group = cleaned_data.get('blood_group')
        if package_type == 'blood' and not blood_group:
            self.add_error('blood_group', 'Blood group is required for blood deliveries.')
        return cleaned_data


# ── REFERRAL ──────────────────────────────────────────────────────────────────

class ReferralForm(forms.ModelForm):

    URGENCY_CHOICES = [
        ('routine',   'Routine — within a few days'),
        ('urgent',    'Urgent — today'),
        ('emergency', 'Emergency — immediate transfer'),
    ]

    TRANSPORT_CHOICES = [
        ('own',       'Own means'),
        ('ambulance', 'Ambulance'),
        ('facility',  'Facility vehicle'),
    ]

    urgency        = forms.ChoiceField(choices=URGENCY_CHOICES, required=True)
    transport_mode = forms.ChoiceField(choices=TRANSPORT_CHOICES, required=True)

    class Meta:
        model  = Referral
        fields = [
            'referred_to', 'urgency', 'reason',
            'specialist_needed', 'transport_mode',
            'accompanying_staff', 'referring_doctor_notes',
        ]
        widgets = {
            'reason':                forms.Textarea(attrs={'rows': 4}),
            'referring_doctor_notes': forms.Textarea(attrs={'rows': 2}),
        }


# ── VISIT REGISTRATION (reception) ───────────────────────────────────────────

class VisitRegistrationForm(forms.ModelForm):

    VISIT_TYPE_CHOICES = [
        ('outpatient',  'Outpatient'),
        ('emergency',   'Emergency'),
        ('maternity',   'Maternity'),
        ('follow_up',   'Follow-up'),
        ('referral_in', 'Referral — incoming'),
        ('vaccination', 'Vaccination / MCH'),
        ('lab_only',    'Lab only'),
    ]

    PAYMENT_MODE_CHOICES = [
        ('cash',      'Cash'),
        ('nhif',      'NHIF'),
        ('insurance', 'Private insurance'),
        ('free',      'Free / waived'),
    ]

    visit_type   = forms.ChoiceField(choices=VISIT_TYPE_CHOICES,   required=True)
    payment_mode = forms.ChoiceField(choices=PAYMENT_MODE_CHOICES, required=True)

    class Meta:
        model  = Visit
        fields = [
            'visit_type', 'payment_mode',
            'presenting_complaint', 'reception_notes',
        ]
        widgets = {
            'presenting_complaint': forms.TextInput(),
            'reception_notes':      forms.Textarea(attrs={'rows': 2}),
        }


# ── REMINDER ──────────────────────────────────────────────────────────────────

class ReminderForm(forms.ModelForm):

    class Meta:
        model  = Reminder
        fields = ['facility', 'appointment_type', 'date', 'time', 'notes']
        widgets = {
            'date':  forms.DateInput(attrs={'type': 'date'}),
            'time':  forms.TimeInput(attrs={'type': 'time'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }


# ── LAB RESULT ENTRY ─────────────────────────────────────────────────────────

class LabResultForm(forms.ModelForm):

    STATUS_CHOICES = [
        ('normal',   'Normal — within reference range'),
        ('abnormal', 'Abnormal — outside reference range'),
        ('critical', 'Critical — immediate attention needed'),
    ]

    status = forms.ChoiceField(choices=STATUS_CHOICES, required=True)

    class Meta:
        model  = LabResult
        fields = [
            'result_value', 'unit', 'normal_range',
            'lab_notes', 'status',
        ]
        widgets = {
            'lab_notes': forms.Textarea(attrs={'rows': 2}),
        }


# ── STOCK DELIVERY ────────────────────────────────────────────────────────────

class StockDeliveryForm(forms.Form):
    """
    Not a ModelForm — handles the composite logic of creating/updating
    DrugStock and logging a StockDelivery in one go.
    """
    UNIT_CHOICES = [
        ('tablets',  'Tablets'),
        ('capsules', 'Capsules'),
        ('vials',    'Vials'),
        ('ampoules', 'Ampoules'),
        ('bottles',  'Bottles'),
        ('sachets',  'Sachets'),
        ('litres',   'Litres'),
        ('units',    'Units'),
    ]

    CATEGORY_CHOICES = [
        ('',               '— Select category —'),
        ('antibiotic',     'Antibiotic'),
        ('analgesic',      'Analgesic / pain relief'),
        ('antimalarial',   'Antimalarial'),
        ('antifungal',     'Antifungal'),
        ('antiretroviral', 'Antiretroviral (ARV)'),
        ('antihypertensive', 'Antihypertensive'),
        ('antidiabetic',   'Antidiabetic'),
        ('vaccine',        'Vaccine'),
        ('iv_fluid',       'IV fluid'),
        ('supplement',     'Supplement / vitamin'),
        ('other',          'Other'),
    ]

    drug_name            = forms.CharField(max_length=200, required=True)
    category             = forms.ChoiceField(choices=CATEGORY_CHOICES, required=False)
    quantity             = forms.IntegerField(min_value=1, required=True)
    unit                 = forms.ChoiceField(choices=UNIT_CHOICES, required=True)
    supplier             = forms.CharField(max_length=200, required=False)
    delivery_date        = forms.DateField(
        required=True,
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    batch_number         = forms.CharField(max_length=50, required=False)
    expiry_date          = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    low_stock_threshold  = forms.IntegerField(min_value=1, initial=50, required=True)
    delivery_notes       = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 2})
    )