from pathlib import Path

import environ
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BASE_DIR.parent
env = environ.Env(
    DJANGO_DEBUG=(bool, False),
)
env.read_env(ROOT_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY", default="")
if not SECRET_KEY:
    raise ImproperlyConfigured(
        "Configura DJANGO_SECRET_KEY en el entorno o en el archivo .env."
    )

DEBUG = env("DJANGO_DEBUG")
MEDIA_UPLOADS_ENABLED = DEBUG
ALLOWED_HOSTS = env.list(
    "DJANGO_ALLOWED_HOSTS",
    default=["localhost", "127.0.0.1"] if DEBUG else [],
)
CORS_ALLOWED_ORIGINS = env.list(
    "DJANGO_CORS_ALLOWED_ORIGINS",
    default=(
        ["http://localhost:5173", "http://127.0.0.1:5173"]
        if DEBUG
        else []
    ),
)
CSRF_TRUSTED_ORIGINS = env.list(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    default=(
        ["http://localhost:5173", "http://127.0.0.1:5173"]
        if DEBUG
        else []
    ),
)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "whitenoise.runserver_nostatic",
    "rest_framework",
    "catalog",
    "orders",
    "accounts",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
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
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASE_URL = env("DATABASE_URL", default="")
if DATABASE_URL:
    DATABASES = {"default": env.db("DATABASE_URL")}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

configured_media_root = env("MEDIA_ROOT", default="")
MEDIA_ROOT = Path(configured_media_root) if configured_media_root else BASE_DIR / "media"
if configured_media_root and not MEDIA_ROOT.is_absolute():
    raise ImproperlyConfigured("MEDIA_ROOT debe ser una ruta absoluta.")

if not DEBUG:
    if not SECRET_KEY or len(SECRET_KEY) < 50 or SECRET_KEY.startswith("django-insecure-"):
        raise ImproperlyConfigured(
            "En producción, DJANGO_SECRET_KEY debe ser una clave aleatoria de al menos 50 caracteres."
        )
    if not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS:
        raise ImproperlyConfigured(
            "Configura DJANGO_ALLOWED_HOSTS con dominios explícitos del backend."
        )
    if not CORS_ALLOWED_ORIGINS or not CSRF_TRUSTED_ORIGINS:
        raise ImproperlyConfigured(
            "Configura DJANGO_CORS_ALLOWED_ORIGINS y DJANGO_CSRF_TRUSTED_ORIGINS."
        )
    if any(not origin.startswith("https://") for origin in CORS_ALLOWED_ORIGINS):
        raise ImproperlyConfigured(
            "Los orígenes CORS de producción deben usar HTTPS."
        )
    if any(not origin.startswith("https://") for origin in CSRF_TRUSTED_ORIGINS):
        raise ImproperlyConfigured(
            "Los orígenes CSRF de producción deben usar HTTPS."
        )
    if (
        not DATABASE_URL
        or DATABASES["default"]["ENGINE"] != "django.db.backends.postgresql"
    ):
        raise ImproperlyConfigured(
            "Configura DATABASE_URL con PostgreSQL para producción."
        )
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "es-cl"
TIME_ZONE = "America/Santiago"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = "media/"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        ),
    },
}
WHITENOISE_USE_FINDERS = env.bool("WHITENOISE_USE_FINDERS", default=DEBUG)
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CORS_ALLOW_CREDENTIALS = True
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SAMESITE = env("DJANGO_COOKIE_SAMESITE", default="Lax")
CSRF_COOKIE_SAMESITE = SESSION_COOKIE_SAMESITE
SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=not DEBUG)
SECURE_HSTS_SECONDS = env.int("DJANGO_SECURE_HSTS_SECONDS", default=0)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool(
    "DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS",
    default=False,
)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
if env.bool("DJANGO_TRUST_X_FORWARDED_PROTO", default=False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "120/hour",
        "customer_register": "5/hour",
        "customer_login": "10/hour",
        "customer_verify": "5/hour",
        "customer_password_reset": "5/hour",
    },
}

WHATSAPP_BUSINESS_NUMBER = env("WHATSAPP_BUSINESS_NUMBER", default="")
STORE_NAME = env("STORE_NAME", default="Siempre Natural")
STORE_TAGLINE = env("STORE_TAGLINE", default="Alimentación consciente, a tu medida")
STORE_PICKUP_ADDRESS = env("STORE_PICKUP_ADDRESS", default="")
STORE_BUSINESS_HOURS = env("STORE_BUSINESS_HOURS", default="")
STORE_CONTACT_EMAIL = env("STORE_CONTACT_EMAIL", default="")

EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = env(
    "DEFAULT_FROM_EMAIL",
    default=EMAIL_HOST_USER or STORE_CONTACT_EMAIL,
)
EMAIL_TIMEOUT = env.int("EMAIL_TIMEOUT", default=10)
FRONTEND_BASE_URL = env("FRONTEND_BASE_URL", default="http://localhost:5173")
