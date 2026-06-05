from django.contrib.auth import views as auth_views
from django.views.generic import RedirectView
from django.urls import path
from . import views

urlpatterns = [
    path('', views.home_redirect, name='home'),

    # ── LANDING PAGE ──────────────────────────────────────────────────────
    path('community-pulse/',
         views.community_pulse_view,
         name='community_pulse'),

    # ── AUTH ──────────────────────────────────────────────────────────────
    path('login/',
         views.login_view,
         name='login'),

    path('logout/',
         auth_views.LogoutView.as_view(next_page='/login/'),
         name='logout'),

    path('register/',
         views.register_view,
         name='register'),

    path('password-reset/',
         auth_views.PasswordResetView.as_view(
             template_name='registration/password_reset_form.html'
         ),
         name='password_reset'),

    path('password-reset/done/',
         auth_views.PasswordResetDoneView.as_view(
             template_name='registration/password_reset_done.html'
         ),
         name='password_reset_done'),

    path('password-reset/confirm/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(
             template_name='registration/password_reset_confirm.html'
         ),
         name='password_reset_confirm'),

    path('password-reset/complete/',
         auth_views.PasswordResetCompleteView.as_view(
             template_name='registration/password_reset_complete.html'
         ),
         name='password_reset_complete'),

    # After login, redirect to the correct dashboard based on user role
    path('redirect/',
         views.role_redirect_view,
         name='role_redirect'),


    # ── PATIENT ───────────────────────────────────────────────────────────
    path('patient/dashboard/',
         views.patient_dashboard,
         name='patient_dashboard'),

    path('patient/symptoms/',
         views.symptom_entry,
         name='patient_symptom_entry'),

    path('patient/visits/',
         views.visit_history,
         name='patient_visit_history'),

    path('patient/visits/<int:visit_id>/',
         views.visit_detail,
         name='patient_visit_detail'),

    path('patient/facilities/',
         views.facility_finder,
         name='patient_facility_finder'),

    path('patient/facility/change/',
         views.change_facility,
         name='patient_change_facility'),

    path('patient/emergency/',
         views.emergency_view,
         name='patient_emergency'),


    # ── RECEPTION ─────────────────────────────────────────────────────────
    path('reception/',
         views.reception_dashboard,
         name='reception_dashboard'),

    path('reception/register/',
         views.register_visit_view,
         name='reception_register_visit'),


    # ── NURSE ─────────────────────────────────────────────────────────────
    path('nurse/',
         views.nurse_dashboard,
         name='nurse_dashboard'),

    path('nurse/vitals/',
         views.vitals_entry,
         name='nurse_vitals_entry'),


    # ── DOCTOR ────────────────────────────────────────────────────────────
    path('doctor/',
         views.doctor_dashboard,
         name='doctor_dashboard'),

    path('doctor/consultation/<int:patient_id>/',
         views.consultation_view,
         name='doctor_consultation'),

    path('doctor/history/',
         views.patient_history,
         name='doctor_patient_history'),

    path('doctor/referral/',
         views.referral_form,
         name='doctor_referral_form'),


    # ── LABORATORY ────────────────────────────────────────────────────────
    path('lab/',
         views.lab_dashboard,
         name='lab_dashboard'),

    path('lab/results/',
         views.results_entry,
         name='lab_results_entry'),


    # ── PHARMACY ──────────────────────────────────────────────────────────
    path('pharmacy/',
         views.pharmacy_dashboard,
         name='pharmacy_dashboard'),

    path('pharmacy/dispense/',
         views.dispense_view,
         name='pharmacy_dispense'),


    # ── BILLING ───────────────────────────────────────────────────────────
    path('billing/',
         views.billing_dashboard,
         name='billing_dashboard'),

    path('billing/invoice/',
         views.invoice_view,
         name='billing_invoice'),


    # ── DRUG SUPERVISOR ───────────────────────────────────────────────────
    path('supervisor/',
         views.supervisor_dashboard,
         name='supervisor_dashboard'),

    path('supervisor/stock/entry/',
         views.stock_entry,
         name='supervisor_stock_entry'),

    path('supervisor/stock/report/',
         views.stock_report,
         name='supervisor_stock_report'),


    # ── ADMIN PANEL ───────────────────────────────────────────────────────
    path('admin-panel/',
         views.admin_dashboard,
         name='admin_panel_dashboard'),

    path('admin-panel/facilities/',
         views.manage_facilities,
         name='admin_panel_manage_facilities'),


    # ── INTERNAL APIS (called by JS fetch in templates) ───────────────────
    path('api/patients/search/',
         views.patient_search_api,
         name='patient_search_api'),

    path('api/facilities/',
         views.facilities_api,
         name='facilities_api'),

    path('api/facilities/nearby/',
         views.nearby_hospitals_api,
         name='nearby_hospitals_api'),

    path('api/stock/<int:facility_id>/',
         views.stock_api,
         name='stock_api'),

]