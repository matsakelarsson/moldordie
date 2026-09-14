---
status: accepted
---

# Read generated settings from source

The generation tests need what a generated settings module binds: the apps and middleware
`base.py` lists, the context processors, the default `local.py` and `test.py` give the secret
key. The reader (`PythonModule` in `tests/generated_project.py`) reads each file from its source
alone, resolving the small subset of Python its docstring lists and failing explicitly outside
it: no generated module is imported, `from .base import *` is not followed, and an environment
module answers only for what it binds itself. The subset is deliberately closed: a case outside
it gets an explicit failure, not an extension of the evaluator.

## Considered options

- **Import each module under a fake environment**, with `env` pointing at made-up values, and
  read the effective settings back. Rejected: it makes Django and every package a settings
  module imports (Sentry, Channels, storages) a test dependency of this repository, runs the
  module's side effects (`sentry_sdk.init` in production), and hides which file a value came
  from.
- **Layer `base.py` under each environment module**, resolving it first and letting `local.py`,
  `test.py` and `production.py` see its names. Rejected: it is a second evaluator of the star
  import, it has to model what an environment module does to an object `base.py` built
  (`SECURE_CSP["connect-src"] = [...]`), and no assertion so far needs an inherited setting.

## Consequences

An assertion on a setting a module inherits is written against the file that binds it, or stays
textual on the module's source. Reopen this decision when an assertion needs the effective
contents of an inherited setting; Django becoming a dependency of this repository for another
reason is not, by itself, a reason to.
