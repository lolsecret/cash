# ruff: noqa: ERA001, E501
"""Base settings to build other settings files upon."""
import base64
import datetime
from pathlib import Path
import os
import environ

BASE_DIR = Path(__file__).resolve(strict=True).parent.parent.parent
# apps/
APPS_DIR = BASE_DIR
env = environ.Env()\

SECRET_KEY = env(
    "DJANGO_SECRET_KEY",
    default="Mv2CbZTMEQI4jZqIxdnuYXYGhUqPkr2Tv3eN9WkzCvuJu4ts6IzaLWlwFCfpe0lE",
)
ENVIRONMENT = os.getenv("ENVIRONMENT", "local")
# READ_DOT_ENV_FILE = env.bool("DJANGO_READ_DOT_ENV_FILE", default=False)
# if READ_DOT_ENV_FILE:
#     # OS environment variables take precedence over variables from .env
#     env.read_env(str(BASE_DIR / ".env"))
env_files = [
    BASE_DIR / f".envs/.{ENVIRONMENT}/.django",
    BASE_DIR / f".envs/.{ENVIRONMENT}/.postgres",
]

for env_file in env_files:
    if env_file.exists():
        environ.Env.read_env(env_file)
# GENERAL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#debug
DEBUG = env.bool("DJANGO_DEBUG", False)
# Local time zone. Choices are
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# though not all of them may be available with every OS.
# In Windows, this must be set to your system time zone.
TIME_ZONE = "Asia/Almaty"
# https://docs.djangoproject.com/en/dev/ref/settings/#language-code
LANGUAGE_CODE = "ru-RU"
# https://docs.djangoproject.com/en/dev/ref/settings/#languages
# from django.utils.translation import gettext_lazy as _
# LANGUAGES = [
#     ('en', _('English')),
#     ('fr-fr', _('French')),
#     ('pt-br', _('Portuguese')),
# ]
# https://docs.djangoproject.com/en/dev/ref/settings/#site-id
SITE_ID = 1
# https://docs.djangoproject.com/en/dev/ref/settings/#use-i18n
USE_I18N = True
# https://docs.djangoproject.com/en/dev/ref/settings/#use-tz
USE_TZ = True
# https://docs.djangoproject.com/en/dev/ref/settings/#locale-paths
LOCALE_PATHS = [str(BASE_DIR / "locale")]

# DATABASES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#databases

DB_LOGS_NAME = os.getenv("DB_LOGS_NAME", "logger")

DATABASE_ROUTERS = ['apps.logger.db_router.LogDBRouter']
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "microcash"),
        "USER": os.getenv("POSTGRES_USER", "microcash"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", "microcash"),
        "HOST": os.getenv("POSTGRES_HOST", "localhost"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
    },
    "logger": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": DB_LOGS_NAME,
        "USER": os.getenv("DB_LOGS_USER", "logger_user"),
        "PASSWORD": os.getenv("DB_LOGS_PASSWORD", "logger_password"),
        "HOST": os.getenv("DB_LOGS_HOST", "localhost"),
        "PORT": os.getenv("DB_LOGS_PORT", "5432"),
    }
}



CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": os.getenv("CACHE_REDIS", "redis://127.0.0.1:6379/1"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        }
    }
}

# https://docs.djangoproject.com/en/stable/ref/settings/#std:setting-DEFAULT_AUTO_FIELD
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# URLS
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#root-urlconf
ROOT_URLCONF = "config.urls"
# https://docs.djangoproject.com/en/dev/ref/settings/#wsgi-application
WSGI_APPLICATION = "config.wsgi.application"

# APPS
# ------------------------------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.sites",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize", # Handy template tags
    "django.contrib.admin",
    "django.forms",
]
THIRD_PARTY_APPS = [
    "crispy_forms",
    "crispy_bootstrap5",
    # "allauth",
    # "allauth.account",
    # "allauth.socialaccount",
    "django_celery_beat",
    "rest_framework",
    'rest_framework_simplejwt',
    'rest_framework.authtoken',
    "corsheaders",
    "phonenumber_field",  # noqa
    "tinymce",
    "drf_yasg",
    "django_json_widget",
    "adminsortable2",
    "sequences.apps.SequencesConfig",
]

LOCAL_APPS = [
    "apps.accounts",
    "apps.people",
    "apps.core",
    "apps.flow",
    "apps.credits",
    "apps.notifications",
    "apps.references",
    "apps.logger",
    "apps.users",

]
# https://docs.djangoproject.com/en/dev/ref/settings/#installed-apps
INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# MIGRATIONS
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#migration-modules
MIGRATION_MODULES = {"sites": "apps.contrib.sites.migrations"}

# AUTHENTICATION
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#authentication-backends
AUTHENTICATION_BACKENDS = ['apps.users.authenticate.CustomUserModelBackend']
# https://docs.djangoproject.com/en/dev/ref/settings/#auth-user-model
AUTH_USER_MODEL = "users.User"
# https://docs.djangoproject.com/en/dev/ref/settings/#login-redirect-url
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = '/admin/'



# PASSWORDS
# ------------------------------------------------------------------------------
# http
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'log_request_id.middleware.RequestIDMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',

    # "allauth.account.middleware.AccountMiddleware",
]

# STATIC
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#static-root
STATIC_ROOT = str(BASE_DIR / "staticfiles")
# https://docs.djangoproject.com/en/dev/ref/settings/#static-url
STATIC_URL = "/api/static/"
# https://docs.djangoproject.com/en/dev/ref/contrib/staticfiles/#std:setting-STATICFILES_DIRS
STATICFILES_DIRS = [str(APPS_DIR / "static")]
# https://docs.djangoproject.com/en/dev/ref/contrib/staticfiles/#staticfiles-finders
STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
]

# MEDIA
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#media-root
MEDIA_URL = os.getenv("MEDIA_URL", "/api/media/")
MEDIA_ROOT = os.getenv("MEDIA_ROOT", os.path.join(BASE_DIR, "media"))

# TEMPLATES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#templates
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'apps/templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',

                'apps.core.context_processors.get_product_list',
                # 'apps.core.context_processors.get_dashboard_data',
            ],
        },
    },
]
DATALOADER_URL = os.getenv("DATALOADER_URL", None)
OTP_LENGTH = os.getenv("OTP_LENGTH", 6)
OTP_VALIDITY_PERIOD = os.getenv("OTP_VALIDITY_PERIOD", 30)  # In minutes
OTP_MAX_FAILED_VERIFICATION_AMOUNTS = os.getenv("OTP_MAX_FAILED_VERIFICATION_AMOUNTS", 3)


# https://docs.djangoproject.com/en/dev/ref/settings/#form-renderer
FORM_RENDERER = "django.forms.renderers.TemplatesSetting"

# http://django-crispy-forms.readthedocs.io/en/latest/install.html#template-packs
CRISPY_TEMPLATE_PACK = "bootstrap5"
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"

# FIXTURES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#fixture-dirs
FIXTURE_DIRS = (str(APPS_DIR / "fixtures"),)

# SECURITY
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#session-cookie-httponly
SESSION_COOKIE_HTTPONLY = True
# https://docs.djangoproject.com/en/dev/ref/settings/#csrf-cookie-httponly
CSRF_COOKIE_HTTPONLY = True
# https://docs.djangoproject.com/en/dev/ref/settings/#x-frame-options
X_FRAME_OPTIONS = "DENY"

HOTP_KEY = base64.b32encode(SECRET_KEY.encode("utf-8"))
SMS_ENABLE = os.getenv("SMS_ENABLE", True)
SMS_BACKEND = os.getenv("SMS_BACKEND", "apps.notifications.backend.SmsTraffic")
SMS_LOGIN = os.getenv("SMS_LOGIN", "microcash")
SMS_PASSWORD = os.getenv("SMS_PASSWORD", "Microcash2024")
SMS_SENDER = os.getenv("SMS_SENDER", "")


# EMAIL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#email-backend
EMAIL_BACKEND = env(
    "DJANGO_EMAIL_BACKEND",
    default="django.core.mail.backends.smtp.EmailBackend",
)
# https://docs.djangoproject.com/en/dev/ref/settings/#email-timeout
EMAIL_HOST = env("EMAIL_HOST", default="smtp.mail.ru")
EMAIL_PORT = env.int("EMAIL_PORT", default=465)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=False)
EMAIL_USE_SSL = env.bool("EMAIL_USE_SSL", default=True)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="info@microcash.kz")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="TTRVxZ4PvxfZwauMS4xD")
EMAIL_TIMEOUT = env.int("EMAIL_TIMEOUT", default=5)
# ADMIN
# ------------------------------------------------------------------------------
# Django Admin URL.
# https://docs.djangoproject.com/en/dev/ref/settings/#admins
ADMINS = [("""tamerlan""", "lucallonso@gmail.com")]
# https://docs.djangoproject.com/en/dev/ref/settings/#managers
MANAGERS = ADMINS
# https://cookiecutter-django.readthedocs.io/en/latest/settings.html#other-environment-settings
# Force the `admin` sign in process to go through the `django-allauth` workflow

# LOGGING
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#logging
# See https://docs.djangoproject.com/en/dev/topics/logging for
# more details on how to customize your logging configuration.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s",
        },
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {"level": "INFO", "handlers": ["console"]},
}

# Celery
# ------------------------------------------------------------------------------
if USE_TZ:
    # https://docs.celeryq.dev/en/stable/userguide/configuration.html#std:setting-timezone
    CELERY_TIMEZONE = TIME_ZONE
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#std:setting-broker_url
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/3")
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#std:setting-result_backend
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/3")
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#result-extended
CELERY_RESULT_EXTENDED = True
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#result-backend-always-retry
# https://github.com/celery/celery/pull/6122
CELERY_RESULT_BACKEND_ALWAYS_RETRY = True
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#result-backend-max-retries
CELERY_RESULT_BACKEND_MAX_RETRIES = 10
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#std:setting-accept_content
CELERY_ACCEPT_CONTENT = ["json"]
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#std:setting-task_serializer
CELERY_TASK_SERIALIZER = "json"
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#std:setting-result_serializer
CELERY_RESULT_SERIALIZER = "json"
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#task-time-limit
# TODO: set to whatever value is adequate in your circumstances
CELERY_TASK_TIME_LIMIT = 5 * 60
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#task-soft-time-limit
# TODO: set to whatever value is adequate in your circumstances
CELERY_TASK_SOFT_TIME_LIMIT = 60
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#beat-scheduler
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#worker-send-task-events
CELERY_WORKER_SEND_TASK_EVENTS = True
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#std-setting-task_send_sent_event
CELERY_TASK_SEND_SENT_EVENT = True
# django-allauth
# ------------------------------------------------------------------------------
ACCOUNT_ALLOW_REGISTRATION = env.bool("DJANGO_ACCOUNT_ALLOW_REGISTRATION", True)
# https://docs.allauth.org/en/latest/account/configuration.html
# ACCOUNT_AUTHENTICATION_METHOD = "email"
# https://docs.allauth.org/en/latest/account/configuration.html
# ACCOUNT_EMAIL_REQUIRED = True
# https://docs.allauth.org/en/latest/account/configuration.html
# ACCOUNT_USERNAME_REQUIRED = False
# https://docs.allauth.org/en/latest/account/configuration.html
# ACCOUNT_USER_MODEL_USERNAME_FIELD = None
# https://docs.allauth.org/en/latest/account/configuration.html
# ACCOUNT_EMAIL_VERIFICATION = "mandatory"
# https://docs.allauth.org/en/latest/account/configuration.html
# ACCOUNT_ADAPTER = "apps.users.adapters.AccountAdapter"
# https://docs.allauth.org/en/latest/account/forms.html
# ACCOUNT_FORMS = {"signup": "apps.users.forms.UserSignupForm"}
# https://docs.allauth.org/en/latest/socialaccount/configuration.html
# SOCIALACCOUNT_ADAPTER = "apps.users.adapters.SocialAccountAdapter"
# https://docs.allauth.org/en/latest/socialaccount/configuration.html
# SOCIALACCOUNT_FORMS = {"signup": "apps.users.forms.UserSocialSignupForm"}

# django-rest-framework
# -------------------------------------------------------------------------------
# django-rest-framework - https://www.django-rest-framework.org/api-guide/settings/
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        # 'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.BasicAuthentication',
        'apps.accounts.authentication.CustomJSONWebTokenAuthentication',
    ),

}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': datetime.timedelta(days=1),
    'REFRESH_TOKEN_LIFETIME': datetime.timedelta(days=7),
}

# django-cors-headers - https://github.com/adamchainz/django-cors-headers#setup
CORS_URLS_REGEX = r"^/api/.*$"
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
CORS_ALLOWED_ORIGINS = [
    'https://dev.microcash.kz',
    'http://dev.microcash.kz',
    'http://localhost:5173',
]
CSRF_TRUSTED_ORIGINS = [
    'https://dev.microcash.kz',
    'http://dev.microcash.kz',
]

CORS_ALLOW_CREDENTIALS = True

CORS_ALLOW_HEADERS = [
    'authorization',
    'content-type',
    'x-csrftoken',
]

CORS_ALLOW_METHODS = [
    'GET',
    'POST',
    'PUT',
    'PATCH',
    'DELETE',
    'OPTIONS',
]
# By Default swagger ui is available only to admin user(s). You can change permission classes to change that
# See more configuration options at https://drf-spectacular.readthedocs.io/en/latest/settings.html#settings
SWAGGER_SETTINGS = {
    'SECURITY_DEFINITIONS': {
        'Basic': {
            'type': 'basic'
        },
        'Token': {
            'type': 'apiKey',
            'name': 'Authorization',
            'in': 'header'
        }
    },
    'DEFAULT_GENERATOR_CLASS': 'drf_yasg.generators.OpenAPISchemaGenerator',
}
# Your stuff...
# ------------------------------------------------------------------------------
CREATE_PAYMENT_WITHDRAWAL_URL = os.getenv(
    "CREATE_PAYMENT_WITHDRAWAL_URL", "https://chd-api.smartcore.pro/withdrawal/init"
)
MERCHANT_KEY = os.getenv("MERCHANT_KEY", "MicroCash")
MERCHANT_SECRET = os.getenv("MERCHANT_SECRET", "VTwosV2nk6MtknSNy80qNlCgPsjhS41M")
MERCHANT_SITE_URL = os.getenv("MERCHANT_SITE_URL", "https://microcash.kz")
CREATE_PAYMENT_FORM_URL = os.getenv("CREATE_PAYMENT_FORM_URL", "https://api-gateway.smartcore.pro/initPayment")
CHECK_PAYMENT_STATUS_URL = os.getenv("CHECK_PAYMENT_STATUS_URL", "https://api-gateway.smartcore.pro/check")
PAYMENT_CALLBACK_URL = os.getenv("PAYMENT_CALLBACK_URL", "https://dev.microcash.kz/api/credits/payments/callback/")

PAYMENT_1C_WSDL = os.getenv("PAYMENT_1C_WSDL", default="")
PAYMENT_1C_USERNAME = os.getenv("PAYMENT_1C_USERNAME", default="")
PAYMENT_1C_PASSWORD = os.getenv("PAYMENT_1C_PASSWORD", default="")

# ERROR CODES
IS_NOT_CLIENT = os.getenv("IS_NOT_CLIENT", "IS_NOT_CLIENT")
PROFILE_ALREADY_EXISTS = os.getenv("PROFILE_ALREADY_EXISTS", "PROFILE_ALREADY_EXISTS")
IS_REGISTETED = os.getenv("IS_REGISTETED", "IS_REGISTETED")
INVALID_PASS = os.getenv("INVALID_PASS", "INVALID_PASS")

MANAGER_AUTO_SELECTION_ID = os.getenv("MANAGER_AUTO_SELECTION_ID", "1")
EMAIL_ENABLE = os.getenv("EMAIL_ENABLE", "False")
SWAGGER_BASE_URL = os.getenv('SWAGGER_BASE_URL', 'https://dev.microcash.kz/api')


# Verigram Biometry
API_KEY = os.getenv("API_KEY", "RPLCHDCEIRZNSXWXMHV4JY")
API_SECRET = os.getenv("API_SECRET", "XB4E8Q8hsFK8DB3k9M6nhzMAT3sPVVVAsCNCnPZy")
VERIGRAM_TOKEN_URL = os.getenv("VERIGRAM_TOKEN_URL", "https://services.verigram.cloud")
VERIGRAM_URL = os.getenv("VERIGRAM_URL", "https://services.verigram.ai:8443/s/veriface")
VERIGRAM_BIOMETRY_MIN_SCORE = os.getenv("VERIGRAM_BIOMETRY_MIN_SCORE", 50)
BIOMETRY_ATTEMPTS_COUNT = os.getenv("BIOMETRY_ATTEMPTS_COUNT", 3)
VERIGRAM_BASE_URL = os.getenv("VERIGRAM_BASE_URL", "https://services.verigram.cloud")
COMPANY_LOGO_URL = os.getenv("COMPANY_LOGO_URL", "https://dev.microcash.kz/api/static/images/logo.jpg")
BASE_URL = os.getenv("BASE_URL", "https://dev.microcash.kz/api")
