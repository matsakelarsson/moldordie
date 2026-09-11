# Maintainer guide

This document is intended for maintainers of the template.

## Automated updates

We use 2 separate services to keep our dependencies up-to-date:

- Dependabot, which manages updates of Python deps of the template, GitHub actions and Docker images.
- PyUp, which manages the Python deps for the generated project.

We don't use Dependabot for the generated project deps because our requirements files are templated, and Dependabot fails to parse them. PyUp is -AFAIK- the only service out there that supports having Jinja tags in the requirements file.

Updates for the template should be labelled as `project infrastructure` while the ones about the generated project should be labelled as `update`. This is use to work in conjunction with our changelog script (see later).

## Automation scripts

We have a few workflows which have been automated over time. They usually run using GitHub actions and might need a few small manual actions to work nicely. Some have a few limitations which we should document here.

### CI

`ci.yml`

The CI workflow tries to cover 2 main aspects of the template:

- Check all combinations to make sure that valid files are generated with no major linting issues. Issues which are fixed by an auto-formatter after generation aren't considered major, and only aim for best effort. This is under the `test` job.
- Run more in-depth tests on a few combinations, by installing dependencies, running type checker and the test suite of the generated project. We try to cover docker (`docker` job) and non-docker (`bare` job) setups.

We also run the deployment checks, but we don't do much more beyond that for testing the production setup.

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

We wait 10 days before closing issues, and we have a few customised reasons, which are configured in the workflow itself. The config should be fairly self-explanatory.

### Pre-commit auto-update

`pre-commit-autoupdate.yml`

Run daily, to do `pre-commit autoupdate` on the template as well as the generated project, and opens a pull request with the changes.

#### Limitations

- The PR is open as GitHub action which means that CI does NOT run. The documentation for create-pull-request action [explains why](https://github.com/peter-evans/create-pull-request/blob/main/docs/concepts-guidelines.md#triggering-further-workflow-runs).
- Some hooks are also installed as local dependencies (via `requirements/local.txt`), but these are updated separately via PyUP.

### Update changelog

`update-changelog.yml`

Updates the changelog and creates a GitHub release. `workflow_dispatch` only, for the same reason as the Django issue checker above; restore the `schedule:` trigger to cut releases daily. It runs a custom script which:

- List all pull requests merged the day before
- The release name is calendar based, so `YYYY.MM.DD`
- For each PR:
  - Get the PR title to summarize the change
  - Look at the PR labels to classify it in a section of the release notes:
    - anything labelled `project infrastructure` is excluded
    - label `update` goes in section "Updated"
    - label `bug` goes in section "Fixed"
    - label `docs` goes in section "Documentation"
    - Default to section "Changed"

With that in mind, when merging changes, it's a good idea to set the labels and rename the PR title to give a good summary of the change, in the context of the changelog.

#### Limitations

- Dependabot updates for Docker have a verbose title, try to rename them to be more readable: `Bump traefik from v3.7.12 to v3.7.13 in /{{cookiecutter.project_slug}}/compose/production/traefik` -> `Bump traefik to v3.7.13`
- ~~Dependencies updates for the template repo (tox, cookiecutter, etc...) don't need to appear in changelog, and need to be labelled as `project infrastructure` manually. By default, they come from PyUp labelled as `update`.~~
