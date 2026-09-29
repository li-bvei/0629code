import os
from pathlib import Path

from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / '.env')

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'django-insecure-local-dev-key')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DJANGO_DEBUG', 'True') == 'True'

# Key used to encrypt sensitive PII fields (e.g. マイナンバー) at rest.
# Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
FIELD_ENCRYPTION_KEY = os.getenv('FIELD_ENCRYPTION_KEY', 'Xbl6ZzuVAEiN7PrpPSbZlEYiYKOsJQU8fZQuecZP0QM=')

def env_list(name, default=''):
    value = os.getenv(name, default)
    return [item.strip() for item in value.split(',') if item.strip()]


LOCAL_FRONTEND_ORIGINS = [
    'http://127.0.0.1:5173',
    'http://localhost:5173',
    'http://127.0.0.1:5174',
    'http://localhost:5174',
]

ALLOWED_HOSTS = env_list('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1')
CSRF_TRUSTED_ORIGINS = env_list(
    'DJANGO_CSRF_TRUSTED_ORIGINS',
    ','.join(LOCAL_FRONTEND_ORIGINS),
)
if DEBUG:
    CSRF_TRUSTED_ORIGINS = list(dict.fromkeys([*CSRF_TRUSTED_ORIGINS, *LOCAL_FRONTEND_ORIGINS]))

CORS_ALLOWED_ORIGINS = env_list('DJANGO_CORS_ALLOWED_ORIGINS', ','.join(LOCAL_FRONTEND_ORIGINS))
if DEBUG:
    CORS_ALLOWED_ORIGINS = list(dict.fromkeys([*CORS_ALLOWED_ORIGINS, *LOCAL_FRONTEND_ORIGINS]))
CORS_ALLOW_CREDENTIALS = True


# Application definition

INSTALLED_APPS = [
    'simpleui',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'axes',
    'apps.authentication',
    'apps.employees',
    'apps.customers',
    'apps.companies',
    'apps.cases',
    'apps.tasks',
    'apps.reminders',
    'apps.timelines',
    'apps.documents',
    'apps.accounting',
    'apps.real_estate',
    'apps.audit',
    'api',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'apps.audit.middleware.RequestIdMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'axes.middleware.AxesMiddleware',
]

AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesStandaloneBackend',
    'django.contrib.auth.backends.ModelBackend',
]

# Brute-force login protection (covers both /admin/login and /api/auth/login/).
AXES_FAILURE_LIMIT = 3
AXES_LOCKOUT_PARAMETERS = ['username']
AXES_COOLOFF_TIME = 1  # hours
AXES_RESET_ON_SUCCESS = True

ROOT_URLCONF = 'config.urls'

# --- 環境・アクセス制御（docs/SYSTEM_ARCHITECTURE.md / docs/P0_ACCESS_CONTROL_DESIGN.md） ---
# APP_ENV: development / staging / production。本番では DJANGO_APP_ENV=production を必ず設定する。
APP_ENV = os.getenv('DJANGO_APP_ENV', 'development' if DEBUG else 'production')
IS_PRODUCTION = APP_ENV == 'production'
# デモデータ生成・seed・PDF座標デバッグ等の開発用エンドポイント。本番では常に無効。
ENABLE_DEV_TOOLS = (os.getenv('DJANGO_ENABLE_DEV_TOOLS', 'True' if DEBUG else 'False') == 'True') and not IS_PRODUCTION
# 段階B：Django Admin を保護アカウント（ProtectedAccount）に限定する。段階Aでは False。
PROTECTED_ADMIN_ENFORCEMENT = os.getenv('DJANGO_PROTECTED_ADMIN_ENFORCEMENT', 'False') == 'True'
# localdev アカウント検査：warn（初期）/ enforce（本番で停止を確認後）。
LOCALDEV_CHECK_MODE = os.getenv('DJANGO_LOCALDEV_CHECK_MODE', 'warn')
LOCALDEV_USERNAMES = env_list('DJANGO_LOCALDEV_USERNAMES', 'localdev')
# 受保護ダウンロード：True なら nginx の X-Accel-Redirect で送信（本番）、False なら FileResponse（開発）。
PROTECTED_MEDIA_X_ACCEL = os.getenv('DJANGO_PROTECTED_MEDIA_X_ACCEL', 'False' if DEBUG else 'True') == 'True'
PROTECTED_MEDIA_X_ACCEL_PREFIX = '/_protected_media/'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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

WSGI_APPLICATION = 'config.wsgi.application'


# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.getenv('MYSQL_DATABASE', 'gyoseishoshi_erp'),
        'USER': os.getenv('MYSQL_USER', 'root'),
        'PASSWORD': os.getenv('MYSQL_PASSWORD', ''),
        'HOST': os.getenv('MYSQL_HOST', '127.0.0.1'),
        'PORT': os.getenv('MYSQL_PORT', '3306'),
        'OPTIONS': {
            'charset': 'utf8mb4',
        },
    }
}


# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = 'ja'

# 事務所の業務は全て日本時間で運用する。案件番号の採番・受付日・期限・
# ダッシュボードの「今日」・ファイル名の日付などは timezone.localdate() /
# timezone.localtime() 経由でこの TIME_ZONE を基準に判定すること。
TIME_ZONE = 'Asia/Tokyo'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.FormParser',
        'rest_framework.parsers.MultiPartParser',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

SIMPLEUI_HOME_INFO = False
SIMPLEUI_ANALYSIS = False
SIMPLEUI_DEFAULT_THEME = 'light.css'
