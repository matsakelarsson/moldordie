# Domain glossary

The vocabulary of this template's generation flow. Use these terms in code, tests, issues and docs; the
noted alternatives are the ones to avoid.

## Option

A question in `cookiecutter.json` and its answer. A **list option** offers choices that Cookiecutter
validates, so the hooks read its answer as given. A **flag option** is a yes/no answer typed as text; the
pre-generation hook lowercases all of them before any file is rendered and rejects anything but `y` or
`n`, so the templates and both hooks read them in one spelling. A **free-text option** takes any text
(project name, description, author, email, domain, version, time zone) and
reaches the generated files through escaping. The answers to all options together are the **context**,
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
