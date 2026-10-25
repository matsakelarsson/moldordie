from django.apps import AppConfig


class AppTemplateConfig(AppConfig):
    name = "{{ cookiecutter.project_slug }}.scaffold.app_template"
