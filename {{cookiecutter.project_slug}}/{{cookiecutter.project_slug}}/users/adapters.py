from __future__ import annotations

import typing

from allauth.account.adapter import DefaultAccountAdapter
{%- if cookiecutter.rest_api == 'Django Ninja' and cookiecutter.identity_provider != 'none' %}
from allauth.core import context
{%- endif %}
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings
{%- if cookiecutter.rest_api == 'Django Ninja' and cookiecutter.identity_provider != 'none' %}

from {{cookiecutter.project_slug}}.identity.frontend import origin
{%- endif %}
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
{%- if cookiecutter.rest_api == 'Django Ninja' and cookiecutter.identity_provider != 'none' %}

    def is_safe_url(self, url: str) -> bool:
        """May a login return to ``url``?

        A relative URL and this origin keep allauth's own rule, for the server-rendered
        pages. Any other URL must be on one of the origins the single-page application
        is served from: scheme, host and port, not the host alone as allauth's default
        allows.
        """
        destination = origin(url)
        if destination is None:
            return bool(super().is_safe_url(url))
        own = origin(context.request.build_absolute_uri("/"))
        allowed = {
            own,
            *(origin(configured) for configured in settings.FRONTEND_ORIGINS),
        }
        return destination in allowed
{%- endif %}


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
