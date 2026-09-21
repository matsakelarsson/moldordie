---
status: accepted
---

# Start telemetry in each serving process

With `observability=opentelemetry` the generated project exports traces and metrics over OTLP,
which means installing a tracer provider and a meter provider on a process and wrapping the
libraries it talks to. Both are global to the process and both cost a background thread, so
where that happens decides what is measured and what is merely slowed down.

`AppConfig.ready` is where a Django project usually wires an SDK up, and it is the wrong place
here. It runs for every management command, so `migrate`, `collectstatic`, `shell`,
`makemigrations` and the test runner would each start exporters, open a connection to the
collector and report as a service instance that answers nothing. Under Celery's prefork pool it
is worse than wasteful: the worker calls `django.setup()` in the parent, so `ready` runs before
the fork, and the batching processor's thread does not survive into the children — the queue
fills and nothing is ever exported.

So `telemetry.configure(component)` is called from the entry point of each process that serves
something, and from nowhere else:

| Process | Call site |
| --- | --- |
| The Gunicorn workers | `post_fork` in `config/gunicorn.py` |
| The Celery workers and the scheduler | `worker_process_init` and `beat_init` in `config/celery_app.py` |
| The task worker and the development server | `TelemetryConfig.ready`, where `DJANGO_TELEMETRY_COMPONENT` names the component |

`post_fork` rather than any later hook, because the Django instrumentation inserts a middleware
into `MIDDLEWARE` and the handler reads that setting once, when it builds its chain: the worker
has to be instrumented after the fork and before it loads the application, and `post_fork` is
the one moment where both hold. The third row is the two processes that have no hook of their
own; their start scripts export the variable, and a management command is told nothing, which
is what keeps `ready` quiet everywhere else.

`configure` starts nothing while `OTEL_EXPORTER_OTLP_ENDPOINT` is empty, and nothing a second
time in a process that has started already. The first is what keeps a checkout, a command and
the generated test suite from dialling anywhere; the second is what makes the three call sites
safe to combine, since a deployment that names a component to a process that also has a hook
would otherwise install a second pair of providers, exporting through neither.

Each process reports as `<component>-<hostname>-<pid>` under one service name, because a
deployment runs several containers of several components, each with workers of its own, and
without that they arrive as one instance and are read as one process.

## Considered options

- **`ready` for everything, guarded on `DEBUG` or on the settings module**: neither says
  whether the process serves. `migrate` in a production container is as much a management
  command as `shell` is on a laptop, and the Celery fork is not a question of environment.
- **The `opentelemetry-instrument` wrapper**: the supported way to start the SDK without code,
  and it does fit the web and Celery commands. It configures from environment variables alone,
  so the settings module stops being the answer to what this project exports; it wraps a
  command rather than a process, so the Celery parent is instrumented along with its children;
  and every start script grows a prefix that is easy to lose. The resource, the endpoint and
  the instrumented libraries are worth having in a module that can be read and tested.
- **A separate settings module per process**: the deployed environments deliberately run one
  production module (`docs/adr/0013`), and which process is running is not configuration.
- **Exporting from the `taskworker` and Celery containers through a scrape instead**: it would
  need an HTTP endpoint in a process that serves none. Pushing is what lets a process that
  nothing can reach still be measured, which is the main thing this option has over
  `observability=prometheus`.

## Consequences

A management command exports nothing, which also means a slow `migrate` leaves no trace to look
at; that is deliberate, and a one-off run can set `DJANGO_TELEMETRY_COMPONENT` to get one. The
web container starts its exporters from a Gunicorn hook, so `compose/production/django/start`
has to pass `--config /app/config/gunicorn.py` for the arm to do anything, and a deployment that
replaces that command loses the traces silently — the generated documentation says where to
look when nothing arrives. Without Docker the development server has no start script, so a
developer names the component themselves. Logs stay on standard output: exporting them is a
separate change, and a log line is worth more with a trace id in it than in a second pipeline.
