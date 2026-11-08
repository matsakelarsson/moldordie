# Change Log

All enhancements and patches to moldordie will be documented in this file.

The history this project inherited from cookiecutter-django, up to and
including release 2026.9.8, is kept in
[CHANGELOG-cookiecutter-django.md](CHANGELOG-cookiecutter-django.md).

<!-- GENERATOR_PLACEHOLDER -->

## 2026.11.8


### Changed

- Fix Celery startup in production and beat startup on a new local stack ([#140](https://github.com/matsakelarsson/moldordie/pull/140))

- Document setting up, configuring and deploying a generated project ([#139](https://github.com/matsakelarsson/moldordie/pull/139))

- Leave no trace of the template in a generated project ([#138](https://github.com/matsakelarsson/moldordie/pull/138))

- Give the account pages one frame and an account menu ([#136](https://github.com/matsakelarsson/moldordie/pull/136))

- Put the pages in a sidebar a page adds its sections to ([#135](https://github.com/matsakelarsson/moldordie/pull/135))

- Scaffold a new app from an app template the project checks ([#134](https://github.com/matsakelarsson/moldordie/pull/134))

- Stop merging upstream, and read its releases instead ([#133](https://github.com/matsakelarsson/moldordie/pull/133))

- Index the generated layout in the repository guide ([#132](https://github.com/matsakelarsson/moldordie/pull/132))

- Let telemetry's tests cross its interface ([#131](https://github.com/matsakelarsson/moldordie/pull/131))

- Give the project's package an import section of its own ([#130](https://github.com/matsakelarsson/moldordie/pull/130))

- Read and route a calling service's token in one place ([#129](https://github.com/matsakelarsson/moldordie/pull/129))

- Check an arm's wiring on every supported combination ([#128](https://github.com/matsakelarsson/moldordie/pull/128))

- Put the fragment contract inside the htmx module ([#127](https://github.com/matsakelarsson/moldordie/pull/127))

- Finish the reader's lookup half ([#126](https://github.com/matsakelarsson/moldordie/pull/126))

- Remove what the skills plugin's setup wrote into the repository ([#125](https://github.com/matsakelarsson/moldordie/pull/125))

- Fix what the September review listed and nothing had fixed ([#124](https://github.com/matsakelarsson/moldordie/pull/124))

- Leave the generated pyproject.toml as its own hook would ([#123](https://github.com/matsakelarsson/moldordie/pull/123))

- Verify the collector's certificate whatever the environment says ([#94](https://github.com/matsakelarsson/moldordie/pull/94))

- Read the derived answers everywhere, and let no template re-derive them ([#121](https://github.com/matsakelarsson/moldordie/pull/121))

- Fail for a removable path that no CI row keeps ([#115](https://github.com/matsakelarsson/moldordie/pull/115))

- Generate the Sentry and nginx arms in CI ([#114](https://github.com/matsakelarsson/moldordie/pull/114))

- Fail for a removable path that no supported combination keeps ([#113](https://github.com/matsakelarsson/moldordie/pull/113))

- Tidy what the observability work left behind ([#98](https://github.com/matsakelarsson/moldordie/pull/98))

- Start the arm that measures where no Compose file starts it ([#95](https://github.com/matsakelarsson/moldordie/pull/95))

- Render the deployed Compose files and Traefik routers from one source ([#120](https://github.com/matsakelarsson/moldordie/pull/120))

- Render the deployed environments' env files from one source ([#119](https://github.com/matsakelarsson/moldordie/pull/119))

- Declare a secret drawn per deployed environment once ([#117](https://github.com/matsakelarsson/moldordie/pull/117))

- Fail for a generated file that cites a path its answers removed ([#116](https://github.com/matsakelarsson/moldordie/pull/116))

- Compare every combination's generated tree between two revisions ([#112](https://github.com/matsakelarsson/moldordie/pull/112))

- Bound what an unverified caller can start ([#97](https://github.com/matsakelarsson/moldordie/pull/97))

- Bound the shutdown a process actually keeps ([#96](https://github.com/matsakelarsson/moldordie/pull/96))

- Bind the derived answers once, before any file renders ([#118](https://github.com/matsakelarsson/moldordie/pull/118))

- Export traces and metrics over OTLP from each serving process ([#93](https://github.com/matsakelarsson/moldordie/pull/93))

- Let a scrape present the token its identity provider issued ([#92](https://github.com/matsakelarsson/moldordie/pull/92))

- Measure the project with django-prometheus behind its own credential ([#91](https://github.com/matsakelarsson/moldordie/pull/91))

### Updated

- Auto-update pre-commit hooks ([#137](https://github.com/matsakelarsson/moldordie/pull/137))

- Auto-update pre-commit hooks ([#122](https://github.com/matsakelarsson/moldordie/pull/122))

## 2026.9.20


### Changed

- Reload an open page when the development server restarts ([#90](https://github.com/matsakelarsson/moldordie/pull/90))

- Name the static files on S3 after their contents ([#89](https://github.com/matsakelarsson/moldordie/pull/89))

- Build the frontend with Tailwind CSS and daisyUI through django-tailwind-cli (#81–#84, #86) ([#88](https://github.com/matsakelarsson/moldordie/pull/88))

- Render the whole page when htmx restores history ([#85](https://github.com/matsakelarsson/moldordie/pull/85))

- Regenerate the catalogues, sweep the last traces and record the browser pass ([#86](https://github.com/matsakelarsson/moldordie/pull/86))

- Add the examples page, routed in every environment ([#84](https://github.com/matsakelarsson/moldordie/pull/84))

- Enable every daisyUI theme behind an htmx theme picker kept in a cookie ([#83](https://github.com/matsakelarsson/moldordie/pull/83))

- Restyle every page with daisyUI and remove the previous frontend ([#82](https://github.com/matsakelarsson/moldordie/pull/82))

- Land the coding agent's guide on main (#79) ([#87](https://github.com/matsakelarsson/moldordie/pull/87))

- Wire django-tailwind-cli, daisyUI and the stylesheet build ([#81](https://github.com/matsakelarsson/moldordie/pull/81))

- Name every Python the packaging metadata allows ([#80](https://github.com/matsakelarsson/moldordie/pull/80))

- Write the chosen coding agent's guide into the generated project ([#79](https://github.com/matsakelarsson/moldordie/pull/79))

- Add the dev and test deployed environments ([#78](https://github.com/matsakelarsson/moldordie/pull/78))

## 2026.9.16


### Changed

- Restore the daily pre-commit auto-update by quoting the Jinja in the config ([#76](https://github.com/matsakelarsson/moldordie/pull/76))

- Replace Pico with django-cotton components and a project-owned UI library (#71–#74) ([#75](https://github.com/matsakelarsson/moldordie/pull/75))

- Document htmx in the generated guide and test the forbidden pages ([#74](https://github.com/matsakelarsson/moldordie/pull/74))

- Add brand colours, the theme preview and the component showcase ([#73](https://github.com/matsakelarsson/moldordie/pull/73))

- Add the starter components and migrate every page from Pico ([#72](https://github.com/matsakelarsson/moldordie/pull/72))

- Configure django-cotton and lay the UI library's foundation ([#71](https://github.com/matsakelarsson/moldordie/pull/71))

- Land the identity provider stack on main (#46–#56) ([#70](https://github.com/matsakelarsson/moldordie/pull/70))

- Address the review of the identity provider stack ([#69](https://github.com/matsakelarsson/moldordie/pull/69))

- Make the verifier resilient around its key source, with diagnostics (#56) ([#68](https://github.com/matsakelarsson/moldordie/pull/68))

- Cover the Google service verifier with tests and docs (#55) ([#67](https://github.com/matsakelarsson/moldordie/pull/67))

- Add permissions for users and services on shared endpoints (#54) ([#66](https://github.com/matsakelarsson/moldordie/pull/66))

- Verify calling services against the Entra tenant with service registrations (#53) ([#65](https://github.com/matsakelarsson/moldordie/pull/65))

- Add the revoke_jwt_sessions command for key rotation (#52) ([#64](https://github.com/matsakelarsson/moldordie/pull/64))

- Document and test provider login from the SPA (#51) ([#63](https://github.com/matsakelarsson/moldordie/pull/63))

- Define the frontend contract for return destinations and mail links (#50) ([#62](https://github.com/matsakelarsson/moldordie/pull/62))

- Authenticate the API with app-issued bearer tokens (#49) ([#61](https://github.com/matsakelarsson/moldordie/pull/61))

- Serve the SPA login with app-issued JWTs on Ninja projects (#48) ([#60](https://github.com/matsakelarsson/moldordie/pull/60))

- Refuse an Entra token without a usable object id (#47) ([#59](https://github.com/matsakelarsson/moldordie/pull/59))

- Add the identity_provider option with sign-in through Entra or Google (#46) ([#58](https://github.com/matsakelarsson/moldordie/pull/58))

- Render the CORS settings for both REST frameworks (#45) ([#57](https://github.com/matsakelarsson/moldordie/pull/57))

- Keep the settings modules importable ([#44](https://github.com/matsakelarsson/moldordie/pull/44))

- Keep the settings modules importable ([#43](https://github.com/matsakelarsson/moldordie/pull/43))

- Render each setting from one block ([#42](https://github.com/matsakelarsson/moldordie/pull/42))

- Render the release notes as Markdown, not HTML ([#41](https://github.com/matsakelarsson/moldordie/pull/41))

### Updated

- Update pyproject-fmt to v2.29.4 ([#77](https://github.com/matsakelarsson/moldordie/pull/77))

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
