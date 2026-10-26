"""The scaffold: ``startapp`` as this project runs it, and the app template it copies.

``app_template/`` is a complete app under placeholder names, ``app_template`` for the
app and ``Item`` for its model: a model, its admin, a form, the views and templates of
a list, a record and the forms that create, change and delete one, a first migration,
a factory and the tests of all of it. It is not an installed app and nothing imports
it; ``manage.py startapp`` copies it into the package under the names given, renaming
as it goes (``names.py``), and the copy is the new app, its tests passing once it is
registered. Being a package of this project, the project's own tools check the
template as it stands: ruff, mypy and djLint run on it with everything else, so a
change to a convention that breaks it fails here, before it reaches a new app. pytest
leaves its tests alone (``pyproject.toml``): they run as the new app's.
"""

from django.apps import AppConfig


class ScaffoldConfig(AppConfig):
    name = "{{ cookiecutter.project_slug }}.scaffold"
