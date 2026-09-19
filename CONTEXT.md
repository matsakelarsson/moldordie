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
names by kind through the `option_names` Jinja global. The answers to all options together are the **context**,
which each hook receives once, as JSON, at its entry point, so a free-text answer cannot break the
hook's source.

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
unset, written by the hook before the secrets are filled (`docs/adr/0014`).

_Avoid_: stage, tier, staging (for `test`); a settings module per deployment; treating the
example as a file to edit by hand.

## Secret

One row of `SECRETS` in `hooks/post_gen_project.py`: a value drawn once when the project is generated,
the placeholder (`!!!SET NAME!!!` in a template file) it replaces, and the files it is written to. A
value the environments share is one row naming every file it goes to; the same placeholder in several
rows is drawn afresh for each, so nothing else is shared. The row also says whether `debug` replaces the value
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
in `tests/test_cookiecutter_generation.py`, which returns the reader. The complete answers, the
catalogue's defaults filling in what the test leaves out, are baked once per test process, and
every test that bakes them gets the same tree, so no test modifies it: a tool that rewrites
files runs on a copy. The hostile free-text answers are a bake of their own. Under xdist a
process is a worker: the tests parametrized over the combinations are grouped so that one
worker runs a combination's, and the hand-written tests bake on the worker that runs them
(`docs/adr/0002`).

_Avoid_: generating a project per test; result (pytest-cookies' object, which the fixture keeps
to itself).

## Reader

The view of a generated project that the tests use to locate files and inspect their contents:
`GeneratedProject` in `tests/generated_project.py`, with `PythonModule` for what a Python file
binds at module scope, read from its source alone (`docs/adr/0001`). Expected behaviour belongs
to the tests: the reader asserts nothing, makes no existence check and validates no tree.

---

The vocabulary of the generated project's frontend: the UI library, its components and its
theme. The terms of the generation flow above still apply; in particular "context" alone is
the answers the hooks receive, and Django's is the **template context**.

## Component

A reusable piece of the generated UI library: a Cotton template under `templates/cotton/ui/`,
invoked as `<c-ui.name>`. It declares the inputs it consumes, renders in an isolated template
context, fills its slots with the caller's markup and forwards the attributes it does not
declare to its documented element.

_Avoid_: element (allauth's unit), widget (Django's form control), partial.

## Slot

Markup a caller hands a component: its content as the default slot, or a named `<c-slot>`.
Rendered in the caller's template context before the component sees it.

_Avoid_: block (template inheritance), child.

## Forwarded attribute

An attribute a component was given but did not declare, written onto its element by the
`ui_attrs` filter under the attribute contract in `ui/attrs.py`.

_Avoid_: passthrough, rest attributes.

## Token

A named design value of the UI library, a CSS custom property with the `--ui-` prefix. The
colour tokens are owned by the palettes in Python and served by the theme stylesheet; the
others live in `static/css/ui/tokens.css`.

_Avoid_: variable.

## Palette

A named, complete set of colour token values in both the light and the dark set: `blue`,
`teal` or `violet` in `ui/palettes.py`. Every palette meets the adjacency table, the pairs
of tokens that meet on the page with the contrast ratio AA asks of each.

_Avoid_: theme, scheme, skin.

## Mode

Which colour set applies: `system`, the browser's preference, or `light` or `dark` forced.

_Avoid_: theme, dark mode as a palette.

## Brand

The overrides a deployment or a company gives the tokens a brand may change, per colour
set, never the status tokens; `UI_BRAND` in the settings is the deployment's. A brand is
valid only together with the palette beneath it, since the adjacency table checks the
result.

_Avoid_: custom theme, skin.

## Theme

Both resolved colour sets of one request, light and dark, plus the mode it asked for: the
palette with the brand over it and, in development, the preview; computed by
`resolve_theme` in `ui/themes.py` and served as `/ui/theme.css`. Python does not decide
which set the browser shows when the mode is `system`.

_Avoid_: palette, style.

## Preview

A palette, a mode and partial colour overrides chosen in the showcase, validated and kept
in the development session. Resolved against the current palettes and brand on each
request, never stored as a finished theme; one that no longer resolves is dropped.

_Avoid_: draft, snapshot.

## Showcase

The development-only page at `/ui/components/` that renders every component and its states
from example templates it also shows as written, with the sample form and the preview form.

_Avoid_: style guide, storybook, demo.

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
