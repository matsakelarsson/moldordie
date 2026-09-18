# Maintainer guide

This document is intended for maintainers of the template.

## Automated updates

Dependabot keeps the template's own Python deps, the GitHub actions and the Docker images up to date; its config is in `.github/dependabot.yml`.

Nothing updates the generated project's Python deps automatically. They are pinned in `{{cookiecutter.project_slug}}/pyproject.toml`, which is a Jinja template that Dependabot cannot parse, so bump them by hand. cookiecutter-django used PyUp for this; the fork does not, and the `.pyup.yml` it left behind pointed at `requirements/*.txt` files that no longer exist.

Three of those pins — `ruff`, `djlint` and `django-upgrade` — also appear in the template's own `pyproject.toml` and `uv.lock` and in the generated project's `.pre-commit-config.yaml`, because the template's test suite lints the generated output with them; `ruff` is in the template's own `.pre-commit-config.yaml` as well. The generated project's pin is the source of truth: `align-versions.yml` copies it to the other places whenever a pull request changes `{{cookiecutter.project_slug}}/pyproject.toml`. Dependabot is told to ignore those three so it cannot bump them out of step.

The Tailwind CLI is one more pin. `TAILWIND_CLI_VERSION` in `{{cookiecutter.project_slug}}/config/settings/base.py` names a release of [`dobicinaitis/tailwind-cli-extra`](https://github.com/dobicinaitis/tailwind-cli-extra/releases), the standalone Tailwind CLI with daisyUI bundled: the number is that repository's own, and its release notes say which Tailwind CSS and which daisyUI it carries. Nothing watches it, here or in a generated project, because it is a string in a settings module and a release asset rather than a package. To bump it, pick a release within Tailwind CSS 4 and daisyUI 5 (a new major of either is a change to the template, not a bump), check that it ships the `linux` and `macos` assets for `x64` and `arm64`, change the setting and the comment above it, and run both integration scripts, which download the binary and build with it. The setting is the only place the version is written; bump `django-tailwind-cli` in the generated `pyproject.toml` with the other pins.

Updates for the template should be labelled as `project infrastructure` while the ones about the generated project should be labelled as `update`. This is use to work in conjunction with our changelog script (see later).

## Automation scripts

We have a few workflows which have been automated over time. They usually run using GitHub actions and might need a few small manual actions to work nicely. Some have a few limitations which we should document here.

### CI

`ci.yml`

The CI workflow tries to cover 2 main aspects of the template:

- Check all combinations to make sure that valid files are generated and pass `ruff check` and `djlint --lint`: the `tests` job, on three Python versions. The `auto-fixable` job checks, on one, that `ruff format`, djlint's formatter and `django-upgrade` would change nothing in the generated output; those tests run only with `AUTOFIXABLE_STYLES=1`, and the job selects them by their `auto_fixable` marker.
- Run more in-depth tests on a few combinations, by installing dependencies, running type checker and the test suite of the generated project, and building its stylesheet with the Tailwind CLI. We try to cover docker (`docker` job) and non-docker (`bare` job) setups.

We also run the deployment checks, but we don't do much more beyond that for testing the production setup.

### Align versions

`align-versions.yml`

Runs `scripts/python_dependency_version.py` for `ruff`, `djlint` and `django-upgrade` on every pull request that touches `{{cookiecutter.project_slug}}/pyproject.toml`, and commits the result back to the branch. Each run reads the version the generated project pins, writes it into the template's own `pyproject.toml` and into both `.pre-commit-config.yaml` files (the template's own has only a `ruff` hook, so for `djlint` and `django-upgrade` that write changes nothing there) and refreshes `uv.lock`, so a pin only ever has to be edited in one place.

#### Limitations

- Pushing back to the branch needs a `GH_PAT` secret. Without one the workflow falls back to the default token, whose pushes do not re-trigger CI, and it cannot push to a pull request opened from a fork at all.

### Regenerate uv.lock

`dependabot-uv-lock.yml`

Runs `uv lock` and commits the result on Dependabot pull requests that change the template's `pyproject.toml`, since Dependabot's uv support updates the manifest but not the lock file. It has the same `GH_PAT` limitation as the workflow above.

### Django issue checker

`django-issue-checker.yml`

This workflow checks whether a new major version of Django (not in the pure SemVer sense) has been released that we are not running, and lists our dependencies' compatibility with it.

It opens an issue in this repository holding a compatibility table and keeps it up to date on each run. The workflow is `workflow_dispatch` only: it was inherited from cookiecutter-django, where it ran daily, and the schedule was removed rather than pointed at this tracker without asking. Restore the `schedule:` trigger to turn it back on.

#### Limitations

Here are a few current and past limitations of the script

- ~~When a new dependency is added to the template, the script fails to update an existing issue~~
- Not sure what happens when a deps is removed
- ~~Unable to parse classifiers without minor version~~
- ~~Creates an issue even if we are on the latest version~~

### Issue manager

`issue-manager.yml`

A workflow that uses [Sebastian Ramirez' issue-manager](https://github.com/tiangolo/issue-manager) to help us automate issue management. The tag line from the repo explains it well:

> Automatically close issues or Pull Requests that have a label, after a custom delay, if no one replies back.

It runs on a schedule as well as when some actions are taken on issues and pull requests.

We wait 10 days before closing issues labelled `needs-info` or `wontfix`, with a message for each, configured in the workflow itself.

### Pre-commit auto-update

`pre-commit-autoupdate.yml`

Run daily, to do `pre-commit autoupdate` on the template as well as the generated project, and opens a pull request with the changes.

#### Limitations

- The PR is open as GitHub action which means that CI does NOT run. The documentation for create-pull-request action [explains why](https://github.com/peter-evans/create-pull-request/blob/main/docs/concepts-guidelines.md#triggering-further-workflow-runs).
- Some hooks are also installed as dependencies of the generated project (in its `dev` dependency group). Those pins are bumped by hand and mirrored by `align-versions.yml`, so this workflow leaves them alone: it passes `--repo` for only the hooks nothing else owns.

### Update changelog

`update-changelog.yml`

Updates the changelog and creates a GitHub release. `workflow_dispatch` only, for the same reason as the Django issue checker above; adding a `schedule:` trigger is safe, since a run with nothing to release exits without writing anything. It runs a custom script which:

- Lists every pull request merged since the previous release, so a manual run picks up whatever has accumulated however long ago it was
- Names the release for the current date, so `YYYY.M.D`
- For each PR:
  - Gets the PR title to summarize the change
  - Looks at the PR labels to classify it in a section of the release notes, as set out by `SECTION_LABELS` and `EXCLUDED_LABEL` at the top of the script:
    - anything labelled `project infrastructure` is excluded
    - label `update` goes in section "Updated"
    - label `bug` goes in section "Fixed"
    - label `documentation` goes in section "Documentation"
    - Default to section "Changed"

With that in mind, when merging changes, it's a good idea to set the labels and rename the PR title to give a good summary of the change, in the context of the changelog.

Those label strings have to match the tracker's labels exactly. One that does not exist there groups nothing and silently leaves its pull requests in "Changed", so the script prints a warning naming any it cannot find. If you rename a label in the tracker, rename it in `SECTION_LABELS` too.

#### Limitations

- Dependabot updates for Docker have a verbose title, try to rename them to be more readable: `Bump traefik from v3.7.12 to v3.7.13 in /{{cookiecutter.project_slug}}/compose/production/traefik` -> `Bump traefik to v3.7.13`
- ~~Dependencies updates for the template repo (tox, cookiecutter, etc...) don't need to appear in changelog, and need to be labelled as `project infrastructure` manually.~~ Dependabot applies the `project infrastructure` label itself.
