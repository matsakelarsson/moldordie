# moldordie

moldordie is a fork of [cookiecutter-django](https://github.com/cookiecutter/cookiecutter-django).
Powered by [Cookiecutter](https://github.com/cookiecutter/cookiecutter), it is a framework for jumpstarting
production-ready Django projects quickly.

- Documentation: [docs/](docs/)
- See [Troubleshooting](docs/5-help/troubleshooting.rst) for common errors and obstacles
- If you have problems with moldordie, please open [issues](https://github.com/matsakelarsson/moldordie/issues/new).

## Features

- For Django 6.0, using its template partials, Content Security Policy and Tasks framework
- Works with Python 3.12, 3.13 and 3.14 (3.14 by default)
- Renders Django projects with 100% starting test coverage
- Server-rendered frontend with [htmx](https://htmx.org) (via [django-htmx](https://github.com/adamchainz/django-htmx)) and a vendored, pinned [Pico CSS](https://picocss.com) — no Node.js toolchain, no CDN
- Nonce-based Content Security Policy on every response
- Background tasks with Django's Tasks framework, stored in PostgreSQL in production via [django-tasks-db](https://github.com/RealOrangeOne/django-tasks-db)
- [12-Factor](https://12factor.net) based settings via [django-environ](https://github.com/joke2k/django-environ)
- Secure by default. We believe in SSL.
- Optimized development and production settings
- Registration via [django-allauth](https://github.com/pennersr/django-allauth)
- Comes with custom user model ready to go
- Served through ASGI with [Uvicorn](https://www.uvicorn.org/), with optional [Django Channels](https://channels.readthedocs.io/) support for websockets
- Send emails via [Anymail](https://github.com/anymail/django-anymail) (using [Mailgun](http://www.mailgun.com/) by default or Amazon SES if AWS is selected cloud provider, but switchable)
- Media storage using Amazon S3, Google Cloud Storage, Azure Storage or nginx
- Docker support using [docker-compose](https://github.com/docker/compose) for development and production (using [Traefik](https://traefik.io/) with [LetsEncrypt](https://letsencrypt.org/) support)
- [Procfile](https://devcenter.heroku.com/articles/procfile) for deploying to Heroku
- Instructions for deploying to [PythonAnywhere](https://www.pythonanywhere.com/)
- Run tests with unittest or pytest
- Customizable PostgreSQL version
- Default integration with [pre-commit](https://github.com/pre-commit/pre-commit) for identifying simple issues before submission to code review

## Optional Integrations

_These features can be enabled during initial project setup._

- Serve static files from Amazon S3, Google Cloud Storage, Azure Storage or [Whitenoise](https://whitenoise.readthedocs.io/)
- Configuration for [Celery](https://docs.celeryq.dev) and [Flower](https://github.com/mher/flower) as an additional task queue with scheduling (the latter in Docker setup only)
- Integration with [Mailpit](https://github.com/axllent/mailpit/) or [Mailtrap Local](https://github.com/mailtrap/mailtrap-local) for local email testing
- Integration with [Sentry](https://sentry.io/welcome/) for error logging

## Constraints

- Only maintained 3rd party libraries are used.
- Uses PostgreSQL everywhere: 14 - 18.
- Environment variables for configuration (This won't work with Apache/mod_wsgi).

## Usage

Let's pretend you want to create a Django project called "redditclone". Rather than using `startproject`
and then editing the results to include your name, email, and various configuration issues that always get forgotten until the worst possible moment, get [cookiecutter](https://github.com/cookiecutter/cookiecutter) to do all the work.

First, get Cookiecutter. Trust me, it's awesome:

    uv tool install "cookiecutter>=1.7.0"

Now run it against this repo:

    uvx cookiecutter https://github.com/matsakelarsson/moldordie

You'll be prompted for some values. Provide them, then a Django project will be created for you.

**Warning**: After this point, change 'Daniel Greenfeld', 'pydanny', etc to your own information.

Answer the prompts with your own desired [options](docs/1-getting-started/project-generation-options.rst). For example:

    project_name [My Awesome Project]: Reddit Clone
    project_slug [reddit_clone]: reddit
    description [Behold My Awesome Project!]: A reddit clone.
    author_name [Daniel Roy Greenfeld]: Daniel Greenfeld
    domain_name [example.com]: myreddit.com
    email [daniel-greenfeld@example.com]: pydanny@gmail.com
    version [0.1.0]: 0.0.1
    Select open_source_license:
    1 - MIT
    2 - BSD
    3 - GPLv3
    4 - Apache Software License 2.0
    5 - Not open source
    Choose from 1, 2, 3, 4, 5 [1]: 1
    Select username_type:
    1 - username
    2 - email
    Choose from 1, 2 [1]: 1
    timezone [UTC]: America/Los_Angeles
    use_docker [n]: n
    Select postgresql_version:
    1 - 18
    2 - 17
    3 - 16
    4 - 15
    5 - 14
    Choose from 1, 2, 3, 4 [1]: 1
    Select cloud_provider:
    1 - AWS
    2 - GCP
    3 - None
    Choose from 1, 2, 3 [1]: 1
    Select mail_service:
    1 - Mailgun
    2 - Amazon SES
    3 - Mailjet
    4 - Mandrill
    5 - Postmark
    6 - Sendgrid
    7 - Brevo (formerly SendinBlue)
    8 - SparkPost
    9 - Other SMTP
    Choose from 1, 2, 3, 4, 5, 6, 7, 8, 9 [1]: 1
    Select rest_api [None]:
    1 - None
    2 - DRF
    3 - Django Ninja
    Choose from 1, 2, 3 [1]: 1
    Select realtime:
    1 - none
    2 - channels
    Choose from 1, 2 [1]: 1
    use_celery [n]: y
    Select mail_catcher:
    1 - None
    2 - Mailpit
    3 - Mailtrap Local
    Choose from 1, 2, 3 [1]: 1
    use_sentry [n]: y
    use_whitenoise [n]: n
    use_heroku [n]: y
    Select ci_tool:
    1 - None
    2 - Travis
    3 - Gitlab
    4 - Github
    Choose from 1, 2, 3, 4 [1]: 4
    keep_local_envs_in_vcs [y]: y
    debug [n]: n

Enter the project and take a look around:

    cd reddit/
    ls

Create a git repo and push it there:

    git init
    git add .
    git commit -m "first awesome commit"
    git remote add origin git@github.com:pydanny/redditclone.git
    git push -u origin main

Now take a look at your repo. Don't forget to carefully look at the generated README. Awesome, right?

For local development, see the following:

- [Developing locally](docs/2-local-development/developing-locally.rst)
- [Developing locally using docker](docs/2-local-development/developing-locally-docker.rst)

## "Your Stuff"

Scattered throughout the Python and HTML of this project are places marked with "your stuff". This is where third-party libraries are to be integrated with your project.
