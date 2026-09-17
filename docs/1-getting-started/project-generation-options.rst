.. _template-options:

Project Generation Options
==========================

This page describes all the template options that will be prompted by the `cookiecutter CLI`_ prior to generating your project.

.. _cookiecutter CLI: https://github.com/cookiecutter/cookiecutter

project_name:
    Your project's human-readable name, capitals and spaces allowed.

project_slug:
    Your project's slug without dashes or spaces. Used to name your repo
    and in other places where a Python-importable version of your project name
    is needed.

description:
    Describes your project and gets used in places like ``README.rst`` and such.

author_name:
    This is you! The value goes into places like ``LICENSE`` and such.

domain_name:
    The domain name you plan to use for your project once it goes live.
    Note that it can be safely changed later on whenever you need to.

email:
    The email address you want to identify yourself in the project.

version:
    The version of the project at its inception.

open_source_license:
    A software license for the project. The choices are:

    1. MIT_
    2. BSD_
    3. GPLv3_
    4. `Apache Software License 2.0`_
    5. Not open source

username_type:
    How users log in. The choices are:

    1. ``username``, with an email field as well
    2. ``email``, with no username field

    It is best practice to always include an email field, so there is no option for
    having just the ``username`` field.

timezone:
    The value to be used for the ``TIME_ZONE`` setting of the project.

use_docker:
    Indicates whether the project should be configured to use Docker_ and `Docker Compose`_.

postgresql_version:
    Select a PostgreSQL_ version to use. The choices are:

    1. 18
    2. 17
    3. 16
    4. 15
    5. 14

cloud_provider:
    Select a cloud provider for static & media files. The choices are:

    1. AWS_
    2. None

    AWS means S3, so any S3-compatible service (Cloudflare R2, Backblaze B2, DigitalOcean
    Spaces, MinIO) works too: point ``AWS_S3_ENDPOINT_URL`` at it in
    ``config/settings/production.py``.

    If you choose no cloud provider and docker, the production stack will serve the media files via an nginx Docker service. Without Docker, the media files won't work.

mail_service:
    Select an email service that Django-Anymail provides

    1. Mailgun_
    2. `Amazon SES`_
    3. `Other SMTP`_

    ``Other SMTP`` uses Django's own SMTP backend, so any service Anymail supports can be
    reached by installing its Anymail extra and setting ``EMAIL_BACKEND`` yourself.

rest_api:
    Select a REST API framework to use. The choices are:

    1. None
    2. ``DRF``, `Django Rest Framework`_
    3. `Django Ninja`_

identity_provider:
    Select an identity provider for signing in through the browser, next to password login.
    The choices are:

    1. none
    2. ``entra``, `Microsoft Entra ID`_ through allauth's OpenID Connect provider, with the
       account keyed by the tenant's immutable object id
    3. ``google``, `Google`_ sign-in

    A provider adds its button to the login page of every project. With `Django Ninja`_ it also
    configures allauth's headless API with app-issued JWTs for a single-page application, and the
    ``identity`` app that verifies the provider's own tokens for calling services. The generated
    ``docs/authentication.rst`` covers the registration, the settings and the flows.

realtime:
    Select the realtime layer. Every project is served through ASGI with Uvicorn, so this only
    decides whether websocket support is included. The choices are:

    1. none
    2. ``channels``, `Django Channels`_ with the in-memory channel layer in development and Redis in production

use_celery:
    Indicates whether the project should be configured to use Celery_. Every project includes Django's built-in Tasks framework for background work (see :ref:`tasks`); Celery adds a broker, the beat scheduler and Flower for workloads that need scheduling, retries or a distributed queue. It runs alongside the Tasks framework rather than underneath it, and ``users/tasks.py`` carries one example of each.

mail_catcher:
    Select a local email catcher to receive emails during development. The choices are:

    1. None
    2. Mailpit_
    3. `Mailtrap Local`_

use_sentry:
    Indicates whether the project should be configured to use Sentry_.

use_whitenoise:
    Indicates whether the project should be configured to use WhiteNoise_.

ci_tool:
    Select a CI tool for running tests. The choices are:

    1. None
    2. `Gitlab CI`_
    3. `Github Actions`_

coding_agent:
    Select the coding agent the generated project writes its instructions for. The guide it
    writes records the answers given here, the commands the project runs, where its code lives
    and the conventions that code follows, under the file name that agent reads. The choices
    are:

    1. none, so no guide is written
    2. claude, for `Claude Code`_, which reads ``CLAUDE.md``
    3. codex, for `OpenAI Codex`_, which reads ``AGENTS.md``
    4. cursor, for Cursor_, which reads ``AGENTS.md``
    5. copilot, for `GitHub Copilot`_, which reads ``.github/copilot-instructions.md``

debug:
    Indicates whether the project should be configured for debugging.
    This option is relevant for moldordie developers only.


.. _MIT: https://opensource.org/licenses/MIT
.. _BSD: https://opensource.org/licenses/BSD-3-Clause
.. _GPLv3: https://www.gnu.org/licenses/gpl.html
.. _Apache Software License 2.0: https://www.apache.org/licenses/LICENSE-2.0

.. _Docker: https://github.com/docker/docker
.. _Docker Compose: https://docs.docker.com/compose/

.. _PostgreSQL: https://www.postgresql.org/docs/

.. _AWS: https://aws.amazon.com/s3/

.. _Amazon SES: https://aws.amazon.com/ses/
.. _Mailgun: https://www.mailgun.com
.. _Other SMTP: https://anymail.readthedocs.io/en/stable/

.. _Django Rest Framework: https://github.com/encode/django-rest-framework/
.. _Django Ninja: https://github.com/vitalik/django-ninja

.. _Microsoft Entra ID: https://learn.microsoft.com/entra/identity-platform/
.. _Google: https://developers.google.com/identity

.. _Celery: https://github.com/celery/celery

.. _Mailpit: https://github.com/axllent/mailpit

.. _Mailtrap Local: https://github.com/mailtrap/mailtrap-local

.. _Sentry: https://github.com/getsentry/sentry

.. _WhiteNoise: https://github.com/evansd/whitenoise

.. _GitLab CI: https://docs.gitlab.com/ee/ci/

.. _Github Actions: https://docs.github.com/en/actions

.. _Claude Code: https://code.claude.com/docs
.. _OpenAI Codex: https://developers.openai.com/codex
.. _Cursor: https://cursor.com/docs
.. _GitHub Copilot: https://docs.github.com/en/copilot
.. _Django Channels: https://channels.readthedocs.io/
