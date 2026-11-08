Settings
======================================================================

``config/settings/base.py`` holds what every environment shares. ``local.py``, ``test.py`` and ``production.py`` hold what differs, and each starts from ``base.py``. The tables below list every variable those modules read. A setting they hardcode cannot be changed through the environment, so change it in the module.

The project is served through ASGI, by Gunicorn with the Uvicorn worker in production and by Uvicorn alone while developing.

The ``Development`` column is the value with ``config.settings.local``, and ``Production`` the value with ``config.settings.production``{% if cookiecutter.use_docker == 'y' %}, which every deployed environment runs{% endif %}. "Required" means that the project refuses to start without it. The env files under ``.envs/`` set many of these, and that value wins over the default shown here.

Reading a ``.env`` file is off by default. Set ``DJANGO_READ_DOT_ENV_FILE=True`` in the environment to load ``.env`` from the root of the project. The real environment still takes precedence over the file.

General
----------------------------------------------------------------------

.. csv-table::
   :header-rows: 1
   :delim: |

   Variable | Django setting | Development | Production
   ``DJANGO_READ_DOT_ENV_FILE`` | ``READ_DOT_ENV_FILE`` | ``False`` | ``False``
   ``DJANGO_DEBUG`` | ``DEBUG`` | not used, ``local.py`` sets ``True`` | ``False``
   ``DJANGO_SECRET_KEY`` | ``SECRET_KEY`` | a development value | required
   ``DJANGO_ADMIN_URL`` | ``ADMIN_URL`` | not read, ``base.py`` sets ``admin/`` | required
   ``DJANGO_ALLOWED_HOSTS`` | ``ALLOWED_HOSTS`` | not read, ``local.py`` lists localhost | ``{{ cookiecutter.domain_name }}``
   ``DJANGO_ACCOUNT_ALLOW_REGISTRATION`` | ``ACCOUNT_ALLOW_REGISTRATION`` | ``True`` | ``True``
   ``DJANGO_ADMIN_FORCE_ALLAUTH`` | ``DJANGO_ADMIN_FORCE_ALLAUTH`` | ``False`` | ``False``
{%- if cookiecutter.use_docker == 'y' %}
   ``USE_DOCKER`` | ``INTERNAL_IPS`` | required, ``yes`` adds the container's gateway | not read
{%- endif %}

Database and cache
----------------------------------------------------------------------

Setting ``DATABASE_URL`` replaces the ``POSTGRES_*`` variables.

.. csv-table::
   :header-rows: 1
   :delim: |

   Variable | Django setting | Development | Production
   ``DATABASE_URL`` | ``DATABASES`` | unset | unset
   ``POSTGRES_DB`` | ``DATABASES`` | required | required
   ``POSTGRES_USER`` | ``DATABASES`` | required | required
   ``POSTGRES_PASSWORD`` | ``DATABASES`` | required | required
   ``POSTGRES_HOST`` | ``DATABASES`` | ``postgres`` | ``postgres``
   ``POSTGRES_PORT`` | ``DATABASES`` | ``5432`` | ``5432``
   ``CONN_MAX_AGE`` | ``DATABASES["default"]`` | not read | ``60``
   ``REDIS_URL`` | ``REDIS_URL`` | ``redis://{% if cookiecutter.use_docker == 'y' %}redis{% else %}localhost{% endif %}:6379/0`` | ``redis://{% if cookiecutter.use_docker == 'y' %}redis{% else %}localhost{% endif %}:6379/0``

Email
----------------------------------------------------------------------

.. csv-table::
   :header-rows: 1
   :delim: |

   Variable | Django setting | Development | Production
   ``DJANGO_EMAIL_BACKEND`` | ``EMAIL_BACKEND`` | {% if cookiecutter.mail_catcher == 'None' %}the console{% else %}the SMTP backend, which reaches the mail catcher{% endif %} | not used, ``production.py`` sets the backend
{%- if cookiecutter.mail_catcher != 'None' and cookiecutter.use_docker == 'y' %}
   ``EMAIL_HOST`` | ``EMAIL_HOST`` | the mail catcher's service | not read
{%- endif %}
   ``DJANGO_DEFAULT_FROM_EMAIL`` | ``DEFAULT_FROM_EMAIL`` | not read | the project's name and ``noreply@{{ cookiecutter.domain_name }}``
   ``DJANGO_SERVER_EMAIL`` | ``SERVER_EMAIL`` | not read | ``DEFAULT_FROM_EMAIL``
   ``DJANGO_EMAIL_SUBJECT_PREFIX`` | ``EMAIL_SUBJECT_PREFIX`` | not read | the project's name in brackets
{%- if cookiecutter.mail_service == 'Mailgun' %}
   ``MAILGUN_API_KEY`` | ``ANYMAIL["MAILGUN_API_KEY"]`` | not read | required
   ``MAILGUN_DOMAIN`` | ``ANYMAIL["MAILGUN_SENDER_DOMAIN"]`` | not read | required
   ``MAILGUN_API_URL`` | ``ANYMAIL["MAILGUN_API_URL"]`` | not read | ``https://api.mailgun.net/v3``
{%- endif %}

Security
----------------------------------------------------------------------

.. csv-table::
   :header-rows: 1
   :delim: |

   Variable | Django setting | Development | Production
   ``DJANGO_SECURE_SSL_REDIRECT`` | ``SECURE_SSL_REDIRECT`` | not read | ``True``
   ``DJANGO_SECURE_CONTENT_TYPE_NOSNIFF`` | ``SECURE_CONTENT_TYPE_NOSNIFF`` | not read | ``True``
   ``DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS`` | ``SECURE_HSTS_INCLUDE_SUBDOMAINS`` | not read | ``True``
   ``DJANGO_SECURE_HSTS_PRELOAD`` | ``SECURE_HSTS_PRELOAD`` | not read | ``True``
   ``DJANGO_CSP_REPORT_URI`` | ``SECURE_CSP["report-uri"]`` | not read | unset, no ``report-uri`` directive
   ``DJANGO_CSP_REPORT_ONLY`` | ``SECURE_CSP_REPORT_ONLY`` | not read | ``False``, the policy is enforced
{%- if cookiecutter.cloud_provider == 'AWS' %}

Storage
----------------------------------------------------------------------

.. csv-table::
   :header-rows: 1
   :delim: |

   Variable | Django setting | Development | Production
   ``DJANGO_AWS_ACCESS_KEY_ID`` | ``AWS_ACCESS_KEY_ID`` | not read | required
   ``DJANGO_AWS_SECRET_ACCESS_KEY`` | ``AWS_SECRET_ACCESS_KEY`` | not read | required
   ``DJANGO_AWS_STORAGE_BUCKET_NAME`` | ``AWS_STORAGE_BUCKET_NAME`` | not read | required
   ``DJANGO_AWS_S3_REGION_NAME`` | ``AWS_S3_REGION_NAME`` | not read | ``None``
   ``DJANGO_AWS_S3_CUSTOM_DOMAIN`` | ``AWS_S3_CUSTOM_DOMAIN`` | not read | ``None``
   ``DJANGO_AWS_S3_MAX_MEMORY_SIZE`` | ``AWS_S3_MAX_MEMORY_SIZE`` | not read | ``100_000_000``
{%- endif %}
{%- if cookiecutter.use_sentry == 'y' %}

Sentry
----------------------------------------------------------------------

The project's ``sentry`` app starts the SDK from these settings once the app registry is ready.

.. csv-table::
   :header-rows: 1
   :delim: |

   Variable | Django setting | Development | Production
   ``SENTRY_DSN`` | ``SENTRY_DSN`` | not read | required
   ``SENTRY_ENVIRONMENT`` | ``SENTRY_ENVIRONMENT`` | not read | ``production``
   ``SENTRY_TRACES_SAMPLE_RATE`` | ``SENTRY_TRACES_SAMPLE_RATE`` | not read | ``0.0``
   ``DJANGO_SENTRY_LOG_LEVEL`` | ``SENTRY_LOG_LEVEL`` | not read | ``logging.INFO``
{%- endif %}
{%- if cookiecutter.observability == 'prometheus' %}

Metrics
----------------------------------------------------------------------

:doc:`observability` explains the credential and the scrape.

.. csv-table::
   :header-rows: 1
   :delim: |

   Variable | Django setting | Development | Production
   ``DJANGO_METRICS_TOKEN`` | ``METRICS_TOKEN`` | empty | empty
{%- endif %}
{%- if cookiecutter.observability == 'opentelemetry' %}

Telemetry
----------------------------------------------------------------------

While ``OTEL_EXPORTER_OTLP_ENDPOINT`` is unset the project exports nothing. :doc:`observability` covers the collector.

.. csv-table::
   :header-rows: 1
   :delim: |

   Variable | Django setting | Development | Production
   ``OTEL_SERVICE_NAME`` | ``OTEL_SERVICE_NAME`` | ``{{ cookiecutter.project_slug }}`` | ``{{ cookiecutter.project_slug }}``
   ``OTEL_DEPLOYMENT_ENVIRONMENT`` | ``OTEL_DEPLOYMENT_ENVIRONMENT`` | ``local`` | ``local``, each deployed env file names its own
   ``OTEL_EXPORTER_OTLP_ENDPOINT`` | ``OTEL_EXPORTER_OTLP_ENDPOINT`` | empty | empty
   ``OTEL_EXPORTER_OTLP_HEADERS`` | ``OTEL_EXPORTER_OTLP_HEADERS`` | empty | empty
   ``OTEL_EXPORTER_OTLP_CERTIFICATE`` | ``OTEL_EXPORTER_OTLP_CERTIFICATE`` | empty | empty
{%- endif %}
{%- if cookiecutter.identity_provider != 'none' %}

Identity provider
----------------------------------------------------------------------

The credentials default to empty so that the project starts without them. ``python manage.py check`` reports each empty one as a warning, because sign-in cannot work until it is set. :doc:`authentication` describes the registration each one comes from.

.. csv-table::
   :header-rows: 1
   :delim: |

   Variable | Django setting | Development | Production
{%- if cookiecutter.identity_provider == 'entra' %}
   ``ENTRA_TENANT_ID`` | ``ENTRA_TENANT_ID`` | empty | empty
   ``ENTRA_LOGIN_CLIENT_ID`` | ``ENTRA_LOGIN_CLIENT_ID`` | empty | empty
   ``ENTRA_LOGIN_CLIENT_SECRET`` | ``ENTRA_LOGIN_CLIENT_SECRET`` | empty | empty
{%- if cookiecutter.service_tokens %}
   ``ENTRA_API_CLIENT_ID`` | ``IDENTITY_SERVICE_AUDIENCE`` | empty | empty
   ``ENTRA_SERVICE_ROLE`` | ``ENTRA_SERVICE_ROLE`` | ``Service.Access`` | ``Service.Access``
{%- endif %}
{%- else %}
   ``GOOGLE_LOGIN_CLIENT_ID`` | ``GOOGLE_LOGIN_CLIENT_ID`` | empty | empty
   ``GOOGLE_LOGIN_CLIENT_SECRET`` | ``GOOGLE_LOGIN_CLIENT_SECRET`` | empty | empty
{%- if cookiecutter.service_tokens %}
   ``GOOGLE_SERVICE_AUDIENCE`` | ``IDENTITY_SERVICE_AUDIENCE`` | ``https://{{ cookiecutter.domain_name }}`` | ``https://{{ cookiecutter.domain_name }}``
{%- endif %}
{%- endif %}
{%- endif %}
{%- if cookiecutter.headless %}

Single-page application
----------------------------------------------------------------------

allauth's headless API serves a single-page application, and the ``identity`` app refuses to start with an empty signing key or a lifetime that is not positive.

.. csv-table::
   :header-rows: 1
   :delim: |

   Variable | Django setting | Development | Production
   ``DJANGO_HEADLESS_JWT_PRIVATE_KEY`` | ``HEADLESS_JWT_PRIVATE_KEY`` | a development key | required
   ``DJANGO_HEADLESS_JWT_ACCESS_TOKEN_EXPIRES_IN`` | ``HEADLESS_JWT_ACCESS_TOKEN_EXPIRES_IN`` | ``300`` | ``300``
   ``DJANGO_HEADLESS_JWT_REFRESH_TOKEN_EXPIRES_IN`` | ``HEADLESS_JWT_REFRESH_TOKEN_EXPIRES_IN`` | ``86400`` | ``86400``
   ``DJANGO_FRONTEND_ORIGINS`` | ``FRONTEND_ORIGINS`` | ``http://localhost:5173`` | required
   ``DJANGO_FRONTEND_URL`` | ``FRONTEND_URL`` | ``http://localhost:5173`` | required
{%- endif %}
