# Change Log

All enhancements and patches to moldordie will be documented in this file.

The history this project inherited from cookiecutter-django, up to and
including release 2026.9.8, is kept in
[CHANGELOG-cookiecutter-django.md](CHANGELOG-cookiecutter-django.md).

<!-- GENERATOR_PLACEHOLDER -->

## 2026.9.14


### Changed

- Apply the deletion test to the users app scaffolding ([#40](https://github.com/matsakelarsson/moldordie/pull/40))

- Let the release workflow push to main ([#39](https://github.com/matsakelarsson/moldordie/pull/39))

- Drop the Pillow, pylibmc and graphviz packages from the apt lists ([#38](https://github.com/matsakelarsson/moldordie/pull/38))

- Name and address a user through the model ([#34](https://github.com/matsakelarsson/moldordie/pull/34))

- Draw the generated secrets from a table in the post-generation hook ([#28](https://github.com/matsakelarsson/moldordie/pull/28))

- Make the generated projects pass their formatters, and check it in CI ([#24](https://github.com/matsakelarsson/moldordie/pull/24))

- Make the Django Tasks / Celery split explicit ([#21](https://github.com/matsakelarsson/moldordie/pull/21))

- Trim cloud_provider to AWS and None, mail_service to three ([#19](https://github.com/matsakelarsson/moldordie/pull/19))

- Test the users views through the client only ([#33](https://github.com/matsakelarsson/moldordie/pull/33))

- Migrate the generation tests to the reader ([#30](https://github.com/matsakelarsson/moldordie/pull/30))

- Read the generated project through one reader in the tests ([#29](https://github.com/matsakelarsson/moldordie/pull/29))

- Declare each option once, in a catalogue read from cookiecutter.json ([#26](https://github.com/matsakelarsson/moldordie/pull/26))

- Normalise the yes/no answers before rendering ([#23](https://github.com/matsakelarsson/moldordie/pull/23))

- Fix three stale spots in the test scripts and CI ([#20](https://github.com/matsakelarsson/moldordie/pull/20))

- Align the checks the two integration scripts run ([#37](https://github.com/matsakelarsson/moldordie/pull/37))

- Wire the admin's allauth login in UsersConfig.ready() ([#32](https://github.com/matsakelarsson/moldordie/pull/32))

- Bake each set of answers once per test process ([#31](https://github.com/matsakelarsson/moldordie/pull/31))

- Check the README transcript and the options page against the catalogue ([#27](https://github.com/matsakelarsson/moldordie/pull/27))

- Remove the Heroku option ([#22](https://github.com/matsakelarsson/moldordie/pull/22))

- Release from the last release, not from yesterday ([#18](https://github.com/matsakelarsson/moldordie/pull/18))

### Fixed

- Serve the current user at /api/users/~me/ ([#36](https://github.com/matsakelarsson/moldordie/pull/36))

- Return the name from get_full_name() and get_short_name() ([#35](https://github.com/matsakelarsson/moldordie/pull/35))

- Fix the defects and dead weight the architecture review found ([#25](https://github.com/matsakelarsson/moldordie/pull/25))

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
