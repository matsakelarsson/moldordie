"""The system checks in ``users/checks.py``."""

from django.core import checks

from {{ cookiecutter.project_slug }}.users.checks import CREDENTIALS
from {{ cookiecutter.project_slug }}.users.checks import check_provider_credentials


def test_the_check_runs_with_the_system_checks(settings):
    for name in CREDENTIALS:
        setattr(settings, name, "")

    ids = [message.id for message in checks.run_checks()]
    assert ids.count("users.W001") == len(CREDENTIALS)


def test_configured_credentials_pass(settings):
    for name in CREDENTIALS:
        setattr(settings, name, "configured")

    assert check_provider_credentials(None) == []


def test_each_empty_credential_is_reported(settings):
    for name in CREDENTIALS:
        setattr(settings, name, "")

    messages = check_provider_credentials(None)

    assert [message.id for message in messages] == ["users.W001"] * len(CREDENTIALS)
    assert all(message.level == checks.WARNING for message in messages)
    assert [name for name in CREDENTIALS if name in messages[0].msg] == [CREDENTIALS[0]]


def test_whitespace_counts_as_empty(settings):
    for name in CREDENTIALS:
        setattr(settings, name, "configured")
    setattr(settings, CREDENTIALS[-1], "  ")

    messages = check_provider_credentials(None)

    assert len(messages) == 1
    assert CREDENTIALS[-1] in messages[0].msg
