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
- Server-rendered frontend with [htmx](https://htmx.org) (via [django-htmx](https://github.com/adamchainz/django-htmx)), styled with [Tailwind CSS](https://tailwindcss.com) and [daisyUI](https://daisyui.com) through [django-tailwind-cli](https://github.com/django-commons/django-tailwind-cli), with the project's own theme to edit, every daisyUI theme behind a theme picker and an examples page — no Node.js toolchain, no CDN and no JavaScript of the project's own
- Nonce-based Content Security Policy on every response
- Background tasks with Django's Tasks framework, stored in PostgreSQL in production via [django-tasks-db](https://github.com/RealOrangeOne/django-tasks-db)
- [12-Factor](https://12factor.net) based settings via [django-environ](https://github.com/joke2k/django-environ)
- Secure by default. We believe in SSL.
- Optimized development and production settings
- Registration via [django-allauth](https://github.com/pennersr/django-allauth)
- Comes with custom user model ready to go
- Served through ASGI with [Uvicorn](https://www.uvicorn.org/), with optional [Django Channels](https://channels.readthedocs.io/) support for websockets
- Send emails via [Anymail](https://github.com/anymail/django-anymail) (using [Mailgun](http://www.mailgun.com/) by default or Amazon SES if AWS is selected cloud provider, but switchable)
- Media storage using Amazon S3 (or any S3-compatible service) or nginx
- Docker support using [docker-compose](https://github.com/docker/compose) for development and production (using [Traefik](https://traefik.io/) with [LetsEncrypt](https://letsencrypt.org/) support)
- Instructions for deploying to [PythonAnywhere](https://www.pythonanywhere.com/)
- Run tests with unittest or pytest
- Customizable PostgreSQL version
- Default integration with [pre-commit](https://github.com/pre-commit/pre-commit) for identifying simple issues before submission to code review

## Optional Integrations

_These features can be enabled during initial project setup._

- Serve static files from Amazon S3 (or any S3-compatible service) or [Whitenoise](https://whitenoise.readthedocs.io/)
- Configuration for [Celery](https://docs.celeryq.dev) and [Flower](https://github.com/mher/flower) as an additional task queue with scheduling (the latter in Docker setup only)
- Integration with [Mailpit](https://github.com/axllent/mailpit/) or [Mailtrap Local](https://github.com/mailtrap/mailtrap-local) for local email testing
- Integration with [Sentry](https://sentry.io/welcome/) for error logging
- A guide for your coding agent — `CLAUDE.md`, `AGENTS.md` or GitHub Copilot's instructions — recording the answers the project was generated from, its commands, its layout and its conventions

## Constraints

- Only maintained 3rd party libraries are used.
- Uses PostgreSQL everywhere: 14 - 18.
- Environment variables for configuration (This won't work with Apache/mod_wsgi).

## Usage

Let's pretend you want to create a Django project called "redditclone". Rather than using `startproject`
and then editing the results to include your name, email, and various configuration issues that always get forgotten until the worst possible moment, get [cookiecutter](https://github.com/cookiecutter/cookiecutter) to do all the work.

Run Cookiecutter against this repo. `uvx` fetches it for the one run:

    uvx cookiecutter https://github.com/matsakelarsson/moldordie

If you generate projects often, install it once instead and drop the `uvx`:

    uv tool install cookiecutter

You'll be prompted for some values. Provide them, then a Django project will be created for you.

**Warning**: After this point, change 'Daniel Greenfeld', 'pydanny', etc to your own information.

Answer the prompts with your own desired [options](docs/1-getting-started/project-generation-options.rst). For example:

      [1/24] project_name (My Awesome Project): Reddit Clone
      [2/24] project_slug (reddit_clone): reddit
      [3/24] description (Behold My Awesome Project!): A reddit clone.
      [4/24] author_name (Daniel Roy Greenfeld): Daniel Greenfeld
      [5/24] domain_name (example.com): myreddit.com
      [6/24] email (daniel-greenfeld@myreddit.com): pydanny@gmail.com
      [7/24] version (0.1.0): 0.0.1
      [8/24] Select open_source_license
        1 - MIT
        2 - BSD
        3 - GPLv3
        4 - Apache Software License 2.0
        5 - Not open source
        Choose from [1/2/3/4/5] (1): 1
      [9/24] Select username_type
        1 - username
        2 - email
        Choose from [1/2] (1): 1
      [10/24] timezone (UTC): America/Los_Angeles
      [11/24] use_docker (n): n
      [12/24] Select postgresql_version
        1 - 18
        2 - 17
        3 - 16
        4 - 15
        5 - 14
        Choose from [1/2/3/4/5] (1): 1
      [13/24] Select cloud_provider
        1 - AWS
        2 - None
        Choose from [1/2] (1): 1
      [14/24] Select mail_service
        1 - Mailgun
        2 - Amazon SES
        3 - Other SMTP
        Choose from [1/2/3] (1): 1
      [15/24] Select rest_api
        1 - None
        2 - DRF
        3 - Django Ninja
        Choose from [1/2/3] (1): 1
      [16/24] Select identity_provider
        1 - none
        2 - entra
        3 - google
        Choose from [1/2/3] (1): 1
      [17/24] Select realtime
        1 - none
        2 - channels
        Choose from [1/2] (1): 1
      [18/24] use_celery (n): y
      [19/24] Select mail_catcher
        1 - None
        2 - Mailpit
        3 - Mailtrap Local
        Choose from [1/2/3] (1): 1
      [20/24] use_sentry (n): y
      [21/24] use_whitenoise (n): n
      [22/24] Select ci_tool
        1 - None
        2 - Gitlab
        3 - Github
        Choose from [1/2/3] (1): 3
      [23/24] Select coding_agent
        1 - none
        2 - claude
        3 - codex
        4 - cursor
        5 - copilot
        Choose from [1/2/3/4/5] (1): 2
      [24/24] debug (n): n

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
