---
status: accepted
---

# Keep what a process started where its tests can build one

With `observability=opentelemetry`, `telemetry/configure.py` starts a process's exporters from
whichever entry point that process has (`docs/adr/0020`) and stops them where the process can
be reached on its way out. What it had started was a module-level dict, `_started`, that
`configure` filled and `shutdown` emptied, and the generated `tests/test_telemetry.py` reached
into it: fourteen of its twenty-six tests replaced the dict with one holding providers of their
own, and the three tests of the entry points replaced `configure` itself with a list's `append`.
That bound the tests to how each entry point names the function. `apps.py` imports it inside
`ready`, so that a management command never imports the SDK; `config/gunicorn.py` imports it
inside `post_fork`, so that the arbiter imports nothing of the project; `config/celery_app.py`
imports the module, because the worker imports it anyway. The Celery test's docstring explained
which name to patch for which site, the ASGI test replaced `flush` where `asgi.py` had bound it
rather than where it is defined, and `post_fork` was driven by no test at all, because it could
not be patched the same way.

What a process has started is now an object, `Exporters`: the component it exports as and the
two providers holding what it recorded, with the `shutdown` and the bounded `flush` as its
methods. The module keeps one for the process, `exporters`, which `configure` starts and the
module-level `shutdown` and `flush` delegate to; `started` reads its component, as before.
`flushing_on_shutdown` takes the flush it runs as a keyword argument, the process's unless the
caller hands one over. Two small protocols, `Tracing` and `Metering`, state what a shutdown
asks of each provider, which is what a test's recording provider has to answer.

The tests then cross the module's interface and nothing else. A process is started with
`configure` and read back with `started`; each entry point is driven as its process drives it,
`post_fork` included, and read back the same way, with a collector named so that starting would
show; a shutdown is watched on `Exporters` of the test's own, started on providers that record
what they are asked, and the lifespan wrapper is handed that object's flush. One lifespan test
builds the wrapper as `config/asgi.py` does and proves it stops the process's own exporters.
What the tests still replace is the SDK's installation into the process, which has no object to
throw away: the global providers and the instrumentations, recorded rather than installed.

## Considered options

- **Keep the dict and the patches**, and add a `post_fork` test that patches the SDK's
  `configure` where the late import finds it. Rejected: a fourth patching recipe for a fourth
  binding style, and the next entry point would need a fifth.
- **One binding style for the four call sites**, so that one patch reaches them all. Rejected:
  each site's style has a reason the code states, and the lazy import in `ready` is what keeps
  a management command from importing the SDK (`docs/adr/0020`).
- **Pass the providers into `shutdown` and `flush`** instead of keeping them anywhere.
  Rejected: the entry points that stop a process have nothing to pass; what they stop is what
  the process started, which something has to hold.
- **The object**, the choice: the state the tests need is the state the process keeps, built
  the same way, and a test that wants one of its own builds one rather than replacing the
  module's.

## Consequences

An entry point can bind `configure` and `flush` however its site needs, and its test drives the
site and reads `started`. The template-level wiring test still pins that Celery's handler calls
the bounded `flush` rather than `shutdown`, since the generated test observes only that the
process stopped. The `exported` fixture begins by asserting that the process exports nothing,
which the suite guarantees by naming no collector, and ends by stopping what the test started;
a test that left the exporters started fails the next one.
