---
status: accepted
---

# Derive what the rows must reach from the removal rules

Every check that runs "over the matrix" (the hostile free-text answers, leftover Jinja,
unfilled placeholders, the parsers, ruff, djlint, the removed-frontend scan) assumes that
some supported combination generates every file the template can generate. Nothing enforced
that. The rows were derived for single choices only, one per choice of every list and flag
option, and a file that exists only for a pair of answers was reached if someone remembered
to write a paired row. On 2026-09-21 one path was kept by none of the 44 rows: the
development Prometheus receiver, `compose/local/prometheus`, which exists only with
`observability=prometheus` and `use_docker=y`. No matrix-wide check had ever rendered it.

The removal rules already state, as a table the tests import, which generated paths depend
on the answers. That table is now the statement of what the rows must reach: every path a
removal rule lists is kept by at least one supported combination
(`test_every_removable_path_is_baked`). A row keeps a path when no rule that applies to the
row's complete answers lists the path or a directory above it; the second half matters
because the rule for no Docker removes the whole `compose` directory, which other rules list
paths under. The computation is a pure function over rules and answers
(`tests/removal_coverage.py`), tested on hand-written rules, and it needs no bake: a rule
whose paths no row keeps fails in milliseconds, and the failure names each path with the
smallest supported row that would keep it.

Coverage is file-level. The rules say which paths exist for which answers, and nothing about
the conditionals inside a file that is kept, so whether every `{% if %}` of a kept file is
rendered by some row is not checked. Checking that was a candidate of the 2026-09-13 review
and was declined; this decision does not reopen it.

The CI integration rows are held to the same table
(`test_every_removable_path_is_generated_by_some_ci_row`). On 2026-09-21 none of the 14 rows
passed `use_sentry=y`, so CI had never type-checked or run the generated Sentry app, and none
reached the nginx image of a Docker project without a cloud provider; the same day, rows that
had been replaced rather than added were restored (#98), because Celery was by then exercised
only together with an observability arm. A row's complete answers are the defaults, then the
answers its script passes to Cookiecutter itself (`use_docker`), then its own, so the coverage
computed is that of the projects CI really generates. Coverage is bought with answers on
existing rows, not with jobs: the `Basic` Docker row and the `Celery` bare-metal row stay the
plain cases, and a job is added only where widening a row would hide which answer a failure
belongs to. Paths that nothing the integration scripts run reads are exempted by hand, each
with its reason (the GPL's text, the agent guide), and an exemption that a row makes
unnecessary, or whose path no rule lists any more, fails.

What "a CI row reaches a path" proves is narrow, in the terms of ADR 0004: the checks of that
row's script ran on a project that has the path. It does not show that those checks execute
the file, or that a service it configures works.

## Considered options

- **Hand-kept paired rows under a comment**, the previous state: the comment above
  `PAIRED_COMBINATIONS` listed the answers that only show their effect together, and the
  receiver sat unreached under it from the day it was added.
- **Deriving the rows from the rules**: left out of scope. The conditions are opaque
  functions, so a row can only be found by searching the answers; the rows stay hand-written,
  the test says when one is missing, and the search runs only to word that failure.
- **Condition-level coverage**: see above.
- **A CI job per arm**: every job generates, installs and checks a whole project to reach
  paths that an answer on an existing row reaches as well. Jobs are for answers whose
  failures would otherwise be hard to tell apart.

## Consequences

A contributor's new removal rule demands its row by itself, and the failure says which
answers to write. The paired row `observability=prometheus` with `use_docker=y` was added
for the receiver; every matrix-wide check passed on it as it stood. A byte-identical
comparison over the supported combinations (`scripts/compare_generated.py`) is now evidence
about every file a removal rule can delete. It still says nothing about a fork inside a
kept file that no row reaches; those answers are passed to the comparison as extra rows.
The Channels cleanup is a step of pruning, not a rule, so its paths are outside this check;
the single-choice rows reach them. In CI, `use_sentry=y` rides on Docker's Channels row and on
bare metal's Celery and OpenTelemetry row, and `cloud_provider=None` with WhiteNoise on Docker's
Entra and Django Ninja row. The check is per path, not per row: narrowing the nginx row, or
both Sentry rows, fails it, naming the paths that lost their last row; narrowing one Sentry
row passes, since the other still keeps the Sentry app.
