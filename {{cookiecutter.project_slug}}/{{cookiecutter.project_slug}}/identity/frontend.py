"""The single-page application's origins, as the checks and the adapter compare them."""

from __future__ import annotations

from urllib.parse import urlsplit

from django.conf import settings

# (scheme, host, port) once normalised: lowercase, the scheme's default port filled in
Origin = tuple[str, str, int]
DEFAULT_PORTS = {"http": 80, "https": 443}


def origin(url: str) -> Origin | None:
    """The normalised origin of ``url``, or None for a relative URL."""
    parts = urlsplit(url)
    if not parts.netloc:
        return None
    scheme = parts.scheme.lower()
    try:
        port = parts.port
    except ValueError:
        # Not a port number: no origin can match it
        return None
    if port is None:
        port = DEFAULT_PORTS.get(scheme, 0)
    return (scheme, (parts.hostname or "").lower(), port)


def frontend_origins() -> set[Origin | None]:
    """The origins the application is served from, ``FRONTEND_ORIGINS`` normalised."""
    return {origin(configured) for configured in settings.FRONTEND_ORIGINS}
