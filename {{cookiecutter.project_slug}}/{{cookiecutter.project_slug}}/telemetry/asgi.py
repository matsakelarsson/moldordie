"""The server lifespan a web worker sends its last telemetry from.

Gunicorn's uvicorn worker re-raises the signal it was sent once it has stopped
serving, which ends the process before Gunicorn's own exit hooks or the SDK's
``atexit`` flush can run. What does run is the server's lifespan shutdown, which
uvicorn sends before it re-raises, so that is where this worker's exporters are told
to send what they are still holding (``docs/adr/0020``).

Django's handler answers no lifespan message, and neither does Channels' router, so
the wrapper answers them itself and passes every other scope through untouched.

The deadline the flush keeps is ``telemetry/configure.py``'s, and it is kept there
rather than here: a Celery worker process stops on the same terms and reaches no
lifespan. What arrives here is the answer, and the shutdown is completed either way —
a server told that its shutdown failed would say so as an unsupported protocol.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from typing import Any

from .configure import flush

if TYPE_CHECKING:
    from collections.abc import Awaitable
    from collections.abc import Callable
    from collections.abc import Mapping

    # What the wrapper is handed, as Django's handler annotates it. The application
    # it wraps keeps its arguments open: Django's handler and Channels' router are
    # each annotated in their own terms, and either may be the one underneath.
    Scope = dict[str, Any]
    Message = Mapping[str, Any]
    Receive = Callable[[], Awaitable[Message]]
    Send = Callable[[Message], Awaitable[None]]
    Application = Callable[..., Awaitable[None]]


def flushing_on_shutdown(application: Application) -> Application:
    """``application``, answering the server's lifespan and flushing on shutdown."""

    async def with_lifespan(scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "lifespan":
            await application(scope, receive, send)
            return
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                await asyncio.to_thread(flush)
                await send({"type": "lifespan.shutdown.complete"})
                return

    return with_lifespan
