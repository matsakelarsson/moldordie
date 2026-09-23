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

This ADR records the binding. Moving the readers over (the hook's rules and secrets table,
the templates) and guarding against a template re-deriving the condition are the next step
(#111).

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
receive. Once a template reads a derived answer (#111), a generation that declines the hooks
fails at that template, since Cookiecutter renders strictly; the template has always needed
its hooks, and that failure is clearer than a half-generated project. Until then the hook's
own `with_headless` and `with_service_tokens` restate the derivation, and nothing ties the
two together but this ADR.
