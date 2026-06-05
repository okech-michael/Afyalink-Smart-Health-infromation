# AfyaLink — Clinical & Logistics Platform

AfyaLink is a Django-based health facility operations and logistics platform. It provides role-based dashboards, patient-facing flows, clinical workflows, stock and supply management, and logistics features (including drone-based delivery tracking). The project is intended to support facility networks, suppliers, and blood banks.

Key capabilities

- Role-based dashboards: patient, reception, nurse, doctor, lab, pharmacy, billing, supervisor, supplier, blood bank, and admin.
- Clinical workflows: visit registration, triage, consultations, prescriptions, lab results, and billing.
- Stock management: drug stock tracking, deliveries, dispense logs and shortage alerts.
- Logistics: drone fleet and drone delivery requests (drug/blood/supplies) with tracking and assignment.
- Notifications: in-app messages and hooks for SMS/push (configurable integrations).
- Admin: Django admin integrations for all models.

What was added recently

- Drone delivery feature: `Drone` and `DroneDelivery` models, supplier/blood-bank dashboards, delivery request and tracking views, forms and templates, and admin registration.
- Registration updates: `supplier` and `blood_bank` staff roles included in registration and redirects.

Code structure (important files)

- `config/` — Django project settings and WSGI/ASGI entry points.
- `core/` — main app with models, forms, views, urls, admin, and migrations.
  - `core/models.py` — domain models (Facility, Profile, Visit, DrugStock, Drone, DroneDelivery, ...).
  - `core/forms.py` — forms including `DroneDeliveryForm`.
  - `core/views.py` — role dashboards and drone delivery views.
  - `core/urls.py` — routes for dashboards and APIs.
  - `core/admin.py` — admin registration for Drone and DroneDelivery.
- `templates/` — Jinja-style Django templates for each role and drone pages (`templates/drone/`, `templates/supplier/`, `templates/blood_bank/`).

Database & migrations

- The app uses Django ORM (designed for Python 3.11, Django 5.x). After model changes run:

```bash
python -m venv .venv
source .venv/Scripts/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
python manage.py migrate
```

- A migration was created for the drone delivery models: `core/migrations/0003_drone_alter_profile_role_dronedelivery_and_more.py`.

Environment & configuration

- Use environment variables for secrets and production settings. Copy `.env.example` to `.env` for local development and set values.
- Important env vars:
  - `DJANGO_SECRET_KEY`
  - `DJANGO_DEBUG` (set `False` in production)
  - `DATABASE_URL` (Postgres recommended for production)
  - `ALLOWED_HOSTS` / `DJANGO_ALLOWED_HOSTS`
  - Third-party keys (AfricasTalking, Firebase, etc.) as needed by your integrations

Running locally

```bash
python manage.py runserver
# Create a superuser to access the admin:
python manage.py createsuperuser
```

Deployment (Railway)

- The repository has been prepared for Railway: `Procfile`, `requirements.txt`, and `runtime.txt` are present. Settings read environment variables and support `DATABASE_URL`.
- Typical Railway steps:

1. Connect the repo in Railway and set environment variables.
2. Ensure `DATABASE_URL` points to a managed Postgres database.
3. On first deploy run `python manage.py migrate` and `python manage.py collectstatic --noinput` (Railway runs release commands or you can run them via the console).

Testing and checks

- Run Django checks:

```bash
python manage.py check
```

- Use automated tests (if added) with:

```bash
python manage.py test
```

Notes & next steps for your presentation

- The drone delivery feature includes models, forms, views and templates but may require wiring to a live telemetry source (drone GPS feed) for real-time tracking. For the demo you can manually update delivery coordinates via the delivery detail UI.
- If you want live maps, add a lightweight JS map (Leaflet/Mapbox) and expose `DroneDelivery.tracking_coordinates` in an API endpoint.
- To show a complete end-to-end flow for the presentation, create seed data for a supplier, a blood bank, a facility and one drone delivery request.

If you want, I can:

- add a simple management command to seed demo data,
- add an API endpoint returning JSON coordinates for deliveries,
- wire a small Leaflet map into `templates/drone/delivery_detail.html` for live demo.

-----

Updated on 2026-06-05.
