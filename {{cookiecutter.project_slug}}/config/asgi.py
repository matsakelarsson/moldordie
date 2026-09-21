"""
ASGI config for {{ cookiecutter.project_name | string_escape }} project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/dev/howto/deployment/asgi/

"""

import os
import sys
from pathlib import Path

from django.core.asgi import get_asgi_application

# This allows easy placement of apps within the interior
# {{ cookiecutter.project_slug }} directory.
BASE_DIR = Path(__file__).resolve(strict=True).parent.parent
sys.path.append(str(BASE_DIR / "{{ cookiecutter.project_slug }}"))

# If DJANGO_SETTINGS_MODULE is unset, default to the local settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
{%- if cookiecutter.realtime == 'channels' %}

# Build the Django application first so that the apps are loaded before the
# websocket routing, which imports consumers and therefore models, is imported.
django_asgi_app = get_asgi_application()

from channels.auth import AuthMiddlewareStack  # noqa: E402
from channels.routing import ProtocolTypeRouter  # noqa: E402
from channels.routing import URLRouter  # noqa: E402
from channels.security.websocket import AllowedHostsOriginValidator  # noqa: E402

from config.websocket import websocket_urlpatterns  # noqa: E402

# types-channels only accepts its own URL pattern type here, hence the ignore.
websocket_application = AllowedHostsOriginValidator(
    AuthMiddlewareStack(URLRouter(websocket_urlpatterns)),  # type: ignore[arg-type]
)

# This application object is used by any ASGI server configured to use this file.
application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": websocket_application,
    },
)
{%- else %}

# This application object is used by any ASGI server configured to use this file.
application = get_asgi_application()
{%- endif %}
{%- if cookiecutter.observability == 'opentelemetry' %}

from {{ cookiecutter.project_slug }}.telemetry.asgi import flushing_on_shutdown  # noqa: E402

# A web worker is stopped by a signal its server re-raises once it has stopped
# serving, so the server's lifespan is the last thing it runs: it is where what this
# worker recorded is sent ({{ cookiecutter.project_slug }}/telemetry/asgi.py). The
# ignore is the rebinding: what serves is now a function rather than the class above.
application = flushing_on_shutdown(application)  # type: ignore[assignment]
{%- endif %}
