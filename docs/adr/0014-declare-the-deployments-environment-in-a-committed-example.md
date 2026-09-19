---
status: accepted
---

# Declare the deployment's environment in a committed example

No env file is in version control. `.envs/.local/` used to be, when `keep_local_envs_in_vcs`
was answered `y`, which was the default; that option is gone and the generated `.gitignore`
now ignores `.env` and `.envs/*` whatever the answers, because every one of those files
carries the credentials of the environment it configures.

That broke what `docs/adr/0006` set up. The generated `tests/test_production_settings.py` read
`.envs/.production/.django` and `.postgres` to learn which variables a deployment supplies, so
in any checkout — the project's own CI included — every test in the module failed at fixture
setup with `FileNotFoundError`, and the generated CI runs nothing else against the production
settings. The fault predated the change for Docker projects, where those files were already
ignored; removing the option made it universal.

The declaration and the values are now separate things. `.env.example` is committed: every
variable a deployment supplies, each with the value the env file carries, except that a value
drawn on generation is left unset. The post-generation hook writes it from
`.envs/.production/.django` and `.postgres`, merged as `merge_production_dotenvs_in_dotenv.py`
merges them, before `fill_secrets` replaces the placeholders — so the example cannot declare
anything a deployment does not read, and cannot carry a secret. The generated test reads the
example and fills each unset value with a stand-in named after it, which keeps two unset keys
from reading alike, and `test_the_example_matches_the_env_files` checks the example against the
env files wherever they are present: a freshly generated tree, a developer's machine, and the
integration scripts.

## Considered options

- **Commit the env files with the secrets stripped, the drawn values going to an ignored file
  Compose loads after them**: the declaration and the values would stay in one directory with
  no second file to read, but a file under `.envs/` would be in version control, which is
  what is not wanted, and a reader would have to know which of two files to trust.
- **Have the generated CI write stand-in deployed env files**, as it already does for
  `.envs/.local/`: a second list of the deployment's variables, in a workflow, free to drift
  from the env files — the option `docs/adr/0006` rejected, and worse here, because a
  developer adding a variable would have to remember the workflow.
- **Skip the module when the files are absent**: the production settings would then be
  exercised nowhere in the project's CI, which is the one place a developer's later edits are
  checked.
- **Derive the required variables from the settings source**, reading every `env(...)` call as
  `docs/adr/0001` does in this repository: it needs no committed declaration, but the
  stand-ins would have to be typed per accessor, and some variables need values the app's own
  checks accept — `DJANGO_FRONTEND_URL` has to be one of `DJANGO_FRONTEND_ORIGINS` — which the
  env files' curated values already are.
- **A stand-in environment written in the test**: a third list, and nothing would connect it
  to what a deployment reads.

## Consequences

A checkout has one file describing what a deployment must supply, and it is the file the tests
load, so a variable the settings require and the example omits fails in the project's own CI.
The example is written from the production env files, so a variable added to one environment
reaches it without anyone editing it, and `test_the_example_dotenv_declares_the_deployment_variables`
checks over every combination that the two agree and that no drawn value reached the example.

`write_example_dotenv` must stay ahead of `fill_secrets` in `main`; a test asserts that order
in the hook's source, because afterwards the placeholders are gone and the example would carry
the drawn values. The env files are now generated for every project rather than dropped without
Docker: nothing prunes them, since the answer that asked for them to be kept is gone, and
without Docker the merge script still turns the deployment's files into the `.env` that
`DJANGO_READ_DOT_ENV_FILE` reads.
