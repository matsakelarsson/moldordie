#!/bin/sh
# this is a very simple script that generates a project and runs its checks on bare metal
# it is meant to be run from the root directory of the repository, eg:
# sh tests/test_bare.sh

set -o errexit
set -x

# create a cache directory
mkdir -p .cache/bare
cd .cache/bare

# create the project using the default settings in cookiecutter.json
uv run cookiecutter ../../ --no-input --overwrite-if-exists use_docker=n "$@"
cd my_awesome_project

# Run on the requested interpreter (the project defaults to .python-version)
if [ -n "${PYTHON_VERSION:-}" ]; then uv python pin "$PYTHON_VERSION"; fi
uv run python --version

# Install OS deps
sudo utility/install_os_dependencies.sh install

# Install Python deps
uv sync

# run the project's type checks
uv run mypy .

# run the project's tests
uv run pytest

# return non-zero status code if there are migrations that have not been created
uv run python manage.py makemigrations --check

# Make sure the check doesn't raise any warnings; the placeholders stand in for the
# identity provider's credentials, which the checks report when empty
ENTRA_TENANT_ID=x \
ENTRA_LOGIN_CLIENT_ID=x \
ENTRA_LOGIN_CLIENT_SECRET=x \
GOOGLE_LOGIN_CLIENT_ID=x \
GOOGLE_LOGIN_CLIENT_SECRET=x \
uv run python manage.py check --settings=config.settings.local --fail-level WARNING

# Check that message extraction completes and updates the catalogues
uv run python manage.py makemessages --all

# Run the deployment checks against the production settings; the placeholders stand in
# for the deployment's secrets, the database and Redis come from the environment
DJANGO_SECRET_KEY="$(openssl rand -base64 64)" \
DJANGO_AWS_ACCESS_KEY_ID=x \
DJANGO_AWS_SECRET_ACCESS_KEY=x \
DJANGO_AWS_STORAGE_BUCKET_NAME=x \
DJANGO_ADMIN_URL=x \
MAILGUN_API_KEY=x \
MAILGUN_DOMAIN=x \
ENTRA_TENANT_ID=x \
ENTRA_LOGIN_CLIENT_ID=x \
ENTRA_LOGIN_CLIENT_SECRET=x \
GOOGLE_LOGIN_CLIENT_ID=x \
GOOGLE_LOGIN_CLIENT_SECRET=x \
uv run python manage.py check --settings=config.settings.production --deploy --database default --fail-level WARNING

# Generate the HTML for the documentation
cd docs && uv run make html
