---
status: accepted
---

# Give the project's package an import section of its own

A generated project has three first-party roots: `config`, the root-level modules
(`merge_production_dotenvs_in_dotenv`, `manage`) and the package named after the project. ruff's
isort sorted all three in one section, by name, so the order of a file importing from two of
them depended on how the project's name sorts. Three files do: `tests/urls.py`, which every
project has, imports `config.urls` beside the package's `htmx`; the metrics tests import
`config.gunicorn` beside the identity app; the production settings test imports the dotenv
merge module beside the identity app. With the default name, `my_awesome_project`, every such
pair happened to sort as written. With a name before `config` — `acme`, `api`, `backend`, most
names — `ruff check` failed on a freshly generated project, and a name between `config` and
`merge` failed on the settings test alone. The suite bakes every combination under the default
name and so never saw it.

The package is now an isort section of its own, `project`, declared in the generated
`pyproject.toml` and placed after `first-party` in the section order. `config` and the root
modules stay first-party, sorted among themselves by names that never change; the package's
imports follow, after a blank line, whatever the package is called. The three files are written
that way, and `test_imports_sort_whatever_the_slug` bakes once with a name that sorts before
`config` and runs ruff on it.

## Considered options

- **Order the imports in the template by comparing the slug**, a Jinja condition per file
  choosing which import comes first. Rejected: isort's order is natural ordering over the
  lowercased name, which a string comparison in a template only approximates, and every new
  file that imports from two roots would need the same condition.
- **Avoid the pairs**, by reaching `config` or the merge module another way in the three files.
  Rejected: the next file to import from two roots would reintroduce the defect, and nothing
  would say so until a project was generated under such a name.
- **Constrain the slug** to sort after the fixed names. Rejected: a template that refuses most
  project names because of its own import order.
- **The section**, the choice: one declaration, no import depends on the name, and a file that
  puts a package import directly after a first-party one fails ruff under the default name too,
  so the existing per-combination ruff tests guard every file.

## Consequences

A file that imports from `config` or a root module and from the package writes the package's
imports as their own block, after a blank line; `ruff check --fix` puts them there. The explicit
`section-order` is required: without it ruff places a custom section elsewhere and reorders
third-party imports around it. The generated guide states the convention; the generation tests
keep baking under the default name, and one test bakes under `acme`.
