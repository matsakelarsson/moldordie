from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from asgiref.sync import async_to_sync
from asgiref.testing import ApplicationCommunicator

if TYPE_CHECKING:
    from channels.routing import ProtocolTypeRouter

pytestmark = pytest.mark.django_db


@pytest.fixture
def application() -> ProtocolTypeRouter:
    # AllowedHostsOriginValidator snapshots ALLOWED_HOSTS when the application is
    # built, so build it only after pytest-django has added "testserver" to it.
    from config.asgi import application  # noqa: PLC0415

    return application


def test_ping_is_answered_with_pong(application: ProtocolTypeRouter):
    async def exchange() -> None:
        communicator = ApplicationCommunicator(
            application,
            {
                "type": "websocket",
                "path": "/ws/ping/",
                "query_string": b"",
                "headers": [
                    (b"host", b"testserver"),
                    (b"origin", b"http://testserver"),
                ],
                "subprotocols": [],
            },
        )
        await communicator.send_input({"type": "websocket.connect"})
        accepted = await communicator.receive_output()
        assert accepted["type"] == "websocket.accept"

        await communicator.send_input({"type": "websocket.receive", "text": "ping"})
        reply = await communicator.receive_output()
        assert reply == {"type": "websocket.send", "text": "pong!"}

        await communicator.send_input({"type": "websocket.disconnect", "code": 1000})
        await communicator.wait()

    async_to_sync(exchange)()
