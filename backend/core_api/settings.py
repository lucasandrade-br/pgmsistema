"""
Django settings for core_api project.
"""

import os
from pathlib import Path
import environ

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Inicializa django-environ e lê o arquivo .env na raiz do backend
env = environ.Env(
    DEBUG=(bool, False),
)
environ.Env.read_env(BASE_DIR / ".env")

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env("SECRET_KEY")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env("DEBUG")

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

# URL pública do frontend (usada em e-mails e jobs)
FRONTEND_URL = env("FRONTEND_URL", default="http://localhost:5173")

# Segredo compartilhado para endpoints internos acionados pelo Cloud Scheduler
JOB_SECRET_KEY = env("JOB_SECRET_KEY", default="")


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Terceiros
    "rest_framework",
    "corsheaders",
    "django_filters",
    "storages",
    # Apps de domínio
    "core",
    "cadastros",
    "gestao",
]

# Modelo de usuário customizado (contém PIN de autorização nativamente)
AUTH_USER_MODEL = "core.CustomUser"

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "core_api.urls"

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

WSGI_APPLICATION = "core_api.wsgi.application"


# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

DATABASES = {
    'default': env.db("DATABASE_URL"),
    'legado': env.db("LEGADO_DATABASE_URL", default="sqlite:///dummy_legado.db")
}

# Django REST Framework
REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",  # necessário para upload de arquivos
        "rest_framework.parsers.FormParser",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
    ],
}

# SimpleJWT
from datetime import timedelta

SIMPLE_JWT = {
    # 1 dia para facilitar o ambiente de desenvolvimento
    "ACCESS_TOKEN_LIFETIME": timedelta(days=1),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": False,
    "ALGORITHM": "HS256",
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

# CORS
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[
    "http://localhost:5173",
    "http://localhost:3000",
])

# ── Criptografia de campos sensíveis (LGPD) ──────────────────────────────────
# FIELD_ENCRYPTION_KEY: chave Fernet (AES-128-CBC + HMAC). Gere com:
#   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# SEARCH_HASH_KEY: chave HMAC-SHA256 para hash de busca determinístico.
FIELD_ENCRYPTION_KEY: str = env("FIELD_ENCRYPTION_KEY", default="")
SEARCH_HASH_KEY:      str = env("SEARCH_HASH_KEY",      default="")


# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

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


# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = "pt-br"

TIME_ZONE = "America/Sao_Paulo"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = "static/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")

# Media files (user-uploaded content)
MEDIA_URL  = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ── Configurações de Produção (Cloud Run + GCS) ──────────────────────────────
if not DEBUG:
    # Segurança e Proxy (Cloud Run fica atrás do load balancer do Google)
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    USE_X_FORWARDED_HOST = True
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

    # Origins confiáveis para CSRF (domínios de produção separados por vírgula no .env)
    CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

    # Arquivos estáticos: WhiteNoise com compressão e hash de cache-busting
    STORAGES = {
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
        # Arquivos de mídia (anexos): Google Cloud Storage
        # Requer: django-storages[google] google-auth google-cloud-storage
        # GS_DEFAULT_ACL = None → arquivos privados com URL assinada (correto para docs jurídicos)
        "default": {
            "BACKEND": "storages.backends.gcloud.GoogleCloudStorage",
        },
    }
    GS_BUCKET_NAME  = env("GS_BUCKET_NAME", default="")
    GS_DEFAULT_ACL  = None          # privado; use GS_QUERYSTRING_AUTH=True para URLs assinadas
    GS_QUERYSTRING_AUTH = True
    GS_EXPIRATION   = 3600          # URL assinada expira em 1 hora

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── Configurações de E-mail (SMTP) ───────────────────────────────────────────
EMAIL_BACKEND      = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST         = env('EMAIL_HOST',         default='smtp.gmail.com')
EMAIL_PORT         = env.int('EMAIL_PORT',     default=587)
EMAIL_USE_TLS      = env.bool('EMAIL_USE_TLS', default=True)
EMAIL_HOST_USER    = env('EMAIL_HOST_USER',    default='')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default=EMAIL_HOST_USER)
