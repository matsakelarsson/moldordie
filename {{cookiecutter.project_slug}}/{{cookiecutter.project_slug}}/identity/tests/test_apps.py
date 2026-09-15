"""The identity app refuses to start with settings that would issue bad tokens."""

import pytest
from django.apps import AppConfig
from django.core.exceptions import ImproperlyConfigured

from {{ cookiecutter.project_slug }}.identity.apps import validate_token_settings


def test_the_test_settings_pass():
    AppConfig.create("{{ cookiecutter.project_slug }}.identity").ready()


@pytest.mark.parametrize("key", ["", "   "])
def test_an_empty_signing_key_refuses_to_start(settings, key):
    """allauth would sign with SECRET_KEY instead, which the tokens must not share."""
    settings.HEADLESS_JWT_PRIVATE_KEY = key

    with pytest.raises(ImproperlyConfigured, match="DJANGO_HEADLESS_JWT_PRIVATE_KEY"):
        AppConfig.create("{{ cookiecutter.project_slug }}.identity").ready()


@pytest.mark.parametrize(
    "name",
    ["HEADLESS_JWT_ACCESS_TOKEN_EXPIRES_IN", "HEADLESS_JWT_REFRESH_TOKEN_EXPIRES_IN"],
)
@pytest.mark.parametrize("lifetime", [0, -1])
def test_a_non_positive_lifetime_refuses_to_start(settings, name, lifetime):
    setattr(settings, name, lifetime)

    with pytest.raises(ImproperlyConfigured, match=name):
        validate_token_settings(settings)
