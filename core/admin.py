from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

from .models import (
    ActivityLog,
    Consultation,
    DrugShortageAlert,
    DrugStock,
    EmergencyAlarm,
    Facility,
    FacilityService,
    Invoice,
    LabResult,
    OutbreakAlert,
    Prescription,
    Profile,
    Referral,
    Reminder,
    StockDelivery,
    StockDispenseLog,
    SymptomEntry,
    Visit,
    Vitals,
    Drone,
    DroneDelivery,
)


# ── FACILITY ──────────────────────────────────────────────────────────────────

class FacilityServiceInline(admin.TabularInline):
    model = FacilityService
    extra = 2


@admin.register(Facility)
class FacilityAdmin(admin.ModelAdmin):
    list_display  = ['name', 'level', 'sub_county', 'county', 'phone', 'drug_status', 'is_active']
    list_filter   = ['level', 'county', 'is_active', 'drug_status']
    search_fields = ['name', 'sub_county', 'county']
    list_editable = ['is_active', 'drug_status']
    inlines       = [FacilityServiceInline]
    fieldsets = (
        ('Basic info', {
            'fields': ('name', 'level', 'sub_county', 'county', 'address', 'is_active')
        }),
        ('Contact', {
            'fields': ('phone', 'emergency_contact', 'email', 'operating_hours')
        }),
        ('Location', {
            'fields': ('latitude', 'longitude')
        }),
        ('Stock status', {
            'fields': ('drug_status',)
        }),
    )


# ── USER + PROFILE ────────────────────────────────────────────────────────────

class ProfileInline(admin.StackedInline):
    model               = Profile
    can_delete          = False
    verbose_name_plural = 'Profile'
    extra               = 1  # Allow creating profile for new users
    fieldsets = (
        (None, {
            'fields': (
                'role', 'facility', 'phone_number', 'firebase_token',
                'date_of_birth', 'gender', 'id_number',
            )
        }),
        ('Medical background', {
            'fields': (
                'blood_group', 'known_allergies',
                'chronic_conditions', 'current_medications',
            ),
            'classes': ('collapse',)
        }),
        ('Payment', {
            'fields': ('payment_mode',),
        }),
    )


class UserAdmin(BaseUserAdmin):
    inlines      = [ProfileInline]
    list_display = [
        'username', 'first_name', 'last_name',
        'get_role', 'get_facility', 'is_active',
    ]
    list_filter  = ['is_active', 'profile__role', 'profile__facility']

    def get_role(self, obj):
        return obj.profile.role if hasattr(obj, 'profile') else '—'
    get_role.short_description = 'Role'

    def get_facility(self, obj):
        if hasattr(obj, 'profile') and obj.profile.facility:
            return obj.profile.facility.name
        return '—'
    get_facility.short_description = 'Facility'
    
    def save_model(self, request, obj, form, change):
        """
        Save the User and ensure the Profile is created if it doesn't exist.
        """
        super().save_model(request, obj, form, change)
        # Ensure a profile exists for this user
        Profile.objects.get_or_create(user=obj)


# Unregister the default User admin, register ours which includes the Profile inline
admin.site.unregister(User)
admin.site.register(User, UserAdmin)


# ── VISIT ─────────────────────────────────────────────────────────────────────

class SymptomEntryInline(admin.StackedInline):
    model      = SymptomEntry
    extra      = 0
    can_delete = False
    fields     = ['body_part', 'severity', 'symptoms', 'duration_value', 'duration_unit', 'known_allergies']


class VitalsInline(admin.StackedInline):
    model      = Vitals
    extra      = 0
    can_delete = False
    fields     = ['blood_pressure', 'temperature', 'pulse', 'oxygen_saturation', 'weight', 'priority', 'nurse_notes']


class ConsultationInline(admin.StackedInline):
    model      = Consultation
    extra      = 0
    can_delete = False
    fields     = ['doctor', 'clinical_findings', 'diagnosis', 'treatment_plan', 'followup_date']


class PrescriptionInline(admin.TabularInline):
    model           = Prescription
    extra           = 0
    fields          = ['drug_name', 'dosage', 'frequency', 'duration', 'dispensed', 'dispensed_at']
    readonly_fields = ['dispensed_at']


class LabResultInline(admin.TabularInline):
    model  = LabResult
    extra  = 0
    fields = ['test_name', 'urgency', 'status', 'result_value', 'unit', 'normal_range']


@admin.register(Visit)
class VisitAdmin(admin.ModelAdmin):
    list_display   = ['id', 'patient', 'facility', 'date', 'visit_type', 'status', 'check_in_time']
    list_filter    = ['status', 'visit_type', 'facility', 'date', 'payment_mode']
    search_fields  = ['patient__first_name', 'patient__last_name', 'facility__name']
    date_hierarchy = 'date'
    raw_id_fields  = ['patient', 'doctor']
    inlines        = [
        SymptomEntryInline,
        VitalsInline,
        ConsultationInline,
        PrescriptionInline,
        LabResultInline,
    ]
    fieldsets = (
        ('Visit', {
            'fields': ('patient', 'facility', 'doctor', 'date', 'status')
        }),
        ('Details', {
            'fields': (
                'visit_type', 'payment_mode',
                'check_in_time', 'check_out_time',
                'presenting_complaint', 'reception_notes',
            )
        }),
    )


# ── SYMPTOM ENTRY ─────────────────────────────────────────────────────────────

@admin.register(SymptomEntry)
class SymptomEntryAdmin(admin.ModelAdmin):
    list_display   = ['patient', 'body_part', 'severity', 'visit_date', 'facility', 'created_at']
    list_filter    = ['severity', 'facility', 'visit_date']
    search_fields  = ['patient__first_name', 'patient__last_name']
    date_hierarchy = 'visit_date'


# ── VITALS ────────────────────────────────────────────────────────────────────

@admin.register(Vitals)
class VitalsAdmin(admin.ModelAdmin):
    list_display  = ['visit', 'blood_pressure', 'temperature', 'pulse', 'priority', 'recorded_by', 'recorded_at']
    list_filter   = ['priority', 'recorded_at']
    search_fields = ['visit__patient__first_name', 'visit__patient__last_name']


# ── CONSULTATION ──────────────────────────────────────────────────────────────

@admin.register(Consultation)
class ConsultationAdmin(admin.ModelAdmin):
    list_display   = ['visit', 'doctor', 'diagnosis', 'created_at']
    list_filter    = ['doctor', 'created_at']
    search_fields  = ['diagnosis', 'visit__patient__first_name', 'visit__patient__last_name']
    date_hierarchy = 'created_at'


@admin.register(OutbreakAlert)
class OutbreakAlertAdmin(admin.ModelAdmin):
    list_display   = ['diagnosis', 'county', 'sub_county', 'case_count', 'facility_count', 'resolved', 'created_at']
    list_filter    = ['resolved', 'county', 'sub_county']
    search_fields  = ['diagnosis', 'county', 'sub_county']
    date_hierarchy = 'created_at'


@admin.register(Drone)
class DroneAdmin(admin.ModelAdmin):
    list_display   = ['name', 'identifier', 'facility', 'status', 'last_updated']
    list_filter    = ['status', 'facility']
    search_fields  = ['name', 'identifier']


@admin.register(DroneDelivery)
class DroneDeliveryAdmin(admin.ModelAdmin):
    list_display   = ['package_type', 'item_name', 'quantity', 'status', 'origin_facility', 'destination_facility', 'requested_by', 'requested_at']
    list_filter    = ['package_type', 'status', 'origin_facility', 'destination_facility']
    search_fields  = ['item_name', 'description', 'origin_facility__name', 'destination_facility__name']
    date_hierarchy = 'requested_at'


@admin.register(DrugShortageAlert)
class DrugShortageAlertAdmin(admin.ModelAdmin):
    list_display   = ['drug_stock', 'facility', 'days_until_runout', 'estimated_daily_consumption', 'severity', 'resolved', 'predicted_at']
    list_filter    = ['severity', 'resolved', 'facility']
    search_fields  = ['drug_stock__drug_name', 'facility__name']
    date_hierarchy = 'predicted_at'


# ── PRESCRIPTION ──────────────────────────────────────────────────────────────

@admin.register(Prescription)
class PrescriptionAdmin(admin.ModelAdmin):
    list_display  = ['drug_name', 'dosage', 'visit', 'dispensed', 'dispensed_at', 'dispensed_by']
    list_filter   = ['dispensed', 'dispensed_at']
    search_fields = ['drug_name', 'visit__patient__first_name', 'visit__patient__last_name']
    list_editable = ['dispensed']


# ── LAB RESULT ────────────────────────────────────────────────────────────────

@admin.register(LabResult)
class LabResultAdmin(admin.ModelAdmin):
    list_display   = ['test_name', 'visit', 'urgency', 'status', 'result_value', 'ordered_by', 'date_ordered']
    list_filter    = ['status', 'urgency', 'date_ordered']
    search_fields  = ['test_name', 'visit__patient__first_name', 'visit__patient__last_name']
    date_hierarchy = 'date_ordered'


# ── DRUG STOCK ────────────────────────────────────────────────────────────────

@admin.register(DrugStock)
class DrugStockAdmin(admin.ModelAdmin):
    list_display  = [
        'drug_name', 'facility', 'quantity_delivered',
        'quantity_dispensed', 'quantity_remaining_display',
        'unit', 'status', 'low_stock_threshold', 'last_updated',
    ]
    list_filter   = ['status', 'facility', 'category']
    search_fields = ['drug_name', 'facility__name']
    list_editable = ['low_stock_threshold']

    def quantity_remaining_display(self, obj):
        return obj.quantity_remaining
    quantity_remaining_display.short_description = 'Remaining'


@admin.register(StockDelivery)
class StockDeliveryAdmin(admin.ModelAdmin):
    list_display   = ['drug_name', 'facility', 'quantity', 'unit', 'supplier', 'date', 'logged_by']
    list_filter    = ['facility', 'date']
    search_fields  = ['drug_name', 'facility__name', 'supplier']
    date_hierarchy = 'date'


@admin.register(StockDispenseLog)
class StockDispenseLogAdmin(admin.ModelAdmin):
    list_display   = ['drug_stock', 'quantity_dispensed', 'date', 'dispensed_by']
    list_filter    = ['date', 'drug_stock__facility']
    date_hierarchy = 'date'


# ── REFERRAL ──────────────────────────────────────────────────────────────────

@admin.register(Referral)
class ReferralAdmin(admin.ModelAdmin):
    list_display   = [
        'id', 'patient', 'from_facility', 'referred_to',
        'urgency', 'status', 'referring_doctor', 'date',
    ]
    list_filter    = ['status', 'urgency', 'from_facility', 'referred_to']
    search_fields  = ['patient__first_name', 'patient__last_name', 'reason']
    date_hierarchy = 'date'
    raw_id_fields  = ['patient', 'referring_doctor']


# ── EMERGENCY ALARM ───────────────────────────────────────────────────────────

@admin.register(EmergencyAlarm)
class EmergencyAlarmAdmin(admin.ModelAdmin):
    list_display   = [
        'id', 'patient', 'facility', 'condition_type',
        'severity', 'response_type', 'resolved', 'created_at',
    ]
    list_filter    = ['severity', 'response_type', 'resolved', 'facility']
    search_fields  = ['patient__first_name', 'patient__last_name', 'condition_type']
    list_editable  = ['resolved']
    date_hierarchy = 'created_at'
    raw_id_fields  = ['patient']


# ── INVOICE ───────────────────────────────────────────────────────────────────

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display   = [
        'id', 'visit', 'consultation_fee', 'lab_fee',
        'pharmacy_fee', 'total_cost_display', 'paid', 'paid_at',
    ]
    list_filter    = ['paid', 'created_at']
    search_fields  = ['visit__patient__first_name', 'visit__patient__last_name']
    list_editable  = ['paid']
    date_hierarchy = 'created_at'

    def total_cost_display(self, obj):
        return f"KES {obj.total_cost:,.2f}"
    total_cost_display.short_description = 'Total'


# ── REMINDER ──────────────────────────────────────────────────────────────────

@admin.register(Reminder)
class ReminderAdmin(admin.ModelAdmin):
    list_display   = ['patient', 'appointment_type', 'facility', 'date', 'time', 'sms_sent']
    list_filter    = ['sms_sent', 'date', 'facility']
    search_fields  = ['patient__first_name', 'patient__last_name', 'appointment_type']
    list_editable  = ['sms_sent']
    date_hierarchy = 'date'


# ── ACTIVITY LOG ──────────────────────────────────────────────────────────────

@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display    = ['timestamp', 'facility', 'user', 'message']
    list_filter     = ['facility', 'timestamp']
    search_fields   = ['message', 'user__first_name']
    date_hierarchy  = 'timestamp'
    readonly_fields = ['timestamp']


# ── ADMIN SITE BRANDING ───────────────────────────────────────────────────────

admin.site.site_header = 'AfyaLink Administration'
admin.site.site_title  = 'AfyaLink Admin'
admin.site.index_title = 'System management'