.. _deployment-with-docker:

Deployment with Docker
======================

.. index:: deployment, docker, docker compose, compose


Prerequisites
-------------

* Docker 17.05+.
* Docker Compose 1.17+


The Deployed Environments
-------------------------

The project is generated with three deployed environments, in the order a change is promoted through them: ``dev``, ``test`` and ``production``. Each one is a Compose file in the root of the project and a directory of env files beside it:

.. list-table::
   :header-rows: 1

   * - Environment
     - Compose file
     - Env files
     - Host it answers for
   * - ``dev``
     - ``docker-compose.dev.yml``
     - ``.envs/.dev/``
     - ``dev.<your domain>``
   * - ``test``
     - ``docker-compose.test.yml``
     - ``.envs/.test/``
     - ``test.<your domain>``
   * - ``production``
     - ``docker-compose.production.yml``
     - ``.envs/.production/``
     - ``<your domain>``

All three run the same code, built the same way: every one of them builds its images from ``compose/production/``, and every one of them runs ``config/settings/production.py``, which each environment's ``.django`` file names in ``DJANGO_SETTINGS_MODULE``. There is no ``config/settings/dev.py``: a settings module belongs to a *kind* of configuration, not to a deployment, and an environment that ran its own module would drift from production and stop rehearsing it. What an environment is free to differ in is its environment variables, and each one gets its own:

* its hosts, in ``DJANGO_ALLOWED_HOSTS`` and in the Traefik routers the image is built with;
* its secrets — the Django secret key, the admin URL, the database password, Flower's password and, with the single-page application, the token signing key — each drawn separately when the project is generated, so a session or token minted for one environment is not accepted by another. The database role and Flower's user are the deliberate exception: they are shared, so a ``pg_dump`` taken in one environment restores in another;
* the deployment it reports as, in ``SENTRY_ENVIRONMENT``;
* its own Docker volumes, each prefixed with the environment's name, and its own image tags.

The commands below are written with ``docker-compose.production.yml``. Point ``-f`` at another environment's Compose file to run them against it.

Understanding the Docker Compose Setup
--------------------------------------

Before you begin, check out the ``docker-compose.production.yml`` file in the root of this project — the ``dev`` and ``test`` files differ from it only in the configuration named above. Keep note of how it provides configuration for the following services:

* ``django``: your application running behind ``Gunicorn``;
* ``postgres``: PostgreSQL database with the application's relational data;
* ``redis``: Redis instance for caching;
* ``taskworker``: the worker of Django's Tasks framework (``python manage.py db_worker``, see :ref:`tasks`);
* ``traefik``: Traefik reverse proxy with HTTPS on by default. Its static configuration is ``compose/production/traefik/traefik.yml``; its dynamic configuration is the directory beside it, where ``shared.yml`` holds the services and middlewares every environment shares and ``dev.yml``, ``test.yml`` and ``production.yml`` hold each environment's routers. The Compose file passes its environment's name as the ``ENVIRONMENT`` build argument, and the image is built with that environment's routers.

Provided you have opted for Celery (via setting ``use_celery`` to ``y``) there are three more services:

* ``celeryworker`` running a Celery worker process;
* ``celerybeat`` running a Celery beat process;
* ``flower`` running Flower_.

The ``flower`` service is served by Traefik over HTTPS, through the port ``5555``. For more information about Flower and its login credentials, check out :ref:`CeleryFlower` instructions for local environment.

.. _`Flower`: https://github.com/mher/flower


Configuring the Stack
---------------------

The majority of services above are configured through the use of environment variables. Just check out :ref:`envs` and you will know the drill.

If you generated the project with a cloud provider, the bucket holding your static files needs to allow public reads of the ``static`` prefix, otherwise your static files will return a ``403``. See :ref:`cloud-storage`.

To obtain logs and information about crashes in a production setup, make sure that you have access to an external Sentry instance (e.g. by creating an account with `sentry.io`_), and set the ``SENTRY_DSN`` variable. Logs of level `logging.ERROR` are sent as Sentry events. Therefore, in order to send a Sentry event use:

.. code-block:: python

    import logging
    logging.error("This event is sent to Sentry", extra={"<example_key>": "<example_value>"})

The `extra` parameter allows you to send additional information about the context of this error.


With ``observability=prometheus``, the application exposes its metrics at ``/metrics``, to a scrape that presents ``DJANGO_METRICS_TOKEN`` as a bearer token. Point your own Prometheus at every replica rather than at the proxy in front of them — a scrape that arrives through Traefik describes whichever replica answered it — and read the generated ``docs/observability.rst`` for the scrape configuration and for what Gunicorn's multiprocess mode changes about the exposition.

You will probably also need to setup the Mail backend, for example by adding a `Mailgun`_ API key and a `Mailgun`_ sender domain, otherwise, the account creation view will crash and result in a 500 error when the backend attempts to send an email to the account owner.

.. _sentry.io: https://sentry.io/welcome
.. _Mailgun: https://mailgun.com


.. warning::

    .. include:: ../includes/mailgun.rst


Optional: Use AWS IAM Role for EC2 instance
-------------------------------------------

If you are deploying to AWS, you can use the IAM role to substitute AWS credentials, after which it's safe to remove the ``AWS_ACCESS_KEY_ID`` AND ``AWS_SECRET_ACCESS_KEY`` from ``.envs/.production/.django``. To do it, create an `IAM role`_ and `attach`_ it to the existing EC2 instance or create a new EC2 instance with that role. The role should assume, at minimum, the ``AmazonS3FullAccess`` permission.

.. _IAM role: https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html
.. _attach: https://aws.amazon.com/blogs/security/easily-replace-or-attach-an-iam-role-to-an-existing-ec2-instance-by-using-the-ec2-console/


HTTPS is On by Default
----------------------

SSL (Secure Sockets Layer) is a standard security technology for establishing an encrypted link between a server and a client, typically in this case, a web server (website) and a browser. Not having HTTPS means that malicious network users can sniff authentication credentials between your website and end users' browser.

It is always better to deploy a site behind HTTPS and will become crucial as the web services extend to the IoT (Internet of Things). For this reason, we have set up a number of security defaults to help make your website secure:

* If you are not using a subdomain of the domain name set in the project, then remember to put your staging/production IP address in the ``DJANGO_ALLOWED_HOSTS`` environment variable (see :ref:`settings`) before you deploy your website. Failure to do this will mean you will not have access to your website through the HTTP protocol.

* Access to the Django admin is set up by default to require HTTPS in production or once *live*.

The Traefik reverse proxy used in the default configuration will get you a valid certificate from Lets Encrypt and update it automatically. All you need to do to enable this is to make sure that your DNS records are pointing to the server Traefik runs on.

You can read more about this feature and how to configure it, at `Automatic HTTPS`_ in the Traefik docs.

.. _Automatic HTTPS: https://docs.traefik.io/https/acme/

(Optional) Postgres Data Volume Modifications
---------------------------------------------

Postgres is saving its database files to the ``production_postgres_data`` volume by default, and to the ``dev_``- and ``test_``-prefixed volumes in the other environments. Change that if you want something else and make sure to make backups since this is not done automatically.


Building & Running Production Stack
-----------------------------------

You will need to build the stack first. To do that, run::

    docker compose -f docker-compose.production.yml build

The ``django`` image is built with its stylesheet: its build stage runs ``python manage.py tailwind build``, which downloads the Tailwind CLI named by ``TAILWIND_CLI_VERSION`` from GitHub's releases, so a build on a cold cache needs to reach github.com. The CLI stays in a build cache and never becomes part of the image. A container builds nothing when it starts; its ``collectstatic`` collects the stylesheet the image holds. A build host that cannot reach GitHub provisions the binary itself and points ``TAILWIND_CLI_PATH`` at it, or mirrors the release and names the mirror in ``TAILWIND_CLI_SRC_REPO``.

Once this is ready, you can run it with::

    docker compose -f docker-compose.production.yml up

To run the stack and detach the containers, run::

    docker compose -f docker-compose.production.yml up -d

To run a migration, open up a second terminal and run::

   docker compose -f docker-compose.production.yml run --rm django python manage.py migrate

This also creates the tables of the task queue. To create a superuser, run::

   docker compose -f docker-compose.production.yml run --rm django python manage.py createsuperuser

If you need a shell, run::

   docker compose -f docker-compose.production.yml run --rm django python manage.py shell

To check the logs out, run::

   docker compose -f docker-compose.production.yml logs

If you want to scale your application, run::

   docker compose -f docker-compose.production.yml up --scale django=4
   docker compose -f docker-compose.production.yml up --scale taskworker=2
   docker compose -f docker-compose.production.yml up --scale celeryworker=2

.. warning:: don't try to scale ``postgres``, ``celerybeat``, or ``traefik``.

To see how your containers are doing run::

    docker compose -f docker-compose.production.yml ps


Example: Supervisor
-------------------

Once you are ready with your initial setup, you want to make sure that your application is run by a process manager to
survive reboots and auto restarts in case of an error. You can use the process manager you are most familiar with. All
it needs to do is to run ``docker compose -f docker-compose.production.yml up`` in your projects root directory.

If you are using ``supervisor``, you can use this file as a starting point::

    [program:{{cookiecutter.project_slug}}]
    command=docker compose -f docker-compose.production.yml up
    directory=/path/to/{{cookiecutter.project_slug}}
    redirect_stderr=true
    autostart=true
    autorestart=true
    priority=10

Move it to ``/etc/supervisor/conf.d/{{cookiecutter.project_slug}}.conf`` and run::

    supervisorctl reread
    supervisorctl update
    supervisorctl start {{cookiecutter.project_slug}}

For status check, run::

    supervisorctl status

Media files without cloud provider
----------------------------------

If you chose no cloud provider and Docker, the media files will be served by an nginx service, from a ``production_django_media`` volume. Make sure to keep this around to avoid losing any media files.
