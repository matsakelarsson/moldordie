# Change Log

All enhancements and patches to moldordie will be documented in this file.

The history this project inherited from cookiecutter-django, up to and
including release 2026.9.8, is kept in
[CHANGELOG-cookiecutter-django.md](CHANGELOG-cookiecutter-django.md).

<!-- GENERATOR_PLACEHOLDER -->

## 2026.9.13

### Changed

- Modernize template frontend ([#1](https://github.com/matsakelarsson/moldordie/pull/1))
- Make ASGI the default and replace use_async with a realtime option ([#2](https://github.com/matsakelarsson/moldordie/pull/2))
- Rename the package to moldordie in pyproject ([#4](https://github.com/matsakelarsson/moldordie/pull/4))
- Lean into Django 6.0: partials, CSP, Tasks and Python 3.12-3.14 ([#5](https://github.com/matsakelarsson/moldordie/pull/5))
- Remove the machinery that only served upstream ([#7](https://github.com/matsakelarsson/moldordie/pull/7))
- Remove the windows and editor options and the devcontainer ([#8](https://github.com/matsakelarsson/moldordie/pull/8))
- Turn the post-generation removals into a table of removal rules ([#10](https://github.com/matsakelarsson/moldordie/pull/10))
- Pin the generated dependencies in pyproject.toml ([#13](https://github.com/matsakelarsson/moldordie/pull/13))
- Retire the PyUp machinery ([#14](https://github.com/matsakelarsson/moldordie/pull/14))
- Trim ci_tool to None, GitHub and GitLab ([#15](https://github.com/matsakelarsson/moldordie/pull/15))

### Fixed

- Make ruff's template exclusion actually match ([#6](https://github.com/matsakelarsson/moldordie/pull/6))
- Remove docker-compose.docs.yml when use_docker=n ([#9](https://github.com/matsakelarsson/moldordie/pull/9))
- Stop free-text answers from breaking generation ([#11](https://github.com/matsakelarsson/moldordie/pull/11))
- Escape free-text answers in every generated file ([#12](https://github.com/matsakelarsson/moldordie/pull/12))

### Documentation

- Describe the project as moldordie, a fork of cookiecutter-django ([#3](https://github.com/matsakelarsson/moldordie/pull/3))
- Docs accuracy pass ([#16](https://github.com/matsakelarsson/moldordie/pull/16))
