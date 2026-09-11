"""Websocket routing and consumers for {{ cookiecutter.project_name }}."""

from channels.generic.websocket import AsyncWebsocketConsumer
from django.urls import path


class PingConsumer(AsyncWebsocketConsumer):
    """Answer every ``ping`` text frame with ``pong!``."""

    async def receive(
        self,
        text_data: str | None = None,
        bytes_data: bytes | None = None,
    ) -> None:
        if text_data == "ping":
            await self.send(text_data="pong!")


# django-stubs types ``path`` for HTTP views, so consumers need the ignore below.
websocket_urlpatterns = [
    path("ws/ping/", PingConsumer.as_asgi()),  # type: ignore[arg-type]
]
