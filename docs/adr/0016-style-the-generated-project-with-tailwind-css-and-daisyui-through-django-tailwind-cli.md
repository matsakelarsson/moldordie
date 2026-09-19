---
status: accepted
---

# Style the generated project with Tailwind CSS and daisyUI through django-tailwind-cli

The generated project's pages are server-rendered Django templates enhanced with htmx, and the
template's standing condition for their styling is that nothing needs Node.js. The frontend this
replaces was a project-owned library of django-cotton components and hand-written stylesheets.
Tailwind had been turned down before it. The owner's account of why, and of what changed:
"Tailwind was rejected because I thought it needed node.js, but then I found django-tailwind-cli
that is a seamless and easy integration of tailwind into django without node.js".

Pages are written with Tailwind's utilities and daisyUI's component classes. django-tailwind-cli,
pinned in the generated `pyproject.toml` as a runtime dependency, downloads Tailwind's standalone
CLI and drives it from `manage.py tailwind build` and `manage.py tailwind watch`.
`TAILWIND_CLI_USE_DAISY_UI = True` makes that binary `tailwindcss-extra`, the standalone CLI with
daisyUI bundled, from `dobicinaitis/tailwind-cli-extra`, and `TAILWIND_CLI_VERSION` pins its
release, which fixes the Tailwind CSS and the daisyUI a project builds with. The source stylesheet
is `<project_slug>/styles/main.css`, outside the static directories, because a manifest storage
cannot resolve its `@import "tailwindcss"`. It names its sources itself (`source(none)` and
`@source`), so the scan covers the package's templates and modules and is the same on every
machine and in an image, where `.dockerignore` leaves `.gitignore` out.

The built stylesheet, `<project_slug>/static/css/tailwind.css`, is an artefact: generation does
not write it and git ignores it. The watcher rebuilds it in development, a second process without
Docker and the `tailwind` service of the local Compose file with it. For a deployment the
production image builds it in its build stage, before anything collects, with the CLI in a build
cache so that no layer holds the binary. A container builds nothing when it starts: `collectstatic`
collects what the image holds.

## Considered options

- **A Node.js toolchain**, Tailwind and daisyUI installed as packages and built by a Node process:
  what the owner's condition excludes, and what the generation tests fence against
  (`FRONTEND_TOOLCHAIN_PATHS`, `FRONTEND_TOOLCHAIN_TOKENS`).
- **Tailwind's own standalone binary with daisyUI's plugin files vendored beside the source
  stylesheet**, as daisyUI documents for Django. It keeps the downloaded binary first-party. It
  also makes two minified third-party files the template's to carry: kept out of Cookiecutter's
  rendering and out of the formatters, licensed, and upgraded by hand in step with the binary.
  django-tailwind-cli's one switch covers the binary and the plugin together.
- **Committing the built stylesheet**, so that a checkout is styled before anything has run: a
  minified file that changes with most template edits, conflicts on every merge and can be
  committed stale without any check noticing.
- **Building when a container starts**, next to `collectstatic` in the production `start` script:
  every container start would download the binary and depend on GitHub being reachable, and the
  running container would carry a build tool. `start` is also the step nothing in the template's
  CI runs, while the image build is.

## Consequences

There is a build step. A checkout has no stylesheet until the watcher or a build has run: in
development the pages are unstyled until then, and under a manifest storage collecting before
building does not fail `collectstatic`, it fails the first page that renders, with a missing
manifest entry. Deployments outside Docker run `tailwind build` before `collectstatic` by hand.

Image builds, CI and a developer's first run download the binary, about 110 MB for Linux, from
GitHub; django-tailwind-cli verifies no checksum. `tailwindcss-extra` is a third-party build from
one maintainer's repository, so a project that cannot accept that points `TAILWIND_CLI_SRC_REPO`
at a mirror or `TAILWIND_CLI_PATH` at a binary it provisions. Nothing bumps the pin: it is a
string in a settings template, which neither this repository's Dependabot nor a generated
project's can see, so the maintainer guide lists it with the pins bumped by hand.

Every `TAILWIND_CLI_*` setting lives in `config/settings/base.py` and nowhere else, because the
image builds under `config.settings.test`: an override in `production.py` would make the image
build one file and the deployment ask for another. `test_tailwind_and_daisyui` holds the other
settings modules to that.

Tailwind generates a class only where it finds the whole name in a scanned file, so templates
choose between whole class names and never assemble one.

`test_tailwind_and_daisyui` and `test_docker_builds_and_watches_the_stylesheet` check the wiring
without running the CLI. The generated `tests/test_staticfiles.py` runs it: it builds the
stylesheet into a temporary directory and collects everything under a manifest storage, which
needs the network the first time. The integration scripts build from the command line as a
deployment does, and the Docker script also checks that the watcher service stays up and that the
production image carries the stylesheet and not the CLI.
