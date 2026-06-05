import os
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured

# ── BASE ──────────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent.parent


def get_env_setting(name, default=None, required=False):
    value = os.environ.get(name, default)
    if required and not value:
        raise ImproperlyConfigured(f"The {name} environment variable is required.")
    return value


# ── SECURITY ──────────────────────────────────────────────────────────────────
# IMPORTANT: Supply a strong secret key via the DJANGO_SECRET_KEY environment variable.
# Generate one with:
#   python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

SECRET_KEY = get_env_setting('DJANGO_SECRET_KEY', 'replace-this-with-your-own-secret-key-before-running')

# Set DJANGO_DEBUG=False in production
DEBUG = os.environ.get('DJANGO_DEBUG', 'True').lower() in ('1', 'true', 'yes')

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1,.railway.app').split(',')
    if host.strip()
]


# ── INSTALLED APPS ────────────────────────────────────────────────────────────

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'core.apps.CoreConfig',
]


# ── MIDDLEWARE ────────────────────────────────────────────────────────────────

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


# ── URLS ──────────────────────────────────────────────────────────────────────

ROOT_URLCONF = 'config.urls'


# ── TEMPLATES ─────────────────────────────────────────────────────────────────

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            BASE_DIR / 'templates',  # project-level templates folder
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]


# ── WSGI ──────────────────────────────────────────────────────────────────────

WSGI_APPLICATION = 'config.wsgi.application'


# ── DATABASE ──────────────────────────────────────────────────────────────────
# SQLite is fine for development and the demo.
# Railway can use a DATABASE_URL environment variable for Postgres in production.

DATABASE_URL = os.environ.get('DATABASE_URL')

if DATABASE_URL:
    try:
        import dj_database_url

        DATABASES = {
            'default': dj_database_url.parse(DATABASE_URL, conn_max_age=600)
        }
    except ImportError:
        raise ImproperlyConfigured('dj-database-url is required when DATABASE_URL is set')
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# PostgreSQL example (uncomment and fill in for production):
# DATABASES = {
#     'default': {
#         'ENGINE':   'django.db.backends.postgresql',
#         'NAME':     'afyalink_db',
#         'USER':     'afyalink_user',
#         'PASSWORD': 'your_db_password',
#         'HOST':     'localhost',
#         'PORT':     '5432',
#     }
# }


# ── PASSWORD VALIDATION ───────────────────────────────────────────────────────

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# ── LOCALISATION ──────────────────────────────────────────────────────────────

LANGUAGE_CODE = 'en-us'
TIME_ZONE     = 'Africa/Nairobi'
USE_I18N      = True
USE_TZ        = True


# ── STATIC FILES ─────────────────────────────────────────────────────────────

STATIC_URL = '/static/'

STATICFILES_DIRS = [
    BASE_DIR / 'static',      # development static files (css, js, images)
]

STATIC_ROOT = BASE_DIR / 'staticfiles'  # collected for production with collectstatic
STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'


# ── MEDIA FILES ───────────────────────────────────────────────────────────────

MEDIA_URL  = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


# ── AUTH REDIRECTS ────────────────────────────────────────────────────────────

LOGIN_URL          = '/login/'
LOGIN_REDIRECT_URL = '/redirect/'    # role_redirect_view sends each user to correct dashboard
LOGOUT_REDIRECT_URL = '/login/'


# ── DEFAULT PRIMARY KEY ───────────────────────────────────────────────────────

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# ── MESSAGES ─────────────────────────────────────────────────────────────────
# Maps Django message levels to CSS classes used in base.html

from django.contrib.messages import constants as messages_constants

MESSAGE_TAGS = {
    messages_constants.DEBUG:   'debug',
    messages_constants.INFO:    'info',
    messages_constants.SUCCESS: 'success',
    messages_constants.WARNING: 'warning',
    messages_constants.ERROR:   'error',
}


# ── SESSION ───────────────────────────────────────────────────────────────────

SESSION_COOKIE_AGE     = 60 * 60 * 8   # 8 hours — log out after a full working shift
SESSION_EXPIRE_AT_BROWSER_CLOSE = False


# ── GOOGLE MAPS ───────────────────────────────────────────────────────────────
# Get your key at https://console.cloud.google.com
# Enable: Maps JavaScript API, Directions API

GOOGLE_MAPS_API_KEY = os.environ.get('GOOGLE_MAPS_API_KEY', 'AIzaSyCKaiYRZ8oWP7H3_QeTRrlK6cDMDNVCDog')


# ── AFRICA'S TALKING ─────────────────────────────────────────────────────────
# Get your key at https://africastalking.com
# Use 'sandbox' as username during development — no real SMS is sent

AFRICASTALKING_USERNAME = os.environ.get('AFRICASTALKING_USERNAME', 'sandbox')
AFRICASTALKING_API_KEY  = os.environ.get('AFRICASTALKING_API_KEY',  'your-africastalking-api-key-here')
FIREBASE_SERVER_KEY     = os.environ.get('FIREBASE_SERVER_KEY', '')


# ── EMAIL ─────────────────────────────────────────────────────────────────────
# Used for password reset emails.
# During development, emails are printed to the console.

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Switch to SMTP for production:
# EMAIL_BACKEND       = 'django.core.mail.backends.smtp.EmailBackend'
# EMAIL_HOST          = 'smtp.gmail.com'
# EMAIL_PORT          = 587
# EMAIL_USE_TLS       = True
# EMAIL_HOST_USER     = os.environ.get('EMAIL_HOST_USER', 'your_gmail@gmail.com')
# EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', 'your_gmail_app_password')
# DEFAULT_FROM_EMAIL  = 'AfyaLink <your_gmail@gmail.com>'