---
status: accepted
---

# Scaffold a new app from an app template the project checks

A generated project's conventions are many and none of them is Django's default: a view
answers htmx with a partial and the whole page otherwise (`docs/adr/0025`), a template is
written in daisyUI's classes with its class names whole and without inline code, a form
goes through the project's renderer, a model's `get_absolute_url` says how a record is
addressed, imports are absolute and one per line, tests use the project's `page`,
`fragment` and `element` helpers, and mypy runs strict. Django's `startapp` writes an empty
app into the working directory, from which the docs told a developer to move it, edit its
`apps.py` and register it; the conventions were then learned from the users app, or not.
The first app a project adds was the point where the template stopped helping.

The project now has a `startapp` of its own, in `scaffold/`, an installed app that holds
the command and the app template beside it. The app template is a complete app under
placeholder names, `app_template` with a model called `Item`: the model with its first
migration and its admin, a form, the list filtered and paged, the detail, the create and
update forms and the delete confirmation in a dialog, each view answering htmx with a
partial, the templates, a factory, the tests of all of it, and the model's routes on the
REST API when the project has one. The command copies it into the package under the name
given, renaming paths and contents, runs the project's formatters, ruff and djLint, over
the copy, and prints where the app is registered. Nothing edits the settings or the URL
configuration: the command says what to add, where, as the code that goes in, and the
copy's tests pass once it is added.

The app template is not installed. It is checked where it stands, by ruff, mypy and djLint
as any other module of the project, so a convention that changes is changed there and
every app created after follows it. Its tests are not collected (`--ignore-glob` in
`pyproject.toml`), since they need the app installed; they run as the copy's. pytest and
coverage are told the one path to leave alone; mypy and ruff need nothing, since the
placeholder app is a package like any other, with its manager declared on the model so the
type checker reads it without the app being installed.

The renaming is by whole names: `Item` and `item`, `Items` and `items`, `app_template`,
`AppTemplate` and the module path, each replaced where no letter, digit or hyphen precedes
it and no lowercase letter or digit follows, with a hyphen allowed after the lowercase
model name. So `ItemForm` and `item-card` become the new app's while `items-center` and
`join-item`, class names of Tailwind's and daisyUI's, are untouched; the template's own
prose avoids the English word. The text is scanned once, so a name that holds a
placeholder word, `item_tracker`, is put in once and not renamed again. A name the
template uses for something else is refused before anything is copied: a model called
`Page` would rename every record `page`, the test helper that reads a page, and `Filter`
would make the record's form a second `FilterForm`, so the command reads the identifiers
the template's Python binds and the variables its templates name and refuses a name the
renaming would double. After the copy, ruff sorts the imports, whose order within the
package's section depends on how the app's name sorts against the package's other
modules, and formats what a longer name pushed past the line length, and djLint lays out
the attributes a longer name pushed past its limit, as Django's own `startapp` runs black
over what it writes. The formatters are found on the path; without them, or when one
fails, the copy stands and the command says so, and the pre-commit hooks of the first
commit finish it.

## Considered options

- **Django's own `--template`**, a tree of `.py-tpl` files rendered with the app's name.
  Rejected: Cookiecutter renders every file of this repository, so each placeholder would
  need escaping, and nothing would check the sources, which are not Python until rendered.
- **Install the app template under the test settings**, so its tests run in place.
  Rejected: it would need a URL configuration of its own under test, which a developer would
  have to delete from every project, and a model in every project's migration graph.
- **Edit the settings and the URL configuration from the command.** Rejected: the places
  are marked, the edits are two lines, and a command that rewrites `base.py` has to parse it
  or guess; what it would save is less than what a wrong guess costs.
- **Leave the copy's imports to the pre-commit hooks.** Rejected: the first commit would
  fail its hooks and succeed the second time, for every app; running the formatter the
  hooks run, where it is found, is what Django's `startapp` does with black.
- **A complete app under placeholder names, copied and renamed**, the choice.

## Consequences

Every generated project carries the scaffold app and the app template, about thirty files
that are never served, and its tests of the renaming and the command. The removal rules
know the template's REST API arm, so the hook tests and the generation tests check it on
every combination, and the generation tests copy and rename it under a name that sorts
after the package's other modules and run the project's linters on the result. The
integration scripts scaffold an app, register it and run the project's checks with it, so
a convention the app template breaks fails CI. A change to how the project writes a view,
a template or a test is made in the app template too, or the next app does not follow it.
