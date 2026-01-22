import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    from django.core.exceptions import ImproperlyConfigured
    raise ImproperlyConfigured("SECRET_KEY environment variable is required")

DEBUG = os.getenv("DEBUG") == "True"
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS").split(",") if os.getenv("ALLOWED_HOSTS") else ["localhost","127.0.0.1"]
INSTALLED_APPS = [
    "grappelli",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_celery_beat",
    "core",
    "bot",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

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

WSGI_APPLICATION = "config.wsgi.application"

db_host = os.getenv("DB_HOST") or os.getenv("DATABASE_HOST")
db_name = (
    os.getenv("DB_DATABASE")
    or os.getenv("DB_NAME")
    or os.getenv("DATABASE_NAME")
)
db_user = os.getenv("DB_USER") or os.getenv("DATABASE_USER")
db_password = os.getenv("DB_PASSWORD") or os.getenv("DATABASE_PASSWORD")
db_port = os.getenv("DB_PORT") or os.getenv("DATABASE_PORT")

def is_valid_db_value(value):
    if not value:
        return False
    value_stripped = value.strip()
    if not value_stripped or value_stripped == "://" or value_stripped.startswith("://"):
        return False
    return True

if db_host and db_name and db_user and is_valid_db_value(db_host) and is_valid_db_value(db_name) and is_valid_db_value(db_user):
    db_config = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": db_name,
        "USER": db_user,
        "HOST": db_host,
    }
    if db_password:
        db_config["PASSWORD"] = db_password
    if db_port:
        db_config["PORT"] = db_port
    DATABASES = {
        "default": db_config
    }
else:
    from django.core.exceptions import ImproperlyConfigured
    missing_vars = []
    if not db_host:
        missing_vars.append("DATABASE_HOST or DB_HOST")
    if not db_name:
        missing_vars.append("DATABASE_NAME, DB_NAME, or DB_DATABASE")
    if not db_user:
        missing_vars.append("DATABASE_USER or DB_USER")
    raise ImproperlyConfigured(
        f"Database configuration is incomplete. Missing required environment variables: {', '.join(missing_vars)}"
    )

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "uk"
TIME_ZONE = "Europe/Kyiv"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

STATICFILES_DIRS = [
    BASE_DIR / "static",
] if (BASE_DIR / "static").exists() else []

GRAPPELLI_ADMIN_TITLE = "SDA Morning Bot Admin"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

_redis_url = os.getenv("REDIS_URL")
if _redis_url:
    CELERY_BROKER_URL = _redis_url
    CELERY_RESULT_BACKEND = _redis_url
elif os.getenv("CELERY_BROKER_URL"):
    CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL")
    CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND") or CELERY_BROKER_URL
else:
    _h = os.getenv("REDIS_HOST")
    _p = os.getenv("REDIS_PORT")
    _d = os.getenv("REDIS_DB")
    if _h and _p and _d:
        _default = f"redis://{_h}:{_p}/{_d}"
        CELERY_BROKER_URL = _default
        CELERY_RESULT_BACKEND = _default
    else:
        from django.core.exceptions import ImproperlyConfigured
        raise ImproperlyConfigured(
            "Celery configuration is incomplete. Set REDIS_URL, CELERY_BROKER_URL, or REDIS_HOST, REDIS_PORT, REDIS_DB"
        )

CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE

from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    "send-inspirations-to-users": {
        "task": "bot.tasks.send_inspirations_to_users",
        "schedule": crontab(minute="*/5"),
    },
}

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

EGW_API_AUTH_TOKEN = os.getenv("EGW_API_AUTH_TOKEN")

