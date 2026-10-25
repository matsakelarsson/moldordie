---
status: accepted
---

# Index the generated layout in the repository guide

`AGENTS.md` at the repository root is what a coding agent reads before changing the template.
Its "Generated Project Layout" section listed the generated project's files, and for each one
said how it works: what a module binds, which hook calls what, why a stylesheet sits where it
does, what each test asserts and why. That is the mechanism, restated. On 2026-09-13 the guide
was 10 KB with a 2 KB layout section; by 2026-09-22 it was 40 KB with 17 KB of layout; at the
time of this decision 45 KB with 19 KB, the section's bullets up to 2 KB each. Of the 36 commits
since the 2026.9.20 release, 26 changed the guide. The five fix pull requests of the
observability review (#94 to #98) changed the telemetry's shutdown, the Gunicorn hooks and the
verifier's discovery, each of them a mechanism the section described, and none of them changed
one line of it: a reader of the section after those merges read how the code used to work.

A mechanism restated in a second place goes stale in that place, and the section was the second
place for everything in it. Each thing it said is written where it lives: the module's docstring
(`telemetry/configure.py`, `identity/verification.py`, `metrics.py`, `themes.py`, the tests),
the leading comment of a template (`base.html`, `partials/navigation.html`, the form and allauth
templates), the comment at a settings block (`config/settings/base.py`), the generated
`docs/frontend.rst`, `docs/authentication.rst` and `docs/observability.rst`, and the generated
agent guide, whose tables the generation tests check against the tree. The reasons are in the
decisions, cited by number, and the terms in `CONTEXT.md`. Nothing checks the repository guide
against anything, which is why it could drift.

The section is now an index. A row names what a path holds, the answer that keeps it where there
is one, and where it is explained, and nothing else; a mechanism is read where it lives, and a
row changes only when a path or a pointer does. The section fell from 19 KB to 7 KB and the guide
from 45 KB to 32 KB with no mechanism lost: every claim the old bullets made was found in one of
the places above before the bullet was cut.

## Considered options

- **Keep the section and maintain it**, treating the five pull requests as lapses. Rejected: a
  description of a mechanism in a file that no test reads will lapse again, and the agent guide
  of the generated project already shows what it takes to keep one honest — a test per table.
- **Delete the section.** Rejected: an agent changing the template needs the map, which answer
  keeps which path, and where to read before touching one. The index is that map.
- **Move the descriptions into the repository's `docs/`.** Rejected: the same second place under
  another name, read by fewer.
- **Test the guide against the tree**, as the generated one is tested. Rejected for prose: the
  generated guide's tables are checked because they are tables; a sentence about how a flush is
  bounded has nothing a test can hold it to short of the code itself, which is where it should be.

## Consequences

An agent reads the index, then the docstring, the comment or the generated document the row
points at; the guide no longer answers a question about a mechanism on its own. A change that
moves a mechanism updates the docstring that explains it and leaves the guide alone, unless a
path or a pointer moved. A new file in the generated project gets a row: its path, the answer
that keeps it, and the docstring or document that explains it, which it therefore has to have.
The "Test Structure" section above it describes this repository's own tests, which no generated
file documents, so it stays prose, and is now the guide's largest section.
