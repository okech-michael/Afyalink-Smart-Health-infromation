import json
from urllib import request

from django.conf import settings
from django.db.models import Count, Max
from django.utils import timezone

from .models import Consultation, Facility, OutbreakAlert, Profile


# Simulated AI outbreak detection logic built on consultation diagnosis patterns.
# This module detects clustered diagnoses across multiple facilities in the same
# region and sends alerts to registered patients through SMS and Firebase push.
OUTBREAK_WINDOW_DAYS = 5
OUTBREAK_PRIOR_WINDOW_DAYS = 14
OUTBREAK_MIN_CASES = 6
OUTBREAK_MIN_FACILITIES = 2

OUTBREAK_ADVICE = (
    "Wash your hands regularly, keep physical distance, stay hydrated, "
    "and seek medical help if you develop fever, cough, difficulty breathing, "
    "or severe fatigue."
)


def send_africastalking_sms(message, recipients):
    if not recipients:
        return

    try:
        import africastalking

        africastalking.initialize(
            username=settings.AFRICASTALKING_USERNAME,
            api_key=settings.AFRICASTALKING_API_KEY,
        )
        sms = africastalking.SMS
        sms.send(message, recipients)
    except Exception:
        pass


def send_firebase_push(title, body, tokens, data=None):
    if not tokens or not getattr(settings, 'FIREBASE_SERVER_KEY', None):
        return

    payload = {
        'registration_ids': list(tokens),
        'notification': {
            'title': title,
            'body': body,
        },
        'data': data or {},
    }
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'key={settings.FIREBASE_SERVER_KEY}',
    }
    try:
        req = request.Request(
            'https://fcm.googleapis.com/fcm/send',
            data=json.dumps(payload).encode('utf-8'),
            headers=headers,
        )
        with request.urlopen(req, timeout=10) as response:
            response.read()
    except Exception:
        pass


def _build_alert_description(county, sub_county, diagnosis, case_count, facility_count):
    region_label = sub_county or county or 'your area'
    return (
        f"{diagnosis} activity is rising in {region_label}. "
        f"{case_count} cases have been confirmed across {facility_count} facilities. "
        "Please follow prevention guidance and seek care if symptoms worsen."
    )


def detect_outbreaks():
    now = timezone.now()
    window_start = now - timezone.timedelta(days=OUTBREAK_WINDOW_DAYS)
    prior_window_start = now - timezone.timedelta(days=OUTBREAK_PRIOR_WINDOW_DAYS)
    prior_window_end = window_start

    recent_consultations = Consultation.objects.filter(
        created_at__gte=window_start,
        diagnosis__isnull=False,
    ).exclude(diagnosis='')

    groups = recent_consultations.values(
        'visit__facility__county',
        'visit__facility__sub_county',
        'diagnosis',
    ).annotate(
        case_count=Count('id'),
        facility_count=Count('visit__facility', distinct=True),
        last_reported=Max('created_at'),
    ).order_by('-case_count')

    alerts = []
    for group in groups:
        case_count = group['case_count']
        facility_count = group['facility_count']
        if case_count < OUTBREAK_MIN_CASES or facility_count < OUTBREAK_MIN_FACILITIES:
            continue

        county = group['visit__facility__county'] or ''
        sub_county = group['visit__facility__sub_county'] or ''
        diagnosis = group['diagnosis'].strip()
        if not diagnosis:
            continue

        previous_count = Consultation.objects.filter(
            created_at__gte=prior_window_start,
            created_at__lt=prior_window_end,
            diagnosis__iexact=diagnosis,
            visit__facility__county=county,
            visit__facility__sub_county=sub_county,
        ).count()

        if previous_count and case_count < max(previous_count * 1.25, OUTBREAK_MIN_CASES):
            continue

        facilities = Facility.objects.filter(county=county, sub_county=sub_county)
        message = _build_alert_description(county, sub_county, diagnosis, case_count, facility_count)
        next_steps = OUTBREAK_ADVICE

        alert = OutbreakAlert.objects.filter(
            county=county,
            sub_county=sub_county,
            diagnosis__iexact=diagnosis,
            resolved=False,
        ).first()

        if alert:
            alert.case_count = case_count
            alert.facility_count = facility_count
            alert.last_detected_at = group['last_reported']
            alert.message = message
            alert.next_steps = next_steps
            alert.save(update_fields=['case_count', 'facility_count', 'last_detected_at', 'message', 'next_steps'])
        else:
            alert = OutbreakAlert.objects.create(
                county=county,
                sub_county=sub_county,
                diagnosis=diagnosis,
                case_count=case_count,
                facility_count=facility_count,
                start_date=timezone.now().date(),
                last_detected_at=group['last_reported'],
                message=message,
                next_steps=next_steps,
            )

        alert.affected_facilities.set(facilities)

        patient_profiles = Profile.objects.filter(
            facility__county=county,
            facility__sub_county=sub_county,
            role='patient',
        ).select_related('user', 'facility')

        sms_numbers = {
            profile.phone_number.strip()
            for profile in patient_profiles
            if profile.phone_number and profile.phone_number.strip()
        }
        firebase_tokens = {
            profile.firebase_token.strip()
            for profile in patient_profiles
            if profile.firebase_token and profile.firebase_token.strip()
        }

        alert_text = (
            f"Health Alert — {diagnosis} is spreading in {sub_county or county}. "
            f"{case_count} confirmed cases across {facility_count} facilities. "
            f"{OUTBREAK_ADVICE}"
        )
        title = f"Outbreak alert: {diagnosis}"

        send_africastalking_sms(alert_text, list(sms_numbers))
        send_firebase_push(title, alert_text, list(firebase_tokens), data={
            'diagnosis': diagnosis,
            'county': county,
            'sub_county': sub_county,
            'case_count': case_count,
        })

        alerts.append(alert)

    return alerts
