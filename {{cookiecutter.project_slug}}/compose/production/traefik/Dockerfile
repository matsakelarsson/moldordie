FROM docker.io/traefik:v3.7.13
# The deployed environment this image routes for. Its routers, which name the hosts the
# environment answers for, are the one piece of the configuration that differs between
# dev, test and production; each environment's Compose file passes its own name here.
ARG ENVIRONMENT=production
RUN mkdir -p /etc/traefik/acme \
  && touch /etc/traefik/acme/acme.json \
  && chmod 600 /etc/traefik/acme/acme.json
COPY ./compose/production/traefik/traefik.yml /etc/traefik/traefik.yml
COPY ./compose/production/traefik/dynamic/shared.yml /etc/traefik/dynamic/shared.yml
COPY ./compose/production/traefik/dynamic/${ENVIRONMENT}.yml /etc/traefik/dynamic/routers.yml
