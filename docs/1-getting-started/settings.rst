.. _settings:

Settings
========

This project relies extensively on environment settings which **will not work with Apache/mod_wsgi setups**. It is served through ASGI, by Gunicorn with the Uvicorn worker.

The tables below list the variables the settings actually read. A setting the project hardcodes is not configurable through the environment even where Django would allow it, so the tables say where that is the case; change those in ``config/settings/``.

Whether a variable is read at all depends on the options the project was generated with: the third-party table only applies to the cloud provider, mail service and error tracker you picked.

Reading the ``.env`` file is off by default; set this to have django-environ load ``BASE_DIR/.env`` before anything else, with the real environment still taking precedence:

======================== ================= =================== ==================
Environment Variable     Django Setting    Development Default Production Default
======================== ================= =================== ==================
DJANGO_READ_DOT_ENV_FILE READ_DOT_ENV_FILE False               False
======================== ================= =================== ==================

This is the main table of Django and project settings:

===================================== ============================== ================================================== ==============================================
Environment Variable                  Django Setting                 Development Default                                Production Default
===================================== ============================== ================================================== ==============================================
DATABASE_URL                          DATABASES                      unset; POSTGRES_* used instead                     unset; POSTGRES_* used instead
POSTGRES_DB                           DATABASES                      raises error unless DATABASE_URL is set            raises error unless DATABASE_URL is set
POSTGRES_USER                         DATABASES                      raises error unless DATABASE_URL is set            raises error unless DATABASE_URL is set
POSTGRES_PASSWORD                     DATABASES                      raises error unless DATABASE_URL is set            raises error unless DATABASE_URL is set
POSTGRES_HOST                         DATABASES                      "postgres"                                         "postgres"
POSTGRES_PORT                         DATABASES                      "5432"                                             "5432"
CONN_MAX_AGE                          DATABASES["default"]           n/a                                                60
DJANGO_SECRET_KEY                     SECRET_KEY                     auto-generated                                     raises error
DJANGO_ADMIN_URL                      ADMIN_URL                      not read; base.py sets "admin/"                    raises error
DJANGO_DEBUG                          DEBUG                          not read; local.py sets True                       False
DJANGO_ALLOWED_HOSTS                  ALLOWED_HOSTS                  not read; local.py sets localhost                  ["your_domain_name"]
DJANGO_EMAIL_BACKEND                  EMAIL_BACKEND                  console, or SMTP with a mail catcher               n/a (Anymail sets the backend)
DJANGO_DEFAULT_FROM_EMAIL             DEFAULT_FROM_EMAIL             n/a                                                "your_project_name <noreply@your_domain_name>"
DJANGO_SERVER_EMAIL                   SERVER_EMAIL                   n/a                                                DEFAULT_FROM_EMAIL
DJANGO_EMAIL_SUBJECT_PREFIX           EMAIL_SUBJECT_PREFIX           n/a                                                "[your_project_name] "
DJANGO_SECURE_SSL_REDIRECT            SECURE_SSL_REDIRECT            n/a                                                True
DJANGO_SECURE_CONTENT_TYPE_NOSNIFF    SECURE_CONTENT_TYPE_NOSNIFF    n/a                                                True
DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS SECURE_HSTS_INCLUDE_SUBDOMAINS n/a                                                True
DJANGO_SECURE_HSTS_PRELOAD            SECURE_HSTS_PRELOAD            n/a                                                True
DJANGO_CSP_REPORT_URI                 SECURE_CSP["report-uri"]       n/a                                                unset (no report-uri directive)
DJANGO_CSP_REPORT_ONLY                SECURE_CSP_REPORT_ONLY         n/a                                                False (the policy is enforced)
REDIS_URL                             CACHES, Celery, Channels       "redis://redis:6379/0" with Docker, else localhost same default; point it at your instance
===================================== ============================== ================================================== ==============================================

The following table lists settings and their defaults for third-party applications, which may or may not be part of your project:

============================== ================================ =================== ==================================
Environment Variable           Django Setting                   Development Default Production Default
============================== ================================ =================== ==================================
DJANGO_AWS_ACCESS_KEY_ID       AWS_ACCESS_KEY_ID                n/a                 raises error
DJANGO_AWS_SECRET_ACCESS_KEY   AWS_SECRET_ACCESS_KEY            n/a                 raises error
DJANGO_AWS_STORAGE_BUCKET_NAME AWS_STORAGE_BUCKET_NAME          n/a                 raises error
DJANGO_AWS_S3_REGION_NAME      AWS_S3_REGION_NAME               n/a                 None
DJANGO_AWS_S3_CUSTOM_DOMAIN    AWS_S3_CUSTOM_DOMAIN             n/a                 None
DJANGO_AWS_S3_MAX_MEMORY_SIZE  AWS_S3_MAX_MEMORY_SIZE           n/a                 100_000_000
SENTRY_DSN                     SENTRY_DSN                       n/a                 raises error
SENTRY_ENVIRONMENT             SENTRY_ENVIRONMENT               n/a                 "production"
SENTRY_TRACES_SAMPLE_RATE      SENTRY_TRACES_SAMPLE_RATE        n/a                 0.0
DJANGO_SENTRY_LOG_LEVEL        SENTRY_LOG_LEVEL                 n/a                 logging.INFO
MAILGUN_API_KEY                ANYMAIL["MAILGUN_API_KEY"]       n/a                 raises error
MAILGUN_DOMAIN                 ANYMAIL["MAILGUN_SENDER_DOMAIN"] n/a                 raises error
MAILGUN_API_URL                ANYMAIL["MAILGUN_API_URL"]       n/a                 "https://api.mailgun.net/v3"
============================== ================================ =================== ==================================

--------------------------
Other Environment Settings
--------------------------

DJANGO_ACCOUNT_ALLOW_REGISTRATION (=True)
    Allow enable or disable user registration through `django-allauth` without disabling other characteristics like authentication and account management. (Django Setting: ACCOUNT_ALLOW_REGISTRATION)

DJANGO_ADMIN_FORCE_ALLAUTH (=False)
    Force the `admin` sign in process to go through the `django-allauth` workflow.
