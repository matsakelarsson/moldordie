---
status: accepted
---

# Expose the metrics behind a credential of their own

With `observability=prometheus` the generated project measures itself and has to let a
scraper read the result. Two things about the generated stack decide how. The application is
served on one port, and every deployed environment routes its host to that port for every
path, so an endpoint the application serves is reachable wherever the application is. And
Gunicorn runs `WEB_CONCURRENCY` workers, each with a registry of its own, so a scrape that
reaches one worker describes a quarter of the traffic.

The endpoint is `/metrics`, served by the application, and it takes a bearer credential:
`METRICS_TOKEN`, drawn separately for each deployed environment, compared in constant time
over bytes, with a missing or empty token refusing every request. It answers no session, so
neither an administrator's browser login nor an identity provider's decides whether a scrape
succeeds, and a scraper needs no account. The refusal is 401 naming the scheme, not 403: the
caller presented no usable credential rather than an insufficient one.

One container's workers share `PROMETHEUS_MULTIPROC_DIR`, which
`compose/production/django/start` exports and empties before Gunicorn starts — the variable
has to be set before Python starts, because `prometheus_client` reads it on import — and
`config/gunicorn.py` retires the samples of a worker that has exited. A scrape then describes
the container. It does not describe the deployment: a deployment that scales the application
runs several containers behind the proxy, and the generated `docs/observability.rst` says to
discover every replica rather than to scrape the address in front of them.

## Considered options

- **Deny the path at Traefik and scrape inside the network**: a router per environment, each
  needing its own TLS block, in the three files a deployment with a certificate of its own
  already has to edit. It also decides the topology for the deployment, which the credential
  does not: a token works from inside the network and from outside it.
- **A metrics-only port per worker** (`PROMETHEUS_METRICS_EXPORT_PORT_RANGE`): nothing is ever
  routed, and no multiprocess directory is needed, because each worker is its own target. But
  the targets are a range of ports per container, which collides once the application is
  scaled, and the exporter's thread does not survive the development server's autoreloader.
- **A session, staff-only**: Prometheus cannot log in, and a browser session says nothing
  about whether a machine may scrape.
- **A token-free endpoint**: the exposition names every URL pattern, the errors each returned
  and how long the database took, to anyone who asks.
- **A provider-issued service token**: where the project verifies Entra's or Google's tokens
  already, that is the credential a corporate deployment would rather present. It cannot be
  the only mechanism, because `identity/verification.py` is generated only with Django Ninja
  and a provider; widening it is its own change.

## Consequences

The option adds nothing to Traefik, so a deployment is free to route, block or tunnel the
application as it likes, and none of that is this option's business. A scrape needs one line
of configuration, the credential, wherever it runs. The multiprocess mode the aggregation
needs costs the process, platform and garbage-collection collectors, which describe a process
where the exposition describes a container, and makes a gauge report every live worker unless
it says how to combine them; both are in the generated documentation. The worker processes —
the task worker and, with Celery, its worker and beat — record the same database and cache
metrics but serve no HTTP, so nothing reads them yet.
