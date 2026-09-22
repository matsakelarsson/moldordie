# Domain glossary

The vocabulary of this template's generation flow. Use these terms in code, tests, issues and docs; the
noted alternatives are the ones to avoid.

## Option

A question in `cookiecutter.json` and its answer. A **list option** offers choices that Cookiecutter
validates, so the hooks read its answer as given. A **flag option** is a yes/no answer typed as text; the
pre-generation hook lowercases all of them before any file is rendered and rejects anything but `y` or
`n`, so the templates and both hooks read them in one spelling. A **free-text option** takes any text
(project name, description, author, email, domain, version, time zone) and
reaches the generated files through escaping. The **catalogue**, `OPTIONS` in `local_extensions.py`, reads
`cookiecutter.json` and tells each option's kind from its declaration alone: a list of choices, a `y`/`n`
default, or any other text. The tests import it; the hooks, which run as standalone scripts, receive the
names by kind through the `option_names` Jinja global. A **derived answer** is a name that follows
from the answers and is not one: `headless` (Django Ninja with an identity provider) and
`service_tokens` (a provider whose tokens something reads), computed as booleans by `derived_answers`
in `local_extensions.py` and bound by the pre-generation hook before any file renders; never
prompted, not in the catalogue, absent from the replay file, and read by name wherever a template
or the post-generation hook needs the concept (`docs/adr/0022`). The answers to all
options together, with the derived answers, are the **context**, which each hook receives once, as
JSON, at its entry point, so a free-text answer cannot break the hook's source.

_Avoid_: variable, setting, feature flag.

## Escaping

How a free-text answer is written into a generated file: at every site where the answer sits inside
delimiters, through the filter for that file's syntax. `string_escape` in `local_extensions.py`, which
Cookiecutter loads through `_extensions` in `cookiecutter.json`, backslash-escapes for Python, TOML,
YAML double-quoted scalars and gettext `.po` strings, taking the delimiter as its argument when it is
not `"`. Jinja's `e` escapes for HTML. Prose files (README, LICENSE, `.rst`, `.po` comments) take the
answer as is. The pre-generation hook rejects the two things escaping cannot fix: control characters in
any free-text answer, and anything but letters, digits, dots, hyphens and underscores in the domain
name, which Traefik's `Host()` rules embed with no escape.

_Avoid_: sanitising, quoting; a `replace` chain written at the site.

## Environment

One configuration of the generated project, named by a directory of env files under `.envs` and,
except for `local`, by a `docker-compose.<name>.yml` in the project root. `local` is the
developer's machine. The **deployed environments** are `dev`, `test` and `production`, in the
order a change is promoted through them: each builds its images from `compose/production/` and
runs `config/settings/production.py`, which its `.django` file names in
`DJANGO_SETTINGS_MODULE`, so what an environment owns is its variables — its hosts, its own
secrets, the deployment it reports as — and its Traefik routers, one file per environment
selected by the image's `ENVIRONMENT` build argument (`docs/adr/0013`). A settings module is not
an environment: `config/settings/test.py` is the settings the generated suite runs under, and no
deployment uses it. No env file is in version control, so what a deployment supplies is declared
in the **example**, `.env.example`: the production env files merged with every drawn value left
unset, written by the hook before the secrets are filled (`docs/adr/0014`). In the template, a
deployed environment's files are stubs that name their environment and include the **shared
source** for their kind: the `templates` directory at the repository root, which Cookiecutter
reads and never renders as output, holding one source per kind of file (the Django and Postgres
env files, the Compose file, the Traefik routers) and one table of what an environment differs
in (`docs/adr/0023`).

_Avoid_: stage, tier, staging (for `test`); a settings module per deployment; treating the
example as a file to edit by hand; adding a variable to one environment's stub.

## Secret

One row of `SECRETS` in `hooks/post_gen_project.py`: a value drawn once when the project is generated,
the placeholder (`!!!SET NAME!!!` in a template file) it replaces, and the files it is written to. A
value the environments share is one row naming every file it goes to; the same placeholder in several
rows is drawn afresh for each, so nothing else is shared. A value each deployed environment draws for
itself is declared once, through `per_deployed_environment`, and is one row per deployed environment in
the table `fill_secrets` reads. The row also says whether `debug` replaces the value
with `debug` (the credentials, not the keys) and, for a placeholder the template renders only for some
answers, the condition. `fill_secrets(root, context)` writes them before pruning; a file or placeholder
it cannot find is an error.

_Avoid_: flag (a kind of option; the placeholders' old name), setter, `set_*` helper.

## Removal rule

One row of `REMOVALS` in `hooks/post_gen_project.py`: a condition over the context, and the template
paths that are deleted when it holds. Paths are relative to the generated project's root, with
`{project_slug}` standing for the project package. For any context, no path is listed twice or under
another listed path, so the rules can be applied in any order; `tests/test_hooks.py` checks this over
every combination of the answers the rules read, and that every listed path exists in the template.
The rules are also the statement of what the supported combinations must reach: a combination
**keeps** a path when no rule that holds for its context lists the path or a directory above it,
and every listed path is kept by some combination; and, per combination, of what the rules
removed from its project, which no generated file may cite (`docs/adr/0021`).

_Avoid_: manifest, cleanup function, `remove_*` helper.

## Prune

Applying the removal rules to a generated project, then the cleanup steps that depend on what is left
in the tree. Lives in `prune(context, root)`. Pruning only deletes: a target that is missing is an
error, and content changes (secrets, `.gitignore` lines) happen in `main`, not here.

_Avoid_: cleanup, post-processing.

## Channels cleanup

The one tree-dependent step of pruning, `remove_channels_tests`: when `realtime` is not `channels`,
the websocket test goes, and the project-level tests package goes with it only if nothing but its
`__init__.py` is left. It is a step rather than a removal rule because whether the package goes depends
on which other tests the context kept there.

_Avoid_: describing it as a removal rule.

## Agent guide

The generated project's instructions for AI coding agents: the answers it was generated from,
its commands, its layout and its conventions, rendered from one template file. Which coding
agent reads it is the `coding_agent` answer, and each reads it under its own name, so the hook
moves the rendered file there after pruning (`AGENT_FILES` and `place_agent_guide`,
`docs/adr/0015`); `none` deletes it through a removal rule. The guide describes the tree that
was generated, never the options it was generated from: its table of choices is a record, and
everything else names what is actually there.

_Avoid_: instructions file, CLAUDE.md or AGENTS.md (one agent's name for it), rules.

## Bake

Generating one project in the tests from a complete set of answers, through the `bake` fixture
in `tests/test_cookiecutter_generation.py`, which returns the reader. The **complete answers**, the
catalogue's defaults filling in what the test leaves out and the derived answers bound on top
(`complete_answers` in `tests/answers.py`), are baked once per test process, and
every test that bakes them gets the same tree, so no test modifies it: a tool that rewrites
files runs on a copy. The hostile free-text answers are a bake of their own. Under xdist a
process is a worker: the tests parametrized over the combinations are grouped so that one
worker runs a combination's, and the hand-written tests bake on the worker that runs them
(`docs/adr/0002`). The **supported combinations** are the rows every matrix-wide check bakes;
between them they keep every path a removal rule lists (`docs/adr/0021`).
`scripts/compare_generated.py` bakes outside the tests, a Cookiecutter process per project and
revision, to compare the trees two revisions generate.

_Avoid_: generating a project per test; result (pytest-cookies' object, which the fixture keeps
to itself); effective answers (for the complete answers).

## Reader

The view of a generated project that the tests use to locate files and inspect their contents:
`GeneratedProject` in `tests/generated_project.py`, with `PythonModule` for what a Python file
binds at module scope, read from its source alone (`docs/adr/0001`). Expected behaviour belongs
to the tests: the reader asserts nothing, makes no existence check and validates no tree.

---

The vocabulary of the generated project's server-rendered frontend: its stylesheets, its themes
and its examples page. The terms of the generation flow above still apply; in particular "context" alone is
the answers the hooks receive, and Django's is the **template context**.

## Source stylesheet

The CSS a developer writes and the Tailwind CLI reads: `styles/main.css` in the project package,
which imports Tailwind CSS, enables daisyUI and names the files whose class names count. It is
committed, and sits outside the static directories.

_Avoid_: input CSS, Tailwind config, main stylesheet.

## Built stylesheet

What the Tailwind CLI writes from the source stylesheet and the class names it finds:
`static/css/tailwind.css`. An artefact: never generated, never committed, rebuilt by the watcher
in development and built into the production image.

_Avoid_: output CSS, bundle, compiled CSS.

## Theme

A daisyUI theme, by name: a complete set of the colours, radii, sizes and effects daisyUI reads,
applied to everything under an element carrying `data-theme`. The ones daisyUI ships are enabled
next to the own theme, and `THEMES` names those a visitor may choose.

_Avoid_: skin, colour scheme, style; "dark mode" for a dark theme.

## Own theme

The project's daisyUI theme, `brand`: a theme block in the source stylesheet with every value
daisyUI reads written out, and the default look. It is the style example: changing the
project's look means editing it, not overriding daisyUI's classes.

_Avoid_: custom theme, default theme (any theme can be made the default), skin.

## Theme picker

The control in the navigation for choosing a theme: a radio button per theme, which restyles
the page through daisyUI's CSS as soon as it is checked, and an htmx request that keeps the
choice in a cookie, from which the server writes `data-theme` on the next page.

_Avoid_: theme switcher, theme toggle, dark mode switch.

## Examples page

The page, routed in every environment and linked from the navigation, that shows daisyUI
components and htmx patterns as the project writes them: each example a template under
`templates/examples/`, rendered live and shown as written. It is starter content, which a
project deletes once it has pages of its own.

_Avoid_: style guide, storybook, demo, component library.

## Watcher

The development process that rebuilds the built stylesheet whenever a scanned file changes:
`manage.py tailwind watch`, a second terminal without Docker, the `tailwind` service with it. No
deployed environment runs one.

_Avoid_: dev server (Uvicorn is), build (the one-off `tailwind build`).

## Partial

A named `partialdef` block of a Django template, addressed as `template.html#name`. It
need not belong to a page template.

_Avoid_: snippet, include.

## Fragment

The HTML a view returns when it selects partial rendering for an eligible request. A
non-boosted htmx request does not guarantee one; `htmx_fragment` in the template context
marks the choice.

_Avoid_: partial response.

## Template context

Django's rendering context, always so qualified. Unqualified, "context" is the answers the
hooks receive.

_Avoid_: context (unqualified) for Django's.
