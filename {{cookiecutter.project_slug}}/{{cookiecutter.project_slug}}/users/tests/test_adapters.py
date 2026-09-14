"""The allauth adapters, called the way allauth calls them."""

import pytest
from allauth.socialaccount.models import SocialAccount
from allauth.socialaccount.models import SocialLogin

from {{ cookiecutter.project_slug }}.users.adapters import AccountAdapter
from {{ cookiecutter.project_slug }}.users.adapters import SocialAccountAdapter
from {{ cookiecutter.project_slug }}.users.models import User


@pytest.fixture
def sociallogin() -> SocialLogin:
    """A social login in progress, with the unsaved user allauth suggests for it."""
    return SocialLogin(user=User(), account=SocialAccount(provider="example"))


class TestAccountAdapter:
    @pytest.mark.parametrize("allowed", [True, False])
    def test_signup_follows_the_setting(self, rf, settings, allowed):
        settings.ACCOUNT_ALLOW_REGISTRATION = allowed

        assert AccountAdapter().is_open_for_signup(rf.get("/")) is allowed


class TestSocialAccountAdapter:
    @pytest.mark.parametrize("allowed", [True, False])
    def test_signup_follows_the_setting(self, rf, settings, sociallogin, allowed):
        settings.ACCOUNT_ALLOW_REGISTRATION = allowed
        adapter = SocialAccountAdapter()

        assert adapter.is_open_for_signup(rf.get("/"), sociallogin) is allowed

    @pytest.mark.parametrize(
        ("data", "name"),
        [
            ({"name": "Ada Lovelace"}, "Ada Lovelace"),
            (
                {"name": "Ada Lovelace", "first_name": "Augusta", "last_name": "King"},
                "Ada Lovelace",
            ),
            ({"first_name": "Ada", "last_name": "Lovelace"}, "Ada Lovelace"),
            ({"first_name": "Ada"}, "Ada"),
            ({"last_name": "Lovelace"}, ""),
            ({}, ""),
        ],
    )
    def test_populate_user_names_the_user(self, rf, sociallogin, data, name):
        user = SocialAccountAdapter().populate_user(rf.get("/"), sociallogin, data)

        assert user.name == name
