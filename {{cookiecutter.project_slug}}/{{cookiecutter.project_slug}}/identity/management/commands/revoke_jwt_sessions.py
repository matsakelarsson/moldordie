"""Delete the sessions behind app-issued tokens, after the signing key was replaced."""

from __future__ import annotations

from typing import Any

from django.contrib.sessions.models import Session
from django.core.management.base import BaseCommand

# allauth's JWT strategy keeps the refresh tokens it issued for a session under this key
# of the session data, an empty mapping once every one of them is used up
REFRESH_TOKEN_STATE = "headless_refresh_tokens"  # noqa: S105 - a session key, not a secret


class Command(BaseCommand):
    help = (
        "Delete the sessions behind app-issued tokens: with the signing key replaced "
        "in every process, the tokens fail already and retained session tokens stop "
        "working too. A pending login without tokens yet is not identified."
    )

    def handle(self, *args: Any, **options: Any) -> None:
        keys = [
            session.session_key
            for session in Session.objects.iterator()
            if REFRESH_TOKEN_STATE in session.get_decoded()
        ]
        removed, _ = Session.objects.filter(session_key__in=keys).delete()
        self.stdout.write(f"Removed {removed} sessions behind app-issued tokens.")
