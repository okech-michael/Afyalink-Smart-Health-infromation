import json
import math
from urllib import parse, request

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import (
    ConsultationForm,
    EmergencyAlarmForm,
    PatientRegistrationForm,
    ReferralForm,
    RoleBasedAuthenticationForm,
    SymptomEntryForm,
    VitalsForm,
)
from .models import (
    ActivityLog,
    Consultation,
    DrugStock,
    EmergencyAlarm,
    Facility,
    Invoice,
    LabResult,
    Prescription,
    Profile,
    OutbreakAlert,
    Referral,
    Reminder,
    StockDelivery,
    StockDispenseLog,
    SymptomEntry,
    Vitals,
    Visit,
)

from .ai_monitor import run_ai_monitoring
from .outbreaks import detect_outbreaks


# ── HELPERS ───────────────────────────────────────────────────────────────────

def role_required(*roles):
    """Decorator — redirects user to their dashboard if they don't have the required role."""
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            if hasattr(request.user, 'profile') and request.user.profile.role in roles:
                return view_func(request, *args, **kwargs)
            return redirect('role_redirect')
        wrapper.__name__ = view_func.__name__
        return wrapper
    return decorator


def notify_doctor_critical(entry):
    """Send SMS alert to facility emergency contact when a critical symptom entry is submitted."""
    try:
        import africastalking
        africastalking.initialize(
            username=settings.AFRICASTALKING_USERNAME,
            api_key=settings.AFRICASTALKING_API_KEY,
        )
        sms = africastalking.SMS
        sms.send(
            f"CRITICAL SYMPTOM ALERT: {entry.patient.get_full_name()} "
            f"reported {entry.body_part} — {entry.symptoms[:80]}. "
            f"Visit date: {entry.visit_date}. Ref #{entry.id}",
            [entry.facility.emergency_contact]
        )
    except Exception:
        pass  # Log in production; never break the page for SMS failures


def haversine(lat1, lng1, lat2, lng2):
    """Calculate distance in km between two GPS coordinates."""
    R = 6371
    dlat = math.radians(float(lat2) - float(lat1))
    dlng = math.radians(float(lng2) - float(lng1))
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(float(lat1))) *
         math.cos(math.radians(float(lat2))) *
         math.sin(dlng / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ── AUTH ──────────────────────────────────────────────────────────────────────

def community_pulse_view(request):
    """
    Landing page for unauthenticated users.
    Displays the Community Health Pulse overview.
    """
    if request.user.is_authenticated:
        return redirect('role_redirect')

    user_location = request.GET.get('location', '')
    active_alerts = OutbreakAlert.objects.filter(resolved=False)
    context = {
        'user_location': user_location,
        'stats': {
            'facilities': Facility.objects.filter(is_active=True).count(),
            'active_alerts': active_alerts.count(),
            'med_shortage': DrugStock.objects.filter(status__in=['low', 'out']).count(),
            'immunisation_pct': 78,
        },
        'disease_trends': [],
        'medication_supply': [],
        'environmental_factors': [],
        'community_feed': [],
    }
    return render(request, 'community_pulse.html', context)


def home_redirect(request):
    """
    Redirect authenticated users to their role dashboard;
    send unauthenticated users to the landing page.
    """
    if request.user.is_authenticated:
        return redirect('role_redirect')
    return redirect('community_pulse')


def login_view(request):
    """
    Custom login view with role-based authentication.
    Users must select their role before entering credentials.
    The selected role is validated against their profile.
    """
    if request.user.is_authenticated:
        return redirect('role_redirect')

    if request.method == 'POST':
        form = RoleBasedAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f"Welcome back, {user.first_name or user.username}!")

            next_url = request.POST.get('next') or request.GET.get('next')
            if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
                return redirect(next_url)
            return redirect('role_redirect')
    else:
        form = RoleBasedAuthenticationForm(request)

    return render(request, 'login.html', {
        'form': form
    })


def register_view(request):
    facilities = Facility.objects.all().order_by('sub_county', 'name')
    fallback_facilities = [
        'Kisumu Main', 'Nairobi West', 'Mombasa Coast',
        'Nakuru Level 5', 'Eldoret Referral', 'Kisii Teaching',
        'Machakos Level 5', 'Thika Level 5', 'Nyeri County',
        'Garissa County',
    ]

    selected_account_type = request.POST.get('account_type', 'patient') if request.method == 'POST' else 'patient'
    selected_staff_role = request.POST.get('staff_role', '') if request.method == 'POST' else ''

    staff_role_map = {
        'doctor':     'doctor',
        'nurse':      'nurse',
        'reception':  'reception',
        'lab':        'lab',
        'pharmacy':   'pharmacy',
        'billing':    'billing',
        'supervisor': 'supervisor',
        'admin':      'admin',
    }

    form = PatientRegistrationForm(request.POST or None)

    if request.method == 'POST':
        if selected_account_type == 'staff' and selected_staff_role not in staff_role_map:
            form.add_error(None, 'Please select a valid staff role.')
        elif form.is_valid():
            user = form.save(commit=False)
            user.save()

            profile = user.profile
            profile.role = staff_role_map.get(selected_staff_role, 'patient')
            profile.date_of_birth = form.cleaned_data['date_of_birth']
            profile.gender = form.cleaned_data['gender']
            profile.phone_number = form.cleaned_data['phone_number']
            profile.id_number = form.cleaned_data.get('id_number', '')
            profile.facility = form.cleaned_data['facility']
            profile.save()

            login(request, user)
            messages.success(request, f"Welcome, {user.first_name}. Your account has been created.")
            return redirect('role_redirect')

    return render(request, 'register.html', {
        'form':                 form,
        'facilities':           facilities,
        'fallback_facilities':  fallback_facilities,
        'selected_account_type': selected_account_type,
        'selected_staff_role':  selected_staff_role,
    })


@login_required
def role_redirect_view(request):
    """After login, send each user to their correct dashboard."""
    role = getattr(request.user, 'profile', None)
    role = role.role if role else 'patient'
    destinations = {
        'patient':    'patient_dashboard',
        'reception':  'reception_dashboard',
        'nurse':      'nurse_dashboard',
        'doctor':     'doctor_dashboard',
        'lab':        'lab_dashboard',
        'pharmacy':   'pharmacy_dashboard',
        'billing':    'billing_dashboard',
        'supervisor': 'supervisor_dashboard',
        'admin':      'admin_panel_dashboard',
    }
    return redirect(destinations.get(role, 'patient_dashboard'))


# ── PATIENT ───────────────────────────────────────────────────────────────────

@login_required
@role_required('patient')
def patient_dashboard(request):
    patient  = request.user
    facility = patient.profile.facility
    today    = timezone.now()

    drug_stock     = DrugStock.objects.filter(facility=facility) if facility else []
    drug_available = DrugStock.objects.filter(facility=facility, status='available').exists() if facility else False

    active_outbreaks = OutbreakAlert.objects.filter(resolved=False)
    if facility:
        active_outbreaks = active_outbreaks.filter(
            Q(county=facility.county) | Q(sub_county=facility.sub_county)
        )

    return render(request, 'patient/dashboard.html', {
        'today':               today,
        'total_visits':        Visit.objects.filter(patient=patient).count(),
        'next_appointment':    Reminder.objects.filter(patient=patient, date__gte=today).order_by('date').first(),
        'recent_visits':       Visit.objects.filter(patient=patient).order_by('-date')[:5],
        'reminders':           Reminder.objects.filter(patient=patient, date__gte=today).order_by('date')[:4],
        'drug_stock':          drug_stock,
        'drug_available':      drug_available,
        'drug_status':         'Available' if drug_available else 'Check facility',
        'pending_results':     LabResult.objects.filter(visit__patient=patient, status='pending').count(),
        'pending_lab_results': LabResult.objects.filter(visit__patient=patient, status='pending'),
        'active_outbreaks':    active_outbreaks,
    })


@login_required
@role_required('patient')
def symptom_entry(request):
    if request.method == 'POST':
        form = SymptomEntryForm(request.POST)
        if form.is_valid():
            entry          = form.save(commit=False)
            entry.patient  = request.user
            entry.save()
            if entry.severity == 'critical':
                notify_doctor_critical(entry)
            messages.success(request, 'Symptoms submitted. Your care team has been notified.')
            return redirect('patient_dashboard')
    else:
        form = SymptomEntryForm(initial={
            'facility':   request.user.profile.facility,
            'visit_date': timezone.now().date(),
        })
    return render(request, 'patient/symptom_entry.html', {
        'form':       form,
        'facilities': Facility.objects.all().order_by('name'),
        'today':      timezone.now(),
    })


@login_required
@role_required('patient')
def visit_history(request):
    visits = Visit.objects.filter(patient=request.user).order_by('-date')

    if request.GET.get('facility'):
        visits = visits.filter(facility__id=request.GET['facility'])
    if request.GET.get('from_date'):
        visits = visits.filter(date__gte=request.GET['from_date'])
    if request.GET.get('to_date'):
        visits = visits.filter(date__lte=request.GET['to_date'])
    if request.GET.get('status'):
        visits = visits.filter(status=request.GET['status'])

    paginator = Paginator(visits, 10)
    visits    = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'patient/visit_history.html', {
        'visits':             visits,
        'facilities':         Facility.objects.all().order_by('name'),
        'total_visits':       Visit.objects.filter(patient=request.user).count(),
        'facilities_visited': Visit.objects.filter(patient=request.user).values('facility').distinct().count(),
        'pending_results':    LabResult.objects.filter(visit__patient=request.user, status='pending').count(),
        'last_visit':         Visit.objects.filter(patient=request.user).order_by('-date').first(),
        'transferred_visits': Visit.objects.filter(
                                  patient=request.user,
                                  referral__isnull=False
                              ).order_by('-date'),
    })


@login_required
@role_required('patient')
def visit_detail(request, visit_id):
    visit = get_object_or_404(Visit, id=visit_id, patient=request.user)
    return render(request, 'patient/visit_detail.html', {'visit': visit})


@login_required
@role_required('patient')
def facility_finder(request):
    facilities = Facility.objects.filter(is_active=True)

    if request.GET.get('q'):
        q          = request.GET['q']
        facilities = facilities.filter(
            Q(name__icontains=q) | Q(sub_county__icontains=q)
        )
    if request.GET.get('service'):
        facilities = facilities.filter(services__name=request.GET['service'])
    if request.GET.get('level'):
        facilities = facilities.filter(level=request.GET['level'])
    if request.GET.get('drugs'):
        facilities = facilities.filter(drug_status=request.GET['drugs'])

    facilities = list(facilities)

    if request.GET.get('lat') and request.GET.get('lng'):
        user_lat = float(request.GET['lat'])
        user_lng = float(request.GET['lng'])
        for f in facilities:
            if f.latitude and f.longitude:
                f.distance_km = haversine(user_lat, user_lng, f.latitude, f.longitude)
            else:
                f.distance_km = None
        facilities = sorted(facilities, key=lambda f: f.distance_km or 9999)

    from django.conf import settings
    return render(request, 'patient/facility_finder.html', {
        'facilities':        facilities,
        'GOOGLE_MAPS_API_KEY': getattr(settings, 'GOOGLE_MAPS_API_KEY', ''),
    })


def nearby_hospitals_api(request):
    lat = request.GET.get('lat')
    lng = request.GET.get('lng')
    radius = request.GET.get('radius', '25000')

    if not lat or not lng:
        return JsonResponse({'error': 'Latitude and longitude are required.', 'hospitals': []}, status=400)

    try:
        latitude = float(lat)
        longitude = float(lng)
        radius = int(radius)
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Invalid coordinates or radius.', 'hospitals': []}, status=400)

    overpass_url = 'https://overpass-api.de/api/interpreter'
    query = f"""
        [out:json][timeout:20];
        (
          node["amenity"="hospital"](around:{radius},{latitude},{longitude});
          way["amenity"="hospital"](around:{radius},{latitude},{longitude});
          relation["amenity"="hospital"](around:{radius},{latitude},{longitude});
        );
        out center tags;
    """

    hospitals = []
    try:
        req = request.Request(
            overpass_url,
            data=query.encode('utf-8'),
            headers={
                'Content-Type': 'text/plain',
                'User-Agent': 'AfyaLink/1.0 (+https://afyalink.example.com)'
            }
        )
        with request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode('utf-8'))

        for element in payload.get('elements', []):
            if element.get('type') == 'node':
                node_lat = element.get('lat')
                node_lng = element.get('lon')
            else:
                center = element.get('center', {})
                node_lat = center.get('lat')
                node_lng = center.get('lon')

            if node_lat is None or node_lng is None:
                continue

            tags = element.get('tags', {})
            name = tags.get('name') or tags.get('operator') or 'Unnamed hospital'
            address = ', '.join(
                filter(None, [
                    tags.get('addr:street'),
                    tags.get('addr:suburb'),
                    tags.get('addr:city'),
                    tags.get('addr:county'),
                    tags.get('addr:postcode')
                ])
            )
            distance_km = round(haversine(latitude, longitude, node_lat, node_lng), 1)

            hospitals.append({
                'id': element.get('id'),
                'name': name,
                'address': address,
                'latitude': node_lat,
                'longitude': node_lng,
                'distance_km': distance_km,
                'source': 'OpenStreetMap'
            })

        hospitals.sort(key=lambda item: item['distance_km'])
    except Exception:
        return JsonResponse({'error': 'Unable to fetch nearby hospitals from OpenStreetMap.', 'hospitals': []}, status=502)

    return JsonResponse({'hospitals': hospitals})


@login_required
@role_required('patient')
def change_facility(request):
    if request.method == 'POST':
        facility = get_object_or_404(Facility, id=request.POST.get('facility_id'))
        request.user.profile.facility = facility
        request.user.profile.save()
        messages.success(request, f"Your facility has been updated to {facility.name}.")
    return redirect('patient_facility_finder')


@login_required
@role_required('patient')
def emergency_view(request):
    if request.method == 'POST':
        form = EmergencyAlarmForm(request.POST)
        if form.is_valid():
            alarm         = form.save(commit=False)
            alarm.patient = request.user
            alarm.save()
            try:
                import africastalking
                africastalking.initialize(username='sandbox', api_key='your_api_key_here')
                sms = africastalking.SMS
                sms.send(
                    f"EMERGENCY ALARM from {request.user.get_full_name()}. "
                    f"Condition: {alarm.condition_type}. "
                    f"Location: {alarm.location_description}. "
                    f"Response needed: {alarm.response_type}. "
                    f"Call: {alarm.contact_number}. Ref #{alarm.id}",
                    [alarm.facility.emergency_contact]
                )
            except Exception:
                pass
            return render(request, 'patient/emergency.html', {
                'alarm_sent': True,
                'alarm':      alarm,
                'facilities': Facility.objects.all(),
            })
    else:
        form = EmergencyAlarmForm(initial={'facility': request.user.profile.facility})

    return render(request, 'patient/emergency.html', {
        'alarm_sent': False,
        'form':       form,
        'facilities': Facility.objects.all().order_by('name'),
    })


# ── RECEPTION ─────────────────────────────────────────────────────────────────

@login_required
@role_required('reception', 'admin')
def reception_dashboard(request):
    today    = timezone.now().date()
    facility = request.user.profile.facility

    today_visits = Visit.objects.filter(
        facility=facility, date=today
    ).select_related(
        'patient', 'patient__profile', 'symptom_entry'
    ).order_by('check_in_time')

    return render(request, 'reception/dashboard.html', {
        'today':                      timezone.now(),
        'today_visits':               today_visits,
        'total_today':                today_visits.count(),
        'waiting_triage':             today_visits.filter(status='waiting').count(),
        'with_doctor':                today_visits.filter(status='in_progress').count(),
        'completed_today':            today_visits.filter(status='complete').count(),
        'triaged':                    today_visits.filter(vitals__isnull=False).count(),
        'seen_by_doctor':             today_visits.filter(consultation__isnull=False).count(),
        'incoming_referrals':         Referral.objects.filter(referred_to=facility, status='pending'),
        'unregistered_pre_arrivals':  SymptomEntry.objects.filter(
                                          facility=facility,
                                          visit_date=today,
                                          visit__isnull=True
                                      ).select_related('patient').order_by('-severity'),
        'activity_log':               ActivityLog.objects.filter(
                                          facility=facility,
                                          timestamp__date=today
                                      ).order_by('-timestamp')[:12],
    })


@login_required
@role_required('reception', 'admin')
def register_visit_view(request):
    facility = request.user.profile.facility
    today    = timezone.now()

    if request.method == 'POST':
        patient = get_object_or_404(User, id=request.POST['patient_id'])
        visit   = Visit.objects.create(
            patient              = patient,
            facility             = facility,
            date                 = request.POST.get('visit_date', today.date()),
            check_in_time        = request.POST.get('check_in_time', today.time()),
            visit_type           = request.POST.get('visit_type', 'outpatient'),
            payment_mode         = request.POST.get('payment_mode', 'cash'),
            presenting_complaint = request.POST.get('presenting_complaint', ''),
            reception_notes      = request.POST.get('reception_notes', ''),
            status               = 'waiting',
        )

        # Link incoming referral if provided
        referral_id = request.POST.get('referral')
        if referral_id:
            Referral.objects.filter(id=referral_id).update(
                status='received',
                received_at=today,
            )
            visit.visit_type = 'referral_in'
            visit.save()

        # Link pre-arrival symptom entry if it exists for today
        pre = SymptomEntry.objects.filter(
            patient=patient,
            facility=facility,
            visit_date=today.date(),
            visit__isnull=True
        ).order_by('-created_at').first()
        if pre:
            pre.visit = visit
            pre.save()

        ActivityLog.objects.create(
            facility=facility,
            user=request.user,
            message=f"Visit registered for {patient.get_full_name()} — {visit.get_visit_type_display()}"
        )
        messages.success(request, f"{patient.get_full_name()} registered. Sent to triage queue.")
        return redirect('reception_dashboard')

    return render(request, 'reception/register_visit.html', {
        'today':                      today,
        'now':                        today,
        'facilities':                 Facility.objects.all().order_by('name'),
        'today_visits':               Visit.objects.filter(
                                          facility=facility,
                                          date=today.date()
                                      ).order_by('-check_in_time')[:15],
        'unregistered_pre_arrivals':  SymptomEntry.objects.filter(
                                          facility=facility,
                                          visit_date=today.date(),
                                          visit__isnull=True
                                      ).select_related('patient'),
    })


# ── NURSE ─────────────────────────────────────────────────────────────────────

@login_required
@role_required('nurse', 'admin')
def nurse_dashboard(request):
    today    = timezone.now().date()
    facility = request.user.profile.facility

    waiting_queue = Visit.objects.filter(
        facility=facility,
        date=today,
        status='waiting',
        vitals__isnull=True,
    ).select_related(
        'patient', 'patient__profile', 'symptom_entry'
    ).order_by('check_in_time')

    triaged_list = Visit.objects.filter(
        facility=facility,
        date=today,
        vitals__isnull=False,
    ).select_related(
        'patient', 'vitals'
    ).order_by('-vitals__recorded_at')[:10]

    return render(request, 'nurse/dashboard.html', {
        'today':               timezone.now(),
        'waiting_queue':       waiting_queue,
        'waiting_count':       waiting_queue.count(),
        'triaged_today':       triaged_list.count(),
        'triaged_list':        triaged_list,
        'high_priority':       Visit.objects.filter(
                                   facility=facility,
                                   date=today,
                                   vitals__priority='high'
                               ).count(),
        'pre_arrival_count':   SymptomEntry.objects.filter(
                                   facility=facility, visit_date=today
                               ).count(),
        'pre_arrival_entries': SymptomEntry.objects.filter(
                                   facility=facility, visit_date=today
                               ).order_by('-severity').select_related('patient')[:8],
        'emergency_alarms':    EmergencyAlarm.objects.filter(facility=facility, resolved=False),
    })


@login_required
@role_required('nurse', 'admin')
def vitals_entry(request):
    facility = request.user.profile.facility
    today    = timezone.now().date()

    preselected_visit = None
    if request.GET.get('visit'):
        preselected_visit = get_object_or_404(Visit, id=request.GET['visit'], facility=facility)

    waiting_queue = Visit.objects.filter(
        facility=facility,
        date=today,
        status='waiting',
        vitals__isnull=True,
    ).select_related('patient', 'patient__profile', 'symptom_entry')

    if request.method == 'POST':
        visit = get_object_or_404(Visit, id=request.POST['visit_id'])
        vitals = Vitals.objects.create(
            visit              = visit,
            blood_pressure     = request.POST.get('blood_pressure', ''),
            temperature        = request.POST.get('temperature') or None,
            pulse              = request.POST.get('pulse') or None,
            oxygen_saturation  = request.POST.get('oxygen_saturation') or None,
            weight             = request.POST.get('weight') or None,
            respiratory_rate   = request.POST.get('respiratory_rate') or None,
            blood_sugar        = request.POST.get('blood_sugar') or None,
            pain_score         = request.POST.get('pain_score') or None,
            priority           = request.POST.get('priority', 'medium'),
            nurse_notes        = request.POST.get('nurse_notes', ''),
            recorded_by        = request.user,
        )
        visit.status = 'in_progress'
        visit.save()

        ActivityLog.objects.create(
            facility=facility,
            user=request.user,
            message=f"Vitals recorded for {visit.patient.get_full_name()} — {vitals.priority} priority"
        )

        return render(request, 'nurse/vitals_entry.html', {
            'vitals_saved':  True,
            'saved_visit':   visit,
            'saved_vitals':  vitals,
        })

    return render(request, 'nurse/vitals_entry.html', {
        'today':             timezone.now(),
        'preselected_visit': preselected_visit,
        'waiting_queue':     waiting_queue,
        'form':              VitalsForm(),
    })


# ── DOCTOR ────────────────────────────────────────────────────────────────────

@login_required
@role_required('doctor', 'admin')
def doctor_dashboard(request):
    today    = timezone.now().date()
    facility = request.user.profile.facility

    queue = Visit.objects.filter(
        facility=facility,
        date=today,
        status='in_progress',
        vitals__isnull=False,
        consultation__isnull=True,
    ).select_related(
        'patient', 'patient__profile', 'vitals', 'symptom_entry'
    ).order_by('-vitals__priority', 'check_in_time')

    return render(request, 'doctor/dashboard.html', {
        'today':               timezone.now(),
        'queue':               queue,
        'queue_count':         queue.count(),
        'emergency_alarms':    EmergencyAlarm.objects.filter(facility=facility, resolved=False),
        'pre_arrival_entries': SymptomEntry.objects.filter(
                                   facility=facility,
                                   visit_date=today,
                                   visit__isnull=True
                               ).order_by('-severity'),
        'pre_arrival_count':   SymptomEntry.objects.filter(facility=facility, visit_date=today).count(),
        'seen_today':          Visit.objects.filter(facility=facility, date=today, status='complete').count(),
        'seen_today_list':     Visit.objects.filter(
                                   facility=facility, date=today, status='complete'
                               ).order_by('-check_out_time')[:8],
        'pending_labs':        LabResult.objects.filter(visit__facility=facility, status='pending').count(),
        'pending_lab_results': LabResult.objects.filter(
                                   visit__facility=facility, status='pending'
                               ).select_related('visit__patient')[:6],
    })


@login_required
@role_required('doctor', 'admin')
def consultation_view(request, patient_id):
    patient = get_object_or_404(User, id=patient_id)
    visit   = Visit.objects.filter(
        patient=patient, status='in_progress'
    ).order_by('-date').first()

    if not visit:
        messages.error(request, "No active visit found for this patient.")
        return redirect('doctor_dashboard')

    if request.method == 'POST':
        action = request.POST.get('action', 'save')

        consultation, _ = Consultation.objects.update_or_create(
            visit=visit,
            defaults={
                'doctor':             request.user,
                'clinical_findings':  request.POST.get('clinical_findings', ''),
                'diagnosis':          request.POST.get('diagnosis', ''),
                'icd_code':           request.POST.get('icd_code', ''),
                'treatment_plan':     request.POST.get('treatment_plan', ''),
                'doctor_notes':       request.POST.get('doctor_notes', ''),
                'followup_date':      request.POST.get('followup_date') or None,
                'followup_notes':     request.POST.get('followup_notes', ''),
            }
        )

        # Save prescriptions
        drug_count = int(request.POST.get('prescription_count', 0))
        consultation.prescriptions.all().delete()
        for i in range(drug_count):
            drug_name = request.POST.get(f'drug_name_{i}')
            if drug_name:
                Prescription.objects.create(
                    consultation = consultation,
                    visit        = visit,
                    drug_name    = drug_name,
                    dosage       = request.POST.get(f'dosage_{i}', ''),
                    frequency    = request.POST.get(f'frequency_{i}', ''),
                    duration     = request.POST.get(f'duration_{i}', ''),
                )

        # Save lab orders
        lab_count = int(request.POST.get('lab_order_count', 0))
        for i in range(lab_count):
            test_name = request.POST.get(f'lab_test_{i}')
            if test_name:
                LabResult.objects.create(
                    visit       = visit,
                    test_name   = test_name,
                    urgency     = request.POST.get(f'lab_urgency_{i}', 'routine'),
                    notes       = request.POST.get(f'lab_notes_{i}', ''),
                    status      = 'pending',
                    ordered_by  = request.user,
                )

        # Handle referral
        refer_to = request.POST.get('refer_to')
        if refer_to:
            Referral.objects.update_or_create(
                visit=visit,
                defaults={
                    'patient':          patient,
                    'from_facility':    request.user.profile.facility,
                    'referred_to_id':   refer_to,
                    'reason':           request.POST.get('referral_reason', ''),
                    'urgency':          request.POST.get('referral_urgency', 'routine'),
                    'referring_doctor': request.user,
                    'status':           'pending',
                }
            )

        detect_outbreaks()

        if action == 'complete':
            visit.status         = 'complete'
            visit.doctor         = request.user
            visit.check_out_time = timezone.now().time()
            visit.save()
            # Auto-create a blank invoice
            Invoice.objects.get_or_create(visit=visit)
            messages.success(request, "Consultation complete. Prescription sent to pharmacy.")
            return redirect('doctor_dashboard')

        messages.success(request, "Consultation saved as draft.")
        return redirect('doctor_consultation', patient_id=patient_id)

    return render(request, 'doctor/consultation.html', {
        'visit':        visit,
        'consultation': getattr(visit, 'consultation', None),
        'lab_orders':   LabResult.objects.filter(visit=visit, status='pending'),
        'past_visits':  Visit.objects.filter(
                            patient=patient, status='complete'
                        ).exclude(id=visit.id).order_by('-date')[:5],
        'facilities':   Facility.objects.exclude(
                            id=request.user.profile.facility.id
                        ).order_by('level', 'name'),
        'form':         ConsultationForm(),
    })


@login_required
@role_required('doctor', 'admin')
def patient_history(request):
    patient        = None
    visits         = []
    search_results = []
    visited_facilities = []
    last_visit     = None

    patient_id = request.GET.get('patient')
    if patient_id:
        patient = get_object_or_404(User, id=patient_id, profile__role='patient')
    elif request.GET.get('q'):
        q = request.GET['q']
        search_results = User.objects.filter(
            profile__role='patient'
        ).filter(
            Q(first_name__icontains=q) |
            Q(last_name__icontains=q)  |
            Q(username__icontains=q)   |
            Q(profile__phone_number__icontains=q)
        ).select_related('profile', 'profile__facility')[:10]

    if patient:
        qs = Visit.objects.filter(patient=patient).order_by('-date')

        if request.GET.get('facility'):
            qs = qs.filter(facility__id=request.GET['facility'])
        if request.GET.get('from_date'):
            qs = qs.filter(date__gte=request.GET['from_date'])
        if request.GET.get('to_date'):
            qs = qs.filter(date__lte=request.GET['to_date'])

        paginator  = Paginator(qs, 8)
        visits     = paginator.get_page(request.GET.get('page', 1))
        last_visit = qs.first()

        visited_facilities = Facility.objects.filter(
            visit__patient=patient
        ).annotate(visit_count=Count('visit')).order_by('-visit_count')

    return render(request, 'doctor/patient_history.html', {
        'patient':            patient,
        'visits':             visits,
        'search_results':     search_results,
        'total_visits':       Visit.objects.filter(patient=patient).count() if patient else 0,
        'facilities_visited': visited_facilities.count() if patient else 0,
        'pending_results':    LabResult.objects.filter(visit__patient=patient, status='pending').count() if patient else 0,
        'last_visit':         last_visit,
        'visited_facilities': visited_facilities,
    })


@login_required
@role_required('doctor', 'admin')
def referral_form(request):
    preselected_patient = None
    active_visit        = None

    if request.GET.get('patient'):
        preselected_patient = get_object_or_404(User, id=request.GET['patient'], profile__role='patient')
        active_visit = Visit.objects.filter(
            patient=preselected_patient, status='in_progress'
        ).order_by('-date').first()

    facilities = Facility.objects.exclude(
        id=request.user.profile.facility.id
    ).order_by('level', 'name')

    facilities_by_level = {}
    for f in facilities:
        facilities_by_level.setdefault(f.level, []).append(f)

    facility_levels = [
        (2, 'Level 2 — Dispensary'),
        (3, 'Level 3 — Health centre'),
        (4, 'Level 4 — Sub-county hospital'),
        (5, 'Level 5 — County hospital'),
        (6, 'Level 6 — Referral hospital'),
    ]

    if request.method == 'POST':
        patient  = get_object_or_404(User, id=request.POST['patient_id'])
        referral = Referral.objects.create(
            patient               = patient,
            from_facility         = request.user.profile.facility,
            referred_to_id        = request.POST['referred_to'],
            urgency               = request.POST['urgency'],
            reason                = request.POST['reason'],
            specialist_needed     = request.POST.get('specialist_needed', ''),
            transport_mode        = request.POST.get('transport_mode', 'own'),
            accompanying_staff    = request.POST.get('accompanying_staff', ''),
            referring_doctor_notes= request.POST.get('referring_doctor_notes', ''),
            referring_doctor      = request.user,
            status                = 'pending',
        )
        if request.POST.get('visit_id'):
            referral.visit_id = request.POST['visit_id']
            referral.save()

        return render(request, 'doctor/referral_form.html', {
            'referral_sent': True,
            'referral':      referral,
        })

    return render(request, 'doctor/referral_form.html', {
        'referral_sent':       False,
        'preselected_patient': preselected_patient,
        'active_visit':        active_visit,
        'facilities_by_level': facilities_by_level,
        'facility_levels':     facility_levels,
        'recent_referrals':    Referral.objects.filter(referring_doctor=request.user).order_by('-date')[:5],
        'form':                ReferralForm(),
    })


# ── LAB ───────────────────────────────────────────────────────────────────────

@login_required
@role_required('lab', 'admin')
def lab_dashboard(request):
    facility = request.user.profile.facility
    today    = timezone.now().date()

    pending_orders   = LabResult.objects.filter(
        visit__facility=facility, status='pending'
    ).select_related('visit__patient', 'ordered_by').order_by('urgency', 'date_ordered')

    completed_orders = LabResult.objects.filter(
        visit__facility=facility,
        date_resulted__date=today,
    ).exclude(status='pending').select_related('visit__patient').order_by('-date_resulted')

    abnormal_results = LabResult.objects.filter(
        visit__facility=facility, status='abnormal'
    ).select_related('visit__patient')

    return render(request, 'lab/dashboard.html', {
        'today':            timezone.now(),
        'pending_orders':   pending_orders,
        'pending_count':    pending_orders.count(),
        'urgent_count':     pending_orders.filter(urgency__in=['urgent', 'stat']).count(),
        'completed_today':  completed_orders.count(),
        'completed_orders': completed_orders[:10],
        'abnormal_results': abnormal_results,
        'abnormal_count':   abnormal_results.count(),
    })


@login_required
@role_required('lab', 'admin')
def results_entry(request):
    facility = request.user.profile.facility

    preselected_order = None
    if request.GET.get('order'):
        preselected_order = get_object_or_404(LabResult, id=request.GET['order'])

    pending_orders = LabResult.objects.filter(
        visit__facility=facility, status='pending'
    ).select_related('visit__patient', 'ordered_by').order_by('urgency', 'date_ordered')

    if request.method == 'POST':
        order = get_object_or_404(LabResult, id=request.POST['order_id'])
        order.result_value  = request.POST.get('result_value', '')
        order.unit          = request.POST.get('unit', '')
        order.normal_range  = request.POST.get('normal_range', '')
        order.lab_notes     = request.POST.get('lab_notes', '')
        order.status        = request.POST.get('status', 'ready')
        order.date_resulted = timezone.now()
        order.resulted_by   = request.user
        order.save()

        return render(request, 'lab/results_entry.html', {
            'result_saved': True,
            'saved_result': order,
        })

    return render(request, 'lab/results_entry.html', {
        'today':             timezone.now(),
        'now':               timezone.now(),
        'preselected_order': preselected_order,
        'pending_orders':    pending_orders,
        'form':              {},
    })


# ── PHARMACY ──────────────────────────────────────────────────────────────────

@login_required
@role_required('pharmacy', 'admin')
def pharmacy_dashboard(request):
    facility = request.user.profile.facility
    today    = timezone.now().date()

    # Group pending prescriptions by visit
    pending_visits = Visit.objects.filter(
        facility=facility,
        prescriptions__dispensed=False,
    ).distinct().select_related('patient').prefetch_related('prescriptions')

    pending_prescriptions = []
    for visit in pending_visits:
        undispensed = visit.prescriptions.filter(dispensed=False)
        if undispensed.exists():
            pending_prescriptions.append({
                'visit_id':    visit.id,
                'patient_name': visit.patient.get_full_name(),
                'doctor_name':  visit.doctor.get_full_name() if visit.doctor else '—',
                'time':         visit.check_in_time.strftime('%H:%M') if visit.check_in_time else '—',
                'drugs':        list(undispensed),
            })

    stock      = DrugStock.objects.filter(facility=facility)
    dispensed  = Prescription.objects.filter(
        visit__facility=facility,
        dispensed=True,
        dispensed_at__date=today,
    ).select_related('visit__patient')

    from .models import DrugShortageAlert
    shortage_alerts = DrugShortageAlert.objects.filter(
        facility=facility,
        resolved=False,
    ).select_related('drug_stock').order_by('-severity', 'days_until_runout')

    return render(request, 'pharmacy/dashboard.html', {
        'today':                timezone.now(),
        'pending_prescriptions': pending_prescriptions,
        'pending_count':         len(pending_prescriptions),
        'dispensed_today':       dispensed.count(),
        'dispensed_list':        dispensed[:20],
        'low_stock_count':       stock.filter(status='low').count(),
        'out_of_stock_count':    stock.filter(status='out').count(),
        'low_stock_drugs':       stock.filter(status='low'),
        'out_of_stock_drugs':    stock.filter(status='out'),
        'shortage_alerts':       shortage_alerts,
    })


@login_required
@role_required('pharmacy', 'admin')
def dispense_view(request):
    facility = request.user.profile.facility

    preselected_visit = None
    if request.GET.get('visit'):
        preselected_visit = get_object_or_404(Visit, id=request.GET['visit'], facility=facility)

    pending_visits = Visit.objects.filter(
        facility=facility,
        prescriptions__dispensed=False,
    ).distinct().select_related('patient')

    stock_summary = []
    if preselected_visit:
        drug_names  = preselected_visit.prescriptions.values_list('drug_name', flat=True)
        stock_summary = DrugStock.objects.filter(
            facility=facility,
            drug_name__in=drug_names
        )

    if request.method == 'POST':
        visit = get_object_or_404(Visit, id=request.POST['visit_id'], facility=facility)

        for rx in visit.prescriptions.filter(dispensed=False):
            if request.POST.get(f'dispense_{rx.id}'):
                qty = int(request.POST.get(f'qty_{rx.id}', 1))
                rx.dispensed          = True
                rx.quantity_dispensed = qty
                rx.dispensed_at       = timezone.now()
                rx.dispensed_by       = request.user
                rx.save()

                # Deduct from stock
                stock_item = DrugStock.objects.filter(
                    facility=facility, drug_name__iexact=rx.drug_name
                ).first()
                if stock_item:
                    stock_item.quantity_dispensed += qty
                    stock_item.update_status()
                    StockDispenseLog.objects.create(
                        drug_stock=stock_item,
                        prescription=rx,
                        quantity_dispensed=qty,
                        dispensed_by=request.user,
                    )

        # Notify billing
        Invoice.objects.get_or_create(visit=visit)

        return render(request, 'pharmacy/dispense.html', {
            'dispensed':       True,
            'dispensed_visit': visit,
        })

    return render(request, 'pharmacy/dispense.html', {
        'preselected_visit': preselected_visit,
        'pending_visits':    pending_visits,
        'stock_summary':     stock_summary,
    })


# ── BILLING ───────────────────────────────────────────────────────────────────

@login_required
@role_required('billing', 'admin')
def billing_dashboard(request):
    facility = request.user.profile.facility
    today    = timezone.now().date()

    ready_visits = Visit.objects.filter(
        facility=facility,
        status='complete',
    ).select_related('patient', 'patient__profile').prefetch_related(
        'prescriptions', 'lab_results'
    ).order_by('-date')

    paid_invoices   = Invoice.objects.filter(visit__facility=facility, paid=True, paid_at__date=today)
    unpaid_invoices = Invoice.objects.filter(visit__facility=facility, paid=False)

    revenue_today = paid_invoices.aggregate(total=Sum('consultation_fee') +
                                                  Sum('lab_fee') +
                                                  Sum('pharmacy_fee'))['total'] or 0

    return render(request, 'billing/dashboard.html', {
        'today':           timezone.now(),
        'ready_visits':    ready_visits,
        'pending_count':   ready_visits.filter(invoice__isnull=True).count(),
        'billed_today':    paid_invoices.count(),
        'unpaid_count':    unpaid_invoices.count(),
        'revenue_today':   revenue_today,
        'recent_payments': paid_invoices.select_related('visit__patient').order_by('-paid_at')[:10],
        'cash_count':      paid_invoices.filter(visit__payment_mode='cash').count(),
        'nhif_count':      paid_invoices.filter(visit__payment_mode='nhif').count(),
        'insurance_count': paid_invoices.filter(visit__payment_mode='insurance').count(),
        'free_count':      Visit.objects.filter(facility=facility, date=today, payment_mode='free').count(),
        'cash_total':      paid_invoices.filter(visit__payment_mode='cash').aggregate(
                               t=Sum('consultation_fee'))['t'] or 0,
        'nhif_total':      paid_invoices.filter(visit__payment_mode='nhif').aggregate(
                               t=Sum('consultation_fee'))['t'] or 0,
        'insurance_total': paid_invoices.filter(visit__payment_mode='insurance').aggregate(
                               t=Sum('consultation_fee'))['t'] or 0,
    })


@login_required
@role_required('billing', 'admin')
def invoice_view(request):
    facility = request.user.profile.facility
    visit    = None
    invoice  = None

    if request.GET.get('visit'):
        visit   = get_object_or_404(Visit, id=request.GET['visit'], facility=facility)
        invoice, _ = Invoice.objects.get_or_create(visit=visit)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'mark_paid':
            visit   = get_object_or_404(Visit, id=request.POST['visit_id'], facility=facility)
            invoice = get_object_or_404(Invoice, visit=visit)
            invoice.paid    = True
            invoice.paid_at = timezone.now()
            invoice.save()
            messages.success(request, "Invoice marked as paid.")
            return redirect(f"{request.path}?visit={visit.id}")

    search_results = []
    if request.GET.get('q'):
        q = request.GET['q']
        search_results = Visit.objects.filter(
            facility=facility,
            status='complete',
        ).filter(
            Q(patient__first_name__icontains=q) |
            Q(patient__last_name__icontains=q)
        ).select_related('patient', 'invoice').order_by('-date')[:10]

    today_invoices = Invoice.objects.filter(
        visit__facility=facility,
        created_at__date=timezone.now().date()
    ).select_related('visit__patient').order_by('-created_at')

    return render(request, 'billing/invoice.html', {
        'today':          timezone.now(),
        'visit':          visit,
        'invoice':        invoice,
        'search_results': search_results,
        'today_invoices': today_invoices,
    })


# ── SUPERVISOR ────────────────────────────────────────────────────────────────

@login_required
@role_required('supervisor', 'admin')
def supervisor_dashboard(request):
    facility    = request.user.profile.facility
    stock_items = DrugStock.objects.filter(facility=facility).order_by('drug_name')

    from .models import DrugShortageAlert
    shortage_alerts = DrugShortageAlert.objects.filter(
        facility=facility,
        resolved=False,
    ).select_related('drug_stock').order_by('-severity', 'days_until_runout')

    return render(request, 'supervisor/dashboard.html', {
        'today':              timezone.now(),
        'stock_items':        stock_items,
        'in_stock_count':     stock_items.filter(status='available').count(),
        'low_stock_count':    stock_items.filter(status='low').count(),
        'out_of_stock_count': stock_items.filter(status='out').count(),
        'alerts_today':       shortage_alerts.count(),
        'out_of_stock_drugs': stock_items.filter(status='out'),
        'low_stock_drugs':    stock_items.filter(status='low'),
        'shortage_alerts':    shortage_alerts,
        'recent_deliveries':  StockDelivery.objects.filter(
                                  facility=facility
                              ).select_related('logged_by').order_by('-date')[:10],
    })


@login_required
@role_required('supervisor', 'admin')
def stock_entry(request):
    facility    = request.user.profile.facility
    stock_items = DrugStock.objects.filter(facility=facility).order_by('drug_name')

    known_drugs = list(stock_items.values_list('drug_name', flat=True).distinct())

    if request.method == 'POST':
        drug_name  = request.POST['drug_name']
        quantity   = int(request.POST['quantity'])
        unit       = request.POST.get('unit', 'tablets')
        batch      = request.POST.get('batch_number', '')

        stock_item, created = DrugStock.objects.get_or_create(
            facility=facility,
            drug_name=drug_name,
            batch_number=batch,
            defaults={
                'unit':                unit,
                'category':            request.POST.get('category', ''),
                'supplier':            request.POST.get('supplier', ''),
                'expiry_date':         request.POST.get('expiry_date') or None,
                'low_stock_threshold': int(request.POST.get('low_stock_threshold', 50)),
                'delivery_notes':      request.POST.get('delivery_notes', ''),
            }
        )

        if not created:
            stock_item.quantity_delivered    += quantity
            stock_item.low_stock_threshold    = int(request.POST.get('low_stock_threshold', 50))
            stock_item.last_delivery_date     = timezone.now().date()
            stock_item.save()
        else:
            stock_item.quantity_delivered = quantity
            stock_item.last_delivery_date = timezone.now().date()
            stock_item.save()

        stock_item.update_status()

        delivery = StockDelivery.objects.create(
            drug_stock   = stock_item,
            drug_name    = drug_name,
            facility     = facility,
            quantity     = quantity,
            unit         = unit,
            supplier     = request.POST.get('supplier', ''),
            date         = request.POST.get('delivery_date', timezone.now().date()),
            batch_number = batch,
            expiry_date  = request.POST.get('expiry_date') or None,
            logged_by    = request.user,
            notes        = request.POST.get('delivery_notes', ''),
        )

        new_level = stock_item.quantity_remaining
        return render(request, 'supervisor/stock_entry.html', {
            'delivery_saved':   True,
            'saved_delivery':   delivery,
            'new_stock_level':  new_level,
        })

    return render(request, 'supervisor/stock_entry.html', {
        'today':       timezone.now(),
        'stock_items': stock_items,
        'known_drugs': known_drugs,
        'facilities':  Facility.objects.all().order_by('name'),
        'form':        {},
    })


@login_required
@role_required('supervisor', 'admin')
def stock_report(request):
    facility    = request.user.profile.facility
    stock_items = DrugStock.objects.filter(facility=facility)

    if request.GET.get('drug'):
        stock_items = stock_items.filter(drug_name__icontains=request.GET['drug'])
    if request.GET.get('category'):
        stock_items = stock_items.filter(category=request.GET['category'])
    if request.GET.get('status'):
        stock_items = stock_items.filter(status=request.GET['status'])

    # Top consumed — most dispensed in period
    top_consumed = list(stock_items.order_by('-quantity_dispensed')[:10])
    if top_consumed:
        max_qty = top_consumed[0].quantity_dispensed or 1
        for item in top_consumed:
            item.percent = int((item.quantity_dispensed / max_qty) * 100)

    return render(request, 'supervisor/stock_report.html', {
        'today':         timezone.now(),
        'report_items':  stock_items.order_by('drug_name'),
        'top_consumed':  top_consumed,
        'period_label':  'all time',
        'summary': {
            'available':        stock_items.filter(status='available').count(),
            'low':              stock_items.filter(status='low').count(),
            'out':              stock_items.filter(status='out').count(),
            'total_deliveries': StockDelivery.objects.filter(facility=facility).count(),
        },
    })


# ── ADMIN PANEL ───────────────────────────────────────────────────────────────

@login_required
@role_required('admin')
def admin_dashboard(request):
    return render(request, 'admin_panel/dashboard.html', {
        'today':          timezone.now(),
        'total_users':    User.objects.count(),
        'total_facilities': Facility.objects.count(),
        'total_visits':   Visit.objects.count(),
        'facilities':     Facility.objects.all().order_by('level', 'name'),
        'recent_users':   User.objects.order_by('-date_joined')[:10],
    })


@login_required
@role_required('admin')
def manage_facilities(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add':
            Facility.objects.create(
                name          = request.POST['name'],
                level         = request.POST['level'],
                sub_county    = request.POST['sub_county'],
                county        = request.POST.get('county', 'Kisii'),
                address       = request.POST.get('address', ''),
                phone         = request.POST.get('phone', ''),
                latitude      = request.POST.get('latitude') or None,
                longitude     = request.POST.get('longitude') or None,
                operating_hours = request.POST.get('operating_hours', ''),
            )
            messages.success(request, "Facility added successfully.")
        elif action == 'toggle':
            facility = get_object_or_404(Facility, id=request.POST['facility_id'])
            facility.is_active = not facility.is_active
            facility.save()
            messages.success(request, f"{facility.name} {'activated' if facility.is_active else 'deactivated'}.")
        return redirect('admin_panel_manage_facilities')

    return render(request, 'admin_panel/manage_facilities.html', {
        'facilities': Facility.objects.all().order_by('level', 'name'),
    })


# ── INTERNAL JSON APIS ────────────────────────────────────────────────────────

@login_required
def patient_search_api(request):
    q = request.GET.get('q', '').strip()
    if not q or len(q) < 2:
        return JsonResponse({'patients': []})

    users = User.objects.filter(
        profile__role='patient'
    ).filter(
        Q(first_name__icontains=q) |
        Q(last_name__icontains=q)  |
        Q(username__icontains=q)   |
        Q(profile__phone_number__icontains=q)
    ).select_related('profile', 'profile__facility')[:10]

    today   = timezone.now().date()
    results = []
    for u in users:
        pre = SymptomEntry.objects.filter(
            patient=u, visit_date=today
        ).order_by('-created_at').first()
        results.append({
            'id':                  u.id,
            'full_name':           u.get_full_name() or u.username,
            'meta':                f"{getattr(u.profile, 'phone_number', '')} — {getattr(u.profile.facility, 'name', 'No facility')}",
            'has_pre_arrival':     pre is not None,
            'pre_arrival_summary': (
                f"{pre.body_part} — {pre.severity} — {pre.symptoms[:80]}"
                if pre else ''
            ),
        })
    return JsonResponse({'patients': results})


@login_required
def facilities_api(request):
    facilities = Facility.objects.filter(is_active=True).values(
        'id', 'name', 'level', 'sub_county',
        'latitude', 'longitude', 'drug_status', 'phone'
    )
    return JsonResponse({'facilities': list(facilities)})


@login_required
def nearby_hospitals_api(request):
    lat = request.GET.get('lat')
    lng = request.GET.get('lng')
    radius = request.GET.get('radius', '25000')

    if not lat or not lng:
        return JsonResponse({'error': 'lat and lng are required'}, status=400)

    try:
        user_lat = float(lat)
        user_lng = float(lng)
        radius = int(radius)
    except ValueError:
        return JsonResponse({'error': 'Invalid lat, lng or radius'}, status=400)

    overpass_url = 'https://overpass-api.de/api/interpreter'
    query = f"""
[out:json][timeout:25];
(
  node["amenity"="hospital"](around:{radius},{user_lat},{user_lng});
  way["amenity"="hospital"](around:{radius},{user_lat},{user_lng});
  relation["amenity"="hospital"](around:{radius},{user_lat},{user_lng});
  node["healthcare"="hospital"](around:{radius},{user_lat},{user_lng});
  way["healthcare"="hospital"](around:{radius},{user_lat},{user_lng});
  relation["healthcare"="hospital"](around:{radius},{user_lat},{user_lng});
);
out center tags;
"""

    try:
        data = parse.urlencode({'data': query}).encode('utf-8')
        req = request.Request(overpass_url, data=data, headers={'User-Agent': 'AfyaLink/1.0'})
        response = request.urlopen(req, timeout=30)
        payload = json.loads(response.read().decode('utf-8'))
    except Exception as exc:
        return JsonResponse({'error': 'External API error', 'details': str(exc)}, status=502)

    hospitals = []
    for element in payload.get('elements', []):
        if element.get('type') == 'node':
            lat0 = element.get('lat')
            lng0 = element.get('lon')
        else:
            center = element.get('center', {})
            lat0 = center.get('lat')
            lng0 = center.get('lon')

        if lat0 is None or lng0 is None:
            continue

        tags = element.get('tags', {})
        name = tags.get('name') or tags.get('operator') or 'Hospital'
        address = ', '.join(filter(None, [
            tags.get('addr:street'),
            tags.get('addr:city'),
            tags.get('addr:suburb'),
            tags.get('addr:county'),
            tags.get('addr:postcode'),
        ]))
        if not address:
            address = tags.get('addr:full', '')

        distance = haversine(user_lat, user_lng, lat0, lng0)
        hospitals.append({
            'osm_id': element.get('id'),
            'osm_type': element.get('type'),
            'name': name,
            'latitude': lat0,
            'longitude': lng0,
            'address': address,
            'phone': tags.get('phone', ''),
            'website': tags.get('website', ''),
            'distance_km': round(distance, 2),
        })

    hospitals = sorted(hospitals, key=lambda x: x['distance_km'])[:50]
    return JsonResponse({'hospitals': hospitals})


@login_required
def stock_api(request, facility_id):
    stock = DrugStock.objects.filter(facility_id=facility_id).values(
        'drug_name', 'quantity_remaining', 'unit', 'status'
    )
    return JsonResponse({'stock': list(stock)})
