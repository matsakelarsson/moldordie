---
status: accepted
---

# Bind the derived answers once, before any file renders

Two concepts run through the template and belong to no part of it. **Headless** is Django
Ninja with an identity provider: when allauth's headless login, the app-issued tokens and the
frontend contract are generated. **Service tokens** is an identity provider whose tokens
something reads, Django Ninja's routes or the metrics endpoint: when the verifier and the
service registrations are generated (ADR 0019). ADR 0019 defines them in prose and the
post-generation hook names them as two functions; the templates had no home for them, so
each file that needed one retyped the boolean expression. Counted on 2026-09-21: 36
spellings, several of them half the concept and true only because a removal rule deletes
the file in the other case. When service tokens widened from Django Ninja to Django Ninja or
Prometheus, the change edited nine files.

The two concepts are **derived answers**: names bound once from the answers, before any
file is rendered, in the place where the answers are already normalised. `derived_answers`
in `local_extensions.py`, beside the catalogue, takes the answers and returns them as
booleans. The pre-generation hook's Jinja preamble, which already trims two answers and
lowercases the flags, calls it last and updates the context with the result. From there the
names reach every template and the JSON the post-generation hook receives. The catalogue's
extension registers the function as a Jinja global, as it does `option_names`, so the hook,
which runs as a standalone script, can reach it. A derived answer is not an option: it is
never prompted, it is not in the catalogue, and it is not in the agent guide's table of
choices or in Cookiecutter's replay file, which Cookiecutter writes before the hooks run, so a
replay recomputes them from the replayed answers. This was run once on a scratch template
(Cookiecutter 2.7.1): the templates read the booleans, the post-generation hook's context
carries them as booleans, an interactive generation asks the catalogue's 25 questions and
nothing more, the replay file holds no derived key, and a replay generates the same project.

The values are booleans so that a template reads `if headless` and the hook reads the same
value after the JSON hand-over, without comparing strings. A condition becomes a derived
answer when it combines two or more answers and is read by files of more than one kind, the
hook among them; a condition one file needs stays a name at that file's top.

Every reader then moved over. The post-generation hook's removal rules and secrets table
read `headless` and `service_tokens` from the context they are handed, and its two predicate
functions went; the rules stayed lambdas over the context and the table a table. Every
template site reads the derived answer: a file that bound one of the names at its top keeps
the local name and binds it from the derived answer, as ADR 0005 asks of the settings
modules, so its body did not change; an inline compound condition became the name; the
half-expressions (a name bound to "a provider" or to "Django Ninja" alone, true only because
a removal rule deletes the file otherwise) became the name too, the two being equal within
those files. The observability page's narrower condition, that the scrape may present a
calling service's token, got a local name of its own, `scrape_tokens`, written in terms of the
derived answer, so `service_tokens` means one thing everywhere. The deployed env files'
conditions were edited once, in the shared source (ADR 0023). A guard test over the text of
the project template and the shared source fails when a tag combines the identity provider
with the REST API or with observability, or binds one of the two names to anything but the
derived answer. It recognises the spellings that existed, a statement tag naming both
answers or a binding of the name; a condition split over a local name or spread over nested
tags is beyond a text guard. The generated projects did not change by a byte: `scripts/compare_generated.py` over every supported combination, plain and hostile,
all 90 the same.

## Considered options

- **Private double-underscore variables in `cookiecutter.json`**: rendered in declaration
  order and never prompted, but a value arrives as the string `'True'`, lands in the replay
  file, and puts the expression into JSON as Jinja.
- **An import from the shared-template directory**: reaches the templates but not the
  hooks, which render without a loader.
- **Per-file bindings**, the state before: 36 spellings, some of them half the concept.
- **Deriving in the post-generation hook alone**: the templates cannot see it.

## Consequences

The tests complete a row's answers the way generation does, through `complete_answers` in
`tests/answers.py`: the catalogue's defaults, the row's answers, then the derived answers
from the same function. A context in a test is therefore a context the hook could really
receive. A generation that declines the hooks fails at the first template that reads a
derived answer, since Cookiecutter renders strictly; the template has always needed its
hooks, and that failure is clearer than a half-generated project. The hook tests' guarded
contexts enumerate every combination of the options the rules read, with the derived answers
computed for each, and still fail on a read of anything else.
