from django.apps import AppConfig
from django.conf import settings
from django.contrib import admin
from django.utils.translation import gettext_lazy as _


class UsersConfig(AppConfig):
    name = "{{ cookiecutter.project_slug }}.users"
    verbose_name = _("Users")

    def ready(self) -> None:
        if settings.DJANGO_ADMIN_FORCE_ALLAUTH:
            # Force the `admin` sign in process to go through the `django-allauth`
            # workflow: https://docs.allauth.org/en/latest/common/admin.html#admin
            # allauth's decorators import its models, so this import waits for the
            # app registry.
            from allauth.account.decorators import secure_admin_login  # noqa: PLC0415

            admin.site.login = secure_admin_login(admin.site.login)  # type: ignore[method-assign]
