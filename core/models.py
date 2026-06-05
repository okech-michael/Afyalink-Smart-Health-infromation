from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


# ── FACILITY ──────────────────────────────────────────────────────────────────

class Facility(models.Model):

    LEVEL_CHOICES = [
        (1, 'Level 1 — Community health unit'),
        (2, 'Level 2 — Dispensary'),
        (3, 'Level 3 — Health centre'),
        (4, 'Level 4 — Sub-county hospital'),
        (5, 'Level 5 — County hospital'),
        (6, 'Level 6 — National referral hospital'),
    ]

    name             = models.CharField(max_length=200)
    level            = models.IntegerField(choices=LEVEL_CHOICES, default=3)
    sub_county       = models.CharField(max_length=100)
    county           = models.CharField(max_length=100, default='Kisii')
    address          = models.TextField(blank=True)
    phone            = models.CharField(max_length=20, blank=True)
    emergency_contact= models.CharField(max_length=20, blank=True)
    email            = models.EmailField(blank=True)
    operating_hours  = models.CharField(max_length=100, blank=True, default='Mon-Fri 8am-5pm')
    latitude         = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude        = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    is_active        = models.BooleanField(default=True)
    drug_status      = models.CharField(
                           max_length=20,
                           choices=[('available','Available'),('low','Low'),('out','Out of stock')],
                           default='available'
                       )
    created_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'Facilities'
        ordering = ['level', 'name']

    def __str__(self):
        return f"{self.name} (Level {self.level})"


class FacilityService(models.Model):
    facility = models.ForeignKey(Facility, on_delete=models.CASCADE, related_name='services')
    name     = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.facility.name} — {self.name}"


# ── USER PROFILE ──────────────────────────────────────────────────────────────

class Profile(models.Model):

    ROLE_CHOICES = [
        ('patient',    'Patient'),
        ('reception',  'Reception'),
        ('nurse',      'Nurse / Triage'),
        ('doctor',     'Doctor'),
        ('lab',        'Laboratory'),
        ('pharmacy',   'Pharmacy'),
        ('billing',    'Billing'),
        ('supervisor', 'Drug Supervisor'),
        ('supplier',   'Drug Supplier'),
        ('blood_bank', 'Blood Bank'),
        ('admin',      'System Admin'),
    ]

    GENDER_CHOICES = [
        ('male',   'Male'),
        ('female', 'Female'),
        ('other',  'Other'),
    ]

    BLOOD_GROUP_CHOICES = [
        ('A+','A+'),('A-','A-'),
        ('B+','B+'),('B-','B-'),
        ('AB+','AB+'),('AB-','AB-'),
        ('O+','O+'),('O-','O-'),
    ]

    user                = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role                = models.CharField(max_length=20, choices=ROLE_CHOICES, default='patient')
    facility            = models.ForeignKey(Facility, on_delete=models.SET_NULL, null=True, blank=True)
    phone_number        = models.CharField(max_length=20, blank=True)
    date_of_birth       = models.DateField(null=True, blank=True)
    gender              = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True)
    id_number           = models.CharField(max_length=30, blank=True)
    blood_group         = models.CharField(max_length=5, choices=BLOOD_GROUP_CHOICES, blank=True)
    known_allergies     = models.TextField(blank=True)
    chronic_conditions  = models.TextField(blank=True)
    current_medications = models.TextField(blank=True)
    payment_mode        = models.CharField(
                              max_length=20,
                              choices=[('cash','Cash'),('nhif','NHIF'),('insurance','Insurance'),('free','Free')],
                              default='cash'
                          )
    firebase_token      = models.CharField(max_length=255, blank=True)
    created_at          = models.DateTimeField(auto_now_add=True)

    @property
    def age(self):
        if self.date_of_birth:
            today = timezone.now().date()
            dob   = self.date_of_birth
            return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        return None

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.role})"


# ── VISIT ─────────────────────────────────────────────────────────────────────

class Visit(models.Model):

    STATUS_CHOICES = [
        ('waiting',     'Waiting'),
        ('in_progress', 'In progress'),
        ('complete',    'Complete'),
        ('cancelled',   'Cancelled'),
    ]

    VISIT_TYPE_CHOICES = [
        ('outpatient',   'Outpatient'),
        ('emergency',    'Emergency'),
        ('maternity',    'Maternity'),
        ('follow_up',    'Follow-up'),
        ('referral_in',  'Referral — incoming'),
        ('vaccination',  'Vaccination / MCH'),
        ('lab_only',     'Lab only'),
    ]

    PAYMENT_MODE_CHOICES = [
        ('cash',      'Cash'),
        ('nhif',      'NHIF'),
        ('insurance', 'Private insurance'),
        ('free',      'Free / waived'),
    ]

    patient              = models.ForeignKey(User, on_delete=models.PROTECT, related_name='visits')
    facility             = models.ForeignKey(Facility, on_delete=models.PROTECT)
    doctor               = models.ForeignKey(
                               User, on_delete=models.SET_NULL,
                               null=True, blank=True, related_name='doctor_visits'
                           )
    date                 = models.DateField(default=timezone.now)
    check_in_time        = models.TimeField(null=True, blank=True)
    check_out_time       = models.TimeField(null=True, blank=True)
    visit_type           = models.CharField(max_length=20, choices=VISIT_TYPE_CHOICES, default='outpatient')
    payment_mode         = models.CharField(max_length=20, choices=PAYMENT_MODE_CHOICES, default='cash')
    presenting_complaint = models.TextField(blank=True)
    reception_notes      = models.TextField(blank=True)
    status               = models.CharField(max_length=20, choices=STATUS_CHOICES, default='waiting')
    created_at           = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-check_in_time']

    def __str__(self):
        return f"Visit #{self.id} — {self.patient.get_full_name()} — {self.date}"


# ── SYMPTOM ENTRY (pre-arrival) ───────────────────────────────────────────────

class SymptomEntry(models.Model):

    SEVERITY_CHOICES = [
        ('mild',     'Mild'),
        ('moderate', 'Moderate'),
        ('severe',   'Severe'),
        ('critical', 'Critical'),
    ]

    DURATION_UNIT_CHOICES = [
        ('hours',  'Hours'),
        ('days',   'Days'),
        ('weeks',  'Weeks'),
        ('months', 'Months'),
    ]

    patient             = models.ForeignKey(User, on_delete=models.CASCADE, related_name='symptom_entries')
    visit               = models.OneToOneField(Visit, on_delete=models.SET_NULL, null=True, blank=True, related_name='symptom_entry')
    facility            = models.ForeignKey(Facility, on_delete=models.CASCADE)
    visit_date          = models.DateField()
    body_part           = models.CharField(max_length=50)
    severity            = models.CharField(max_length=10, choices=SEVERITY_CHOICES)
    symptoms            = models.TextField()
    duration_value      = models.PositiveIntegerField()
    duration_unit       = models.CharField(max_length=10, choices=DURATION_UNIT_CHOICES, default='days')
    temperature         = models.CharField(max_length=10, blank=True)
    current_medications = models.TextField(blank=True)
    known_allergies     = models.TextField(blank=True)
    extra_notes         = models.TextField(blank=True)
    created_at          = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.patient.get_full_name()} — {self.body_part} — {self.visit_date}"


# ── VITALS (triage) ───────────────────────────────────────────────────────────

class Vitals(models.Model):

    PRIORITY_CHOICES = [
        ('high',   'High'),
        ('medium', 'Medium'),
        ('low',    'Low'),
    ]

    visit              = models.OneToOneField(Visit, on_delete=models.CASCADE, related_name='vitals')
    blood_pressure     = models.CharField(max_length=10, blank=True)
    temperature        = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    pulse              = models.PositiveIntegerField(null=True, blank=True)
    oxygen_saturation  = models.PositiveIntegerField(null=True, blank=True)
    weight             = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    respiratory_rate   = models.PositiveIntegerField(null=True, blank=True)
    blood_sugar        = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    pain_score         = models.PositiveIntegerField(null=True, blank=True)
    priority           = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    nurse_notes        = models.TextField(blank=True)
    recorded_by        = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='recorded_vitals')
    recorded_at        = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'Vitals'

    def __str__(self):
        return f"Vitals — Visit #{self.visit.id} — {self.priority} priority"


# ── CONSULTATION ──────────────────────────────────────────────────────────────

class Consultation(models.Model):

    visit            = models.OneToOneField(Visit, on_delete=models.CASCADE, related_name='consultation')
    doctor           = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='consultations')
    clinical_findings= models.TextField()
    diagnosis        = models.CharField(max_length=300)
    icd_code         = models.CharField(max_length=20, blank=True)
    treatment_plan   = models.TextField()
    doctor_notes     = models.TextField(blank=True)
    followup_date    = models.DateField(null=True, blank=True)
    followup_notes   = models.CharField(max_length=300, blank=True)
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Consultation — {self.diagnosis} — Visit #{self.visit.id}"


class OutbreakAlert(models.Model):

    county          = models.CharField(max_length=100, blank=True)
    sub_county      = models.CharField(max_length=100, blank=True)
    diagnosis       = models.CharField(max_length=300)
    message         = models.TextField(blank=True)
    next_steps      = models.TextField(blank=True)
    case_count      = models.PositiveIntegerField(default=0)
    facility_count  = models.PositiveIntegerField(default=0)
    affected_facilities = models.ManyToManyField(Facility, blank=True, related_name='outbreak_alerts')
    resolved        = models.BooleanField(default=False)
    start_date      = models.DateField(null=True, blank=True)
    last_detected_at = models.DateTimeField(null=True, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        region = self.sub_county or self.county or 'Region'
        return f"Outbreak alert — {self.diagnosis} — {region}"


# ── PRESCRIPTION ──────────────────────────────────────────────────────────────

class Prescription(models.Model):

    consultation       = models.ForeignKey(Consultation, on_delete=models.CASCADE, related_name='prescriptions')
    visit              = models.ForeignKey(Visit, on_delete=models.CASCADE, related_name='prescriptions')
    drug_name          = models.CharField(max_length=200)
    dosage             = models.CharField(max_length=50)
    frequency          = models.CharField(max_length=100)
    duration           = models.CharField(max_length=50)
    quantity_to_dispense = models.PositiveIntegerField(default=1)
    quantity_dispensed = models.PositiveIntegerField(default=0)
    unit_price         = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    dispensed          = models.BooleanField(default=False)
    dispensed_at       = models.DateTimeField(null=True, blank=True)
    dispensed_by       = models.ForeignKey(
                             User, on_delete=models.SET_NULL,
                             null=True, blank=True, related_name='dispensed_prescriptions'
                         )

    @property
    def line_total(self):
        return self.unit_price * self.quantity_dispensed

    def __str__(self):
        return f"{self.drug_name} {self.dosage} — Visit #{self.visit.id}"


# ── LAB RESULT ────────────────────────────────────────────────────────────────

class LabResult(models.Model):

    STATUS_CHOICES = [
        ('pending',  'Pending'),
        ('ready',    'Ready'),
        ('abnormal', 'Abnormal'),
        ('critical', 'Critical'),
    ]

    URGENCY_CHOICES = [
        ('routine', 'Routine'),
        ('urgent',  'Urgent'),
        ('stat',    'STAT'),
    ]

    visit         = models.ForeignKey(Visit, on_delete=models.CASCADE, related_name='lab_results')
    test_name     = models.CharField(max_length=200)
    urgency       = models.CharField(max_length=10, choices=URGENCY_CHOICES, default='routine')
    notes         = models.TextField(blank=True)
    result_value  = models.CharField(max_length=100, blank=True)
    unit          = models.CharField(max_length=30, blank=True)
    normal_range  = models.CharField(max_length=100, blank=True)
    lab_notes     = models.TextField(blank=True)
    status        = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    cost          = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    ordered_by    = models.ForeignKey(
                        User, on_delete=models.SET_NULL,
                        null=True, related_name='ordered_lab_tests'
                    )
    date_ordered  = models.DateTimeField(auto_now_add=True)
    date_resulted = models.DateTimeField(null=True, blank=True)
    resulted_by   = models.ForeignKey(
                        User, on_delete=models.SET_NULL,
                        null=True, blank=True, related_name='resulted_lab_tests'
                    )

    def __str__(self):
        return f"{self.test_name} — {self.status} — Visit #{self.visit.id}"


# ── DRUG STOCK ────────────────────────────────────────────────────────────────

class DrugStock(models.Model):

    STATUS_CHOICES = [
        ('available', 'Available'),
        ('low',       'Low stock'),
        ('out',       'Out of stock'),
    ]

    facility              = models.ForeignKey(Facility, on_delete=models.CASCADE, related_name='drug_stock')
    drug_name             = models.CharField(max_length=200)
    category              = models.CharField(max_length=50, blank=True)
    quantity_delivered    = models.PositiveIntegerField(default=0)
    quantity_dispensed    = models.PositiveIntegerField(default=0)
    unit                  = models.CharField(max_length=20, default='tablets')
    supplier              = models.CharField(max_length=200, blank=True)
    batch_number          = models.CharField(max_length=50, blank=True)
    expiry_date           = models.DateField(null=True, blank=True)
    low_stock_threshold   = models.PositiveIntegerField(default=50)
    status                = models.CharField(max_length=10, choices=STATUS_CHOICES, default='available')
    last_updated          = models.DateTimeField(auto_now=True)
    last_delivery_date    = models.DateField(null=True, blank=True)
    delivery_notes        = models.TextField(blank=True)

    @property
    def quantity_remaining(self):
        return max(self.quantity_delivered - self.quantity_dispensed, 0)

    @property
    def days_remaining(self):
        """Estimate days of stock left based on average daily consumption."""
        from django.db.models import Avg
        avg = StockDispenseLog.objects.filter(
            drug_stock=self
        ).values('date').annotate(
            daily=models.Sum('quantity_dispensed')
        ).aggregate(avg=Avg('daily'))['avg']
        if avg and avg > 0:
            return int(self.quantity_remaining / avg)
        return None

    def update_status(self):
        remaining = self.quantity_remaining
        if remaining <= 0:
            self.status = 'out'
        elif remaining <= self.low_stock_threshold:
            self.status = 'low'
        else:
            self.status = 'available'
        self.save(update_fields=['status'])

    class Meta:
        unique_together = ('facility', 'drug_name', 'batch_number')
        ordering = ['drug_name']

    def __str__(self):
        return f"{self.drug_name} — {self.facility.name} — {self.quantity_remaining} {self.unit}"


class StockDelivery(models.Model):
    """Records each delivery of drugs to a facility."""
    drug_stock   = models.ForeignKey(DrugStock, on_delete=models.CASCADE, related_name='deliveries')
    drug_name    = models.CharField(max_length=200)
    facility     = models.ForeignKey(Facility, on_delete=models.CASCADE)
    quantity     = models.PositiveIntegerField()
    unit         = models.CharField(max_length=20, default='tablets')
    supplier     = models.CharField(max_length=200, blank=True)
    date         = models.DateField(default=timezone.now)
    batch_number = models.CharField(max_length=50, blank=True)
    expiry_date  = models.DateField(null=True, blank=True)
    logged_by    = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    notes        = models.TextField(blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.drug_name} — {self.quantity} {self.unit} — {self.date}"


class StockDispenseLog(models.Model):
    """Logs each individual drug dispense for consumption tracking."""
    drug_stock         = models.ForeignKey(DrugStock, on_delete=models.CASCADE, related_name='dispense_logs')
    prescription       = models.ForeignKey(Prescription, on_delete=models.CASCADE)
    quantity_dispensed = models.PositiveIntegerField()
    date               = models.DateField(default=timezone.now)
    dispensed_by       = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"{self.drug_stock.drug_name} — {self.quantity_dispensed} dispensed — {self.date}"


# ── DRONE DELIVERY ───────────────────────────────────────────────────────────

class Drone(models.Model):
    STATUS_CHOICES = [
        ('ready',      'Ready'),
        ('in_transit', 'In transit'),
        ('charging',   'Charging'),
        ('maintenance','Maintenance'),
    ]

    name               = models.CharField(max_length=150)
    identifier         = models.CharField(max_length=100, blank=True)
    facility           = models.ForeignKey(Facility, on_delete=models.SET_NULL, null=True, blank=True, related_name='drones')
    status             = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ready')
    current_latitude   = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    current_longitude  = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    last_updated       = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} — {self.identifier or 'unassigned'}"


class DroneDelivery(models.Model):
    PACKAGE_TYPE_CHOICES = [
        ('drug',      'Drug shipment'),
        ('blood',     'Blood delivery'),
        ('vaccine',   'Vaccines'),
        ('supplies',  'Medical supplies'),
    ]

    STATUS_CHOICES = [
        ('scheduled',  'Scheduled'),
        ('in_transit', 'In transit'),
        ('delayed',    'Delayed'),
        ('delivered',  'Delivered'),
        ('cancelled',  'Cancelled'),
    ]

    drone                 = models.ForeignKey(Drone, on_delete=models.SET_NULL, null=True, blank=True, related_name='deliveries')
    package_type          = models.CharField(max_length=20, choices=PACKAGE_TYPE_CHOICES, default='drug')
    item_name             = models.CharField(max_length=200)
    description           = models.TextField(blank=True)
    quantity              = models.PositiveIntegerField(default=1)
    unit                  = models.CharField(max_length=20, default='units')
    blood_group           = models.CharField(max_length=5, blank=True)
    origin_facility       = models.ForeignKey(Facility, on_delete=models.PROTECT, related_name='drone_origin_deliveries')
    destination_facility  = models.ForeignKey(Facility, on_delete=models.SET_NULL, null=True, blank=True, related_name='drone_destination_deliveries')
    destination_address   = models.TextField(blank=True)
    destination_latitude  = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    destination_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    requested_by          = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='requested_drone_deliveries')
    requested_at          = models.DateTimeField(auto_now_add=True)
    dispatched_at         = models.DateTimeField(null=True, blank=True)
    expected_arrival      = models.DateTimeField(null=True, blank=True)
    delivered_at          = models.DateTimeField(null=True, blank=True)
    current_status_notes  = models.TextField(blank=True)
    current_latitude      = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    current_longitude     = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    status                = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    updated_at            = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-requested_at']

    def __str__(self):
        return f"{self.get_package_type_display()} — {self.item_name} — {self.status}"

    @property
    def tracking_coordinates(self):
        if self.current_latitude and self.current_longitude:
            return {'lat': float(self.current_latitude), 'lng': float(self.current_longitude)}
        return None

    @property
    def is_blood_delivery(self):
        return self.package_type == 'blood'


# ── DRUG SHORTAGE ALERT (AI prediction) ────────────────────────────────────────

class DrugShortageAlert(models.Model):

    SEVERITY_CHOICES = [
        ('warning',  'Warning'),
        ('critical', 'Critical'),
    ]

    facility                    = models.ForeignKey(Facility, on_delete=models.CASCADE, related_name='shortage_alerts')
    drug_stock                  = models.ForeignKey(DrugStock, on_delete=models.CASCADE, related_name='shortage_alerts')
    days_until_runout           = models.PositiveIntegerField()
    estimated_daily_consumption = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    severity                    = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='warning')
    resolved                    = models.BooleanField(default=False)
    predicted_at                = models.DateTimeField(auto_now_add=True)
    last_predicted_at           = models.DateTimeField(auto_now=True)
    resolved_at                 = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-predicted_at']
        unique_together = ('facility', 'drug_stock')

    def __str__(self):
        return f"Shortage alert — {self.drug_stock.drug_name} at {self.facility.name} — {self.days_until_runout}d"


# ── REFERRAL ──────────────────────────────────────────────────────────────────

class Referral(models.Model):

    STATUS_CHOICES = [
        ('pending',  'Pending'),
        ('received', 'Received'),
        ('completed','Completed'),
        ('cancelled','Cancelled'),
    ]

    URGENCY_CHOICES = [
        ('routine',   'Routine'),
        ('urgent',    'Urgent'),
        ('emergency', 'Emergency'),
    ]

    patient              = models.ForeignKey(User, on_delete=models.PROTECT, related_name='referrals')
    visit                = models.OneToOneField(Visit, on_delete=models.SET_NULL, null=True, blank=True, related_name='referral')
    from_facility        = models.ForeignKey(Facility, on_delete=models.PROTECT, related_name='referrals_sent')
    referred_to          = models.ForeignKey(Facility, on_delete=models.PROTECT, related_name='referrals_received')
    referring_doctor     = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='referrals_made')
    urgency              = models.CharField(max_length=10, choices=URGENCY_CHOICES, default='routine')
    reason               = models.TextField()
    specialist_needed    = models.CharField(max_length=50, blank=True)
    transport_mode       = models.CharField(
                               max_length=20,
                               choices=[('own','Own means'),('ambulance','Ambulance'),('facility','Facility vehicle')],
                               default='own'
                           )
    accompanying_staff   = models.CharField(max_length=200, blank=True)
    referring_doctor_notes = models.TextField(blank=True)
    status               = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    date                 = models.DateTimeField(auto_now_add=True)
    received_at          = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"Referral #{self.id} — {self.patient.get_full_name()} → {self.referred_to.name}"


# ── EMERGENCY ALARM ───────────────────────────────────────────────────────────

class EmergencyAlarm(models.Model):

    SEVERITY_CHOICES = [
        ('serious',  'Serious'),
        ('critical', 'Critical'),
    ]

    RESPONSE_TYPE_CHOICES = [
        ('home_visit', 'Home visit'),
        ('ambulance',  'Ambulance'),
        ('advice',     'Advice only'),
    ]

    patient              = models.ForeignKey(User, on_delete=models.CASCADE, related_name='emergency_alarms')
    facility             = models.ForeignKey(Facility, on_delete=models.CASCADE)
    condition_type       = models.CharField(max_length=30)
    severity             = models.CharField(max_length=10, choices=SEVERITY_CHOICES)
    description          = models.TextField()
    location_description = models.TextField()
    latitude             = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude            = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    patient_count        = models.CharField(max_length=5, default='1')
    conscious            = models.CharField(max_length=5, default='yes')
    response_type        = models.CharField(max_length=15, choices=RESPONSE_TYPE_CHOICES, default='home_visit')
    contact_number       = models.CharField(max_length=20)
    resolved             = models.BooleanField(default=False)
    resolved_at          = models.DateTimeField(null=True, blank=True)
    resolved_by          = models.ForeignKey(
                               User, on_delete=models.SET_NULL,
                               null=True, blank=True, related_name='resolved_alarms'
                           )
    created_at           = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def get_condition_type_display(self):
        labels = {
            'chest_pain':     'Chest pain / heart',
            'breathing':      'Difficulty breathing',
            'unconscious':    'Unconscious / unresponsive',
            'seizure':        'Seizure / convulsions',
            'stroke':         'Suspected stroke',
            'severe_pain':    'Severe pain',
            'bleeding':       'Heavy bleeding',
            'allergic':       'Severe allergic reaction',
            'labour':         'Labour / about to give birth',
            'pregnancy_comp': 'Pregnancy complication',
            'accident':       'Accident / trauma',
            'burn':           'Burns',
            'poisoning':      'Poisoning / overdose',
            'other':          'Other',
        }
        return labels.get(self.condition_type, self.condition_type)

    def get_response_type_display(self):
        labels = {
            'home_visit': 'Home visit',
            'ambulance':  'Ambulance',
            'advice':     'Advice only',
        }
        return labels.get(self.response_type, self.response_type)

    def __str__(self):
        return f"Alarm #{self.id} — {self.patient.get_full_name()} — {self.condition_type}"


# ── INVOICE / BILLING ─────────────────────────────────────────────────────────

class Invoice(models.Model):

    visit             = models.OneToOneField(Visit, on_delete=models.CASCADE, related_name='invoice')
    consultation_fee  = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    lab_fee           = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    pharmacy_fee      = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    other_fee         = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount          = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    paid              = models.BooleanField(default=False)
    paid_at           = models.DateTimeField(null=True, blank=True)
    created_at        = models.DateTimeField(auto_now_add=True)
    updated_at        = models.DateTimeField(auto_now=True)

    @property
    def subtotal(self):
        return self.consultation_fee + self.lab_fee + self.pharmacy_fee + self.other_fee

    @property
    def total_cost(self):
        return max(self.subtotal - self.discount, 0)

    def __str__(self):
        return f"Invoice #{self.id} — Visit #{self.visit.id} — KES {self.total_cost}"


# ── REMINDER ──────────────────────────────────────────────────────────────────

class Reminder(models.Model):

    patient          = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reminders')
    facility         = models.ForeignKey(Facility, on_delete=models.SET_NULL, null=True)
    appointment_type = models.CharField(max_length=100)
    date             = models.DateField()
    time             = models.TimeField(null=True, blank=True)
    notes            = models.TextField(blank=True)
    sms_sent         = models.BooleanField(default=False)
    created_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['date', 'time']

    def __str__(self):
        return f"Reminder — {self.patient.get_full_name()} — {self.appointment_type} — {self.date}"


# ── ACTIVITY LOG ──────────────────────────────────────────────────────────────

class ActivityLog(models.Model):

    facility  = models.ForeignKey(Facility, on_delete=models.CASCADE, related_name='activity_logs')
    user      = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    message   = models.CharField(max_length=300)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.timestamp:%H:%M} — {self.message}"


# ── DJANGO SIGNALS ────────────────────────────────────────────────────────────
# Automatically create a Profile whenever a new User is created

from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()