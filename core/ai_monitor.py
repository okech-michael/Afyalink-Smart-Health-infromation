import logging
from datetime import timedelta
from urllib import request

from django.conf import settings
from django.db.models import Avg, Count, Max, Sum, Q
from django.utils import timezone

from .models import (
    DrugStock,
    DrugShortageAlert,
    Facility,
    Profile,
    StockDelivery,
    StockDispenseLog,
)

logger = logging.getLogger(__name__)

# AI prediction configuration
SHORTAGE_LOOKBACK_DAYS = 30
SHORTAGE_FORECAST_DAYS = 14
CONSUMPTION_MIN_DAYS_DATA = 5
CRITICAL_THRESHOLD_MULTIPLIER = 0.5
WARNING_THRESHOLD_MULTIPLIER = 0.75


def calculate_daily_consumption(drug_stock, days=30):
    """Calculate average daily consumption for a drug at a facility."""
    start_date = timezone.now().date() - timedelta(days=days)
    logs = StockDispenseLog.objects.filter(
        drug_stock=drug_stock,
        date__gte=start_date,
    ).values('date').annotate(total=Sum('quantity_dispensed'))
    
    if not logs:
        return 0
    
    daily_average = sum(log['total'] for log in logs) / len(list(logs))
    return daily_average


def forecast_stock_runout(drug_stock, forecast_days=SHORTAGE_FORECAST_DAYS):
    """
    Predict when a drug will run out based on consumption patterns.
    Returns number of days until predicted runout, or None if sufficient stock.
    """
    daily_consumption = calculate_daily_consumption(
        drug_stock, 
        days=SHORTAGE_LOOKBACK_DAYS
    )
    
    if daily_consumption == 0:
        return None
    
    remaining = drug_stock.quantity_remaining
    days_until_runout = remaining / daily_consumption
    
    if days_until_runout <= forecast_days:
        return int(days_until_runout)
    
    return None


def _send_supplier_notification(alert):
    """Send SMS/email to supplier/admin about pending drug shortage."""
    supplier_profiles = Profile.objects.filter(
        role__in=['supervisor', 'admin'],
        facility=alert.facility,
    ).select_related('user')
    
    message = (
        f"DRUG SHORTAGE ALERT: {alert.drug_stock.drug_name} at {alert.facility.name} "
        f"will run out in ~{alert.days_until_runout} days. "
        f"Current stock: {alert.drug_stock.quantity_remaining} {alert.drug_stock.unit}. "
        f"Daily usage: {alert.estimated_daily_consumption:.1f} {alert.drug_stock.unit}. "
        f"Please arrange immediate delivery to avoid stockout."
    )
    
    sms_numbers = {
        profile.phone_number.strip()
        for profile in supplier_profiles
        if profile.phone_number and profile.phone_number.strip()
    }
    
    if sms_numbers:
        try:
            import africastalking
            africastalking.initialize(
                username=settings.AFRICASTALKING_USERNAME,
                api_key=settings.AFRICASTALKING_API_KEY,
            )
            sms = africastalking.SMS
            sms.send(message, list(sms_numbers))
        except Exception:
            pass


def detect_drug_shortages():
    """
    AI prediction: analyze drug consumption and predict shortages.
    Create alerts for drugs that will run out within forecast window.
    """
    now = timezone.now()
    alerts = []
    
    drug_stocks = DrugStock.objects.filter(
        facility__is_active=True,
        status__in=['available', 'low']
    )
    
    for stock in drug_stocks:
        days_until_runout = forecast_stock_runout(stock)
        
        if days_until_runout is None:
            continue
        
        daily_consumption = calculate_daily_consumption(stock)
        
        is_critical = days_until_runout <= (SHORTAGE_FORECAST_DAYS * CRITICAL_THRESHOLD_MULTIPLIER)
        severity = 'critical' if is_critical else 'warning'
        
        existing_alert = DrugShortageAlert.objects.filter(
            drug_stock=stock,
            resolved=False,
        ).first()
        
        if existing_alert:
            existing_alert.days_until_runout = days_until_runout
            existing_alert.estimated_daily_consumption = daily_consumption
            existing_alert.severity = severity
            existing_alert.last_predicted_at = now
            existing_alert.save(update_fields=[
                'days_until_runout',
                'estimated_daily_consumption', 
                'severity',
                'last_predicted_at',
            ])
            alert = existing_alert
        else:
            alert = DrugShortageAlert.objects.create(
                facility=stock.facility,
                drug_stock=stock,
                days_until_runout=days_until_runout,
                estimated_daily_consumption=daily_consumption,
                severity=severity,
                predicted_at=now,
                last_predicted_at=now,
            )
        
        _send_supplier_notification(alert)
        alerts.append(alert)
    
    return alerts


def run_ai_monitoring():
    """
    Main AI monitoring routine: analyze health trends, diagnoses, and drug supply.
    Called periodically to run all predictions and detection systems.
    """
    results = {
        'drug_shortages': [],
        'timestamp': timezone.now(),
    }
    
    results['drug_shortages'] = detect_drug_shortages()
    
    return results
