Linters
=======

.. index:: linters


All of the linters below run from ``.pre-commit-config.yaml``, so ``pre-commit install`` is
enough to have them checked on every commit. The commands here are for running one by hand.

ruff
----

Ruff is a Python linter and code formatter written in Rust. It reimplements the rules of
flake8, pylint, pyupgrade, isort, Black and many more as a single tool, which is why the
generated project needs none of them separately.

Ruff comes with a linter (``ruff check``) and a formatter (``ruff format``).

To run ruff without modifying your files: ::

    $ uv run ruff format --diff .
    $ uv run ruff check .

Ruff is capable of fixing most of the problems it encounters.
Be sure you commit first before running ``ruff`` so you can restore to a savepoint (and amend afterwards to prevent a double commit): ::

    $ uv run ruff format .
    $ uv run ruff check --fix .
    # be careful with the --unsafe-fixes option, it can break your code
    $ uv run ruff check --fix --unsafe-fixes .

The config for ruff is in ``pyproject.toml``, under ``[tool.ruff]``.
One of the most important options is ``lint.select``, which determines which rule sets are
enforced. For example, `DJ <https://docs.astral.sh/ruff/rules/#flake8-django-dj>`_ is
flake8-django; add it to ``lint.select`` to turn it on.
For a full list of available rules, see `the ruff rules index <https://docs.astral.sh/ruff/rules/>`_.

djLint
------

`djLint <https://djlint.com>`_ lints and reformats the Django templates, with
``profile = "django"`` and the options set under ``[tool.djlint]`` in ``pyproject.toml``. Ruff
does not read templates, so this is what keeps their indentation and tag spacing consistent: ::

    $ uv run djlint <project_slug>/templates --reformat
    $ uv run djlint <project_slug>/templates --lint

django-upgrade
--------------

`django-upgrade <https://github.com/adamchainz/django-upgrade>`_ rewrites code that uses
Django APIs superseded by the target version, which the pre-commit hook pins to the Django
version the project was generated for. Raise ``--target-version`` in
``.pre-commit-config.yaml`` when you upgrade Django, and it will do a first pass over the
deprecations for you.

mypy
----

Type checking runs as a pre-commit hook too, on push rather than on commit, because it needs
the project's own environment. See :ref:`testing` for what it checks and how to run it.
