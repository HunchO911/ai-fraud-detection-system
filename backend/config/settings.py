"""
Django settings for the AI-Driven Real-Time Fraud Detection project.

Every secret or environment-specific value is read from environment variables
(a local `.env` file is loaded in development), so nothing sensitive lives in
source control.
"""

import os
from datetime import timedelta
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load backend/.env if it exists. In production the real environment is used.
load_dotenv(BASE_DIR / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    """Read a boolean environment variable ("1", "true", "yes", "on")."""
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    """Read a comma-separated environment variable into a clean list."""
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
DEBUG = env_bool("DJANGO_DEBUG", False)

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "insecure-development-key-do-not-use-in-production"
    else:
        raise ImproperlyConfigured("Set DJANGO_SECRET_KEY when DJANGO_DEBUG is off.")

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
# Render tells the app its own public hostname; allow it automatically.
_render_host = os.getenv("RENDER_EXTERNAL_HOSTNAME", "")
if _render_host:
    ALLOWED_HOSTS.append(_render_host)

# Addresses (with https://) allowed to submit forms to the Django admin. Needed when hosted.
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", "")
if _render_host:
    CSRF_TRUSTED_ORIGINS.append(f"https://{_render_host}")

# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",  # lets us revoke refresh tokens on logout
    "corsheaders",
    # Local apps
    "authentication",
    "transactions",
    "detection",
    "alerts",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",  # must sit above CommonMiddleware
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# WhiteNoise serves the admin's CSS/JS when hosted. It is optional locally: used only if installed.
try:
    import whitenoise  # noqa: F401
except ImportError:
    pass
else:
    MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ---------------------------------------------------------------------------
# Database (PostgreSQL)
# ---------------------------------------------------------------------------
# DB_ENGINE=sqlite uses a simple local file (db.sqlite3): no database server to install,
# good for trying the project out. Leave it unset (or "postgres") for PostgreSQL.
if os.getenv("DATABASE_URL"):
    # Hosting (e.g. Render) provides one address that holds every connection detail.
    from .dburl import parse_database_url

    DATABASES = {"default": parse_database_url(os.environ["DATABASE_URL"])}
elif os.getenv("DB_ENGINE", "postgres").lower() == "sqlite":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("POSTGRES_DB", "fraud_detection"),
            "USER": os.getenv("POSTGRES_USER", "postgres"),
            "PASSWORD": os.getenv("POSTGRES_PASSWORD", ""),
            "HOST": os.getenv("POSTGRES_HOST", "localhost"),
            "PORT": os.getenv("POSTGRES_PORT", "5432"),
            "CONN_MAX_AGE": 60,  # reuse connections instead of reconnecting per request
        }
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
# Our own User model (email login, roles). Must be set before the first migrate.
AUTH_USER_MODEL = "authentication.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# Django REST Framework + JWT
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    # Every endpoint requires a valid JWT unless a view explicitly opts out.
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"]
    + (["rest_framework.renderers.BrowsableAPIRenderer"] if DEBUG else []),
    "DEFAULT_PAGINATION_CLASS": "config.pagination.StandardPagination",
    "PAGE_SIZE": 25,
    # Brute-force protection: only views that declare `throttle_scope` are limited.
    "DEFAULT_THROTTLE_CLASSES": ("rest_framework.throttling.ScopedRateThrottle",),
    "DEFAULT_THROTTLE_RATES": {
        "login": "10/min",
        "register": "5/hour",
    },
}

SIMPLE_JWT = {
    # Short-lived access token + longer refresh token is the standard pattern.
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(os.getenv("JWT_ACCESS_MINUTES", "15"))),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=int(os.getenv("JWT_REFRESH_DAYS", "7"))),
    # Each refresh issues a new refresh token and blacklists the old one,
    # so a stolen refresh token stops working after its first reuse.
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# Origins allowed to call the API from a browser (the React dev servers).
CORS_ALLOWED_ORIGINS = env_list(
    "CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173"
)

# ---------------------------------------------------------------------------
# Fraud detection
# ---------------------------------------------------------------------------
FRAUD_DETECTION = {
    # Starting risk thresholds: a fraud probability at or above a value gets that
    # level. Administrators can change them later from the dashboard (Settings
    # page); the values are then stored in the database and these are only the
    # defaults. Tune "high" to the operating point you pick when evaluating the
    # trained model (precision vs recall).
    "RISK_THRESHOLDS": {"medium": 0.30, "high": 0.60, "critical": 0.85},
    # How much of a customer's past the model gets to see when scoring.
    "HISTORY_DAYS": 90,
    "HISTORY_MAX_ROWS": 1000,
    # Load the trained model in the background when `runserver` starts, so the
    # first transaction is not slow. Set FRAUD_WARMUP=false to turn it off.
    "WARMUP": env_bool("FRAUD_WARMUP", True),
}

# ---------------------------------------------------------------------------
# Alerts: email and SMS
# ---------------------------------------------------------------------------
# By default both channels only PRINT to the terminal, so nothing real is sent
# while you develop. Set the variables in .env to send for real.
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = os.getenv("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_TIMEOUT = 10  # seconds; a slow mail server must not hang the API
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "Fraud Alerts <alerts@example.com>")

SMS_BACKEND = os.getenv("SMS_BACKEND", "console")  # "console" or "termii"
TERMII_API_KEY = os.getenv("TERMII_API_KEY", "")
TERMII_SENDER_ID = os.getenv("TERMII_SENDER_ID", "")  # must be registered with Termii
TERMII_CHANNEL = os.getenv("TERMII_CHANNEL", "generic")  # "generic", "dnd" or "whatsapp"
TERMII_BASE_URL = os.getenv("TERMII_BASE_URL", "https://api.ng.termii.com")

# Where the React dashboard lives; used for the links inside alert emails.
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

# Send alerts from a background thread so the API answers right away even when
# the mail server or SMS provider is slow. Turn off (ALERTS_ASYNC=false) to send
# inside the request. For heavy traffic, move this to a task queue such as Celery.
ALERTS_ASYNC = env_bool("ALERTS_ASYNC", True)

# ---------------------------------------------------------------------------
# Internationalisation
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Lagos"
USE_I18N = True
USE_TZ = True  # store UTC in the database, convert on display

# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# ---------------------------------------------------------------------------
# Production hardening (only when DEBUG is off)
# ---------------------------------------------------------------------------
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    # The host's load balancer handles HTTPS and tells Django through this header.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "standard"},
    },
    "root": {"handlers": ["console"], "level": os.getenv("LOG_LEVEL", "INFO")},
}
