#!/bin/sh
# this is a very simple script that generates a project and tests its docker configuration
# it is meant to be run from the root directory of the repository, eg:
# sh tests/test_docker.sh

set -o errexit
set -x
set -e

finish() {
  # Your cleanup code here
  docker compose -f docker-compose.local.yml down --remove-orphans
  docker volume rm my_awesome_project_my_awesome_project_local_postgres_data

}
# the cleanup doesn't work in the github actions
if [ -z "$GITHUB_ACTIONS" ]; then
  trap finish EXIT
fi


# create a cache directory
mkdir -p .cache/docker
cd .cache/docker

sudo rm -rf my_awesome_project

# create the project using the default settings in cookiecutter.json
uv run cookiecutter ../../ --no-input --overwrite-if-exists use_docker=y "$@"
cd my_awesome_project

# make sure all images build
docker compose -f docker-compose.local.yml build

docker compose -f docker-compose.local.yml run django uv lock

docker compose -f docker-compose.local.yml build

# the watcher service downloads the Tailwind CLI, builds the stylesheet and stays up:
# Tailwind's CLI stops watching when its standard input closes, which tty: true prevents
docker compose -f docker-compose.local.yml up -d tailwind
waited=0
until [ -s my_awesome_project/static/css/tailwind.css ]; do
  waited=$((waited + 1))
  if [ "$waited" -gt 180 ]; then
    docker compose -f docker-compose.local.yml logs tailwind
    exit 1
  fi
  sleep 1
done
sleep 2
test -n "$(docker compose -f docker-compose.local.yml ps --status running -q tailwind)"

# run the project's type checks
docker compose -f docker-compose.local.yml run --rm django mypy .

# run the project's tests
docker compose -f docker-compose.local.yml run --rm django pytest

# build the stylesheet from the command line, as a deployment does before collectstatic
docker compose -f docker-compose.local.yml run --rm -e DJANGO_SETTINGS_MODULE=config.settings.local django python manage.py tailwind build

# return non-zero status code if there are migrations that have not been created
docker compose -f docker-compose.local.yml run --rm django python manage.py makemigrations --check || { echo "ERROR: there were changes in the models, but migration listed above have not been created and are not saved in version control"; exit 1; }

# Make sure the check doesn't raise any warnings; the placeholders stand in for the
# identity provider's credentials, which the checks report when empty
docker compose -f docker-compose.local.yml run --rm \
  -e ENTRA_TENANT_ID=x \
  -e ENTRA_LOGIN_CLIENT_ID=x \
  -e ENTRA_LOGIN_CLIENT_SECRET=x \
  -e ENTRA_API_CLIENT_ID=x \
  -e GOOGLE_LOGIN_CLIENT_ID=x \
  -e GOOGLE_LOGIN_CLIENT_SECRET=x \
  django python manage.py check --settings=config.settings.local --fail-level WARNING

# Check that message extraction completes and updates the catalogues
docker compose -f docker-compose.local.yml run --rm django python manage.py makemessages --all

# Run the deployment checks against the production settings; the placeholders stand in
# for the deployment's secrets
docker compose -f docker-compose.local.yml run --rm \
  -e DJANGO_SECRET_KEY="$(openssl rand -base64 64)" \
  -e REDIS_URL=redis://redis:6379/0 \
  -e DJANGO_AWS_ACCESS_KEY_ID=x \
  -e DJANGO_AWS_SECRET_ACCESS_KEY=x \
  -e DJANGO_AWS_STORAGE_BUCKET_NAME=x \
  -e DJANGO_ADMIN_URL=x \
  -e MAILGUN_API_KEY=x \
  -e MAILGUN_DOMAIN=x \
  -e ENTRA_TENANT_ID=x \
  -e ENTRA_LOGIN_CLIENT_ID=x \
  -e ENTRA_LOGIN_CLIENT_SECRET=x \
  -e ENTRA_API_CLIENT_ID=x \
  -e GOOGLE_LOGIN_CLIENT_ID=x \
  -e GOOGLE_LOGIN_CLIENT_SECRET=x \
  -e DJANGO_HEADLESS_JWT_PRIVATE_KEY=x \
  -e DJANGO_FRONTEND_ORIGINS=https://app.example.com \
  -e DJANGO_FRONTEND_URL=https://app.example.com \
  django python manage.py check --settings=config.settings.production --deploy --database default --fail-level WARNING

# Generate the HTML for the documentation
docker compose -f docker-compose.docs.yml run --rm docs make html

# Every deployed environment's Compose file is a valid configuration, and Traefik's image
# builds with that environment's routers, selected by the ENVIRONMENT build argument
for environment in dev test production; do
  docker compose -f "docker-compose.$environment.yml" config > /dev/null
  docker compose -f "docker-compose.$environment.yml" build traefik
done

docker build -f ./compose/production/django/Dockerfile -t django-prod .

# the production image carries the stylesheet its build stage built, and not the CLI
docker run --rm --entrypoint sh django-prod -c \
  'test -s /app/my_awesome_project/static/css/tailwind.css && ! ls /app/.django_tailwind_cli/tailwindcss-* > /dev/null 2>&1'

docker run --rm \
--env-file .envs/.local/.django \
--env-file .envs/.local/.postgres \
--network my_awesome_project_default \
-e DJANGO_SECRET_KEY="$(openssl rand -base64 64)" \
-e REDIS_URL=redis://redis:6379/0 \
-e DJANGO_AWS_ACCESS_KEY_ID=x \
-e DJANGO_AWS_SECRET_ACCESS_KEY=x \
-e DJANGO_AWS_STORAGE_BUCKET_NAME=x \
-e DJANGO_ADMIN_URL=x \
-e MAILGUN_API_KEY=x \
-e MAILGUN_DOMAIN=x \
-e ENTRA_TENANT_ID=x \
-e ENTRA_LOGIN_CLIENT_ID=x \
-e ENTRA_LOGIN_CLIENT_SECRET=x \
-e ENTRA_API_CLIENT_ID=x \
-e GOOGLE_LOGIN_CLIENT_ID=x \
-e GOOGLE_LOGIN_CLIENT_SECRET=x \
-e DJANGO_HEADLESS_JWT_PRIVATE_KEY=x \
-e DJANGO_FRONTEND_ORIGINS=https://app.example.com \
-e DJANGO_FRONTEND_URL=https://app.example.com \
django-prod python manage.py check --settings=config.settings.production --deploy --database default --fail-level WARNING
