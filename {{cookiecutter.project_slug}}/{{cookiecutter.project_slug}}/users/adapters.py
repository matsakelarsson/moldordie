from __future__ import annotations

import typing

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings
{%- if cookiecutter.identity_provider == 'entra' %}

from .providers import ENTRA
from .providers import EntraProvider
{%- endif %}

if typing.TYPE_CHECKING:
    from allauth.socialaccount.models import SocialLogin
{%- if cookiecutter.identity_provider == 'entra' %}
    from allauth.socialaccount.providers.base.provider import Provider
{%- endif %}
    from django.http import HttpRequest

    from {{cookiecutter.project_slug}}.users.models import User


class AccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request: HttpRequest) -> bool:
        return bool(settings.ACCOUNT_ALLOW_REGISTRATION)


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    # allauth asks the account adapter whether social signup is open, so the
    # setting above gates both.
{%- if cookiecutter.identity_provider == 'entra' %}

    def get_provider(
        self,
        request: HttpRequest,
        provider: str,
        client_id: str | None = None,
    ) -> Provider:
        """Hand out the Entra subclass for the Entra app, allauth's class otherwise."""
        instance: Provider = super().get_provider(
            request,
            provider,
            client_id=client_id,
        )
        if instance.uses_apps and instance.app.provider_id == ENTRA:
            return EntraProvider(request, app=instance.app)
        return instance
{%- endif %}

    def populate_user(
        self,
        request: HttpRequest,
        sociallogin: SocialLogin,
        data: dict[str, typing.Any],
    ) -> User:
        """
        Populates user information from social provider info.

        See: https://docs.allauth.org/en/latest/socialaccount/advanced.html#creating-and-populating-user-instances
        """
        user: User = super().populate_user(request, sociallogin, data)
        if not user.name:
            if name := data.get("name"):
                user.name = name
            elif first_name := data.get("first_name"):
                user.name = first_name
                if last_name := data.get("last_name"):
                    user.name += f" {last_name}"
        return user
