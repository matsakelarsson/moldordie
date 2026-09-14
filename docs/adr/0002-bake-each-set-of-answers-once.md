---
status: accepted
---

# Bake each set of answers once per test process

The generation tests used to bake a project per test: every check that runs over the matrix
of supported combinations (rendering, ruff, djlint, the pins, and the three gated style
checks) baked all 28 rows again, and the hand-written tests baked theirs. The `bake` fixture
in `tests/test_cookiecutter_generation.py` now keeps the projects it has generated in the
test process, keyed by the complete answers (the catalogue's defaults filling in what the
test leaves out), and hands every test that bakes the same answers the same tree. The hostile
free-text answers are a key of their own, so a combination has a plain and a hostile bake.

Under pytest-xdist a process is a worker, and a per-worker cache serves a combination's tests
only when they run on the same worker. The tests parametrized over the combinations carry the
combination's name as their `xdist_group`, and `--dist loadgroup`, the default in `addopts`,
runs a group on one worker. The hand-written tests build their answers in their bodies, so
they are not grouped and bake on whichever worker runs them.

A shared tree must not be modified. django-upgrade rewrites in place, so its test copies the
tree first; ruff runs with `--no-cache` so that no `.ruff_cache` lands among the generated
files.

## Considered options

- **A project per test**, the previous state: simple and isolated, but the generation tests
  baked 177 projects for the 28 combinations and the hand-written answers, and the gated
  style job baked the matrix three more times (84 bakes).
- **A per-worker cache alone**: with `-n auto` and xdist's default load scheduling, the
  tests of one combination spread over the workers and nearly every worker bakes it, so the
  bake count hardly drops in the runs CI does.
- **Grouping every test by the answers it bakes**: a group for a hand-written test would be
  written by hand next to answers built in the test body and would go stale silently; they
  bake once per test as before.
- **`--dist loadgroup` on each invocation** rather than in `addopts`: the option is inert
  without `-n`, so the default covers every documented command without changing it.

## Consequences

Serially, the generation tests bake 94 projects instead of 177. With eight workers the
grouped tests bake 28 between them and the hand-written tests add one bake per test on their
worker, 116 in all, and the gated job bakes 28 instead of 84. Bakes are not elapsed time: on
the laptop these counts were taken on, the serial run fell from 78 to 47 seconds, while the
eight-worker run stayed at 30 seconds and the gated job at 24, because the tools that run over
each project dominate them. A test that needs to change a generated tree works on a copy, as
the django-upgrade test does, and a tool run inside a tree must write nothing there. A
hand-written test shares a matrix row's bake only when it lands on that row's worker.
`--keep-baked-projects` keeps the trees under the session's temporary directory, one `bakeNN`
per distinct answers and worker, which is how these counts were taken.
