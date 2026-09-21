"""The server lifespan a web worker sends its last telemetry from.

Gunicorn's uvicorn worker re-raises the signal it was sent once it has stopped
serving, which ends the process before Gunicorn's own exit hooks or the SDK's
``atexit`` flush can run. What does run is the server's lifespan shutdown, which
uvicorn sends before it re-raises, so that is where this worker's exporters are told
to send what they are still holding (``docs/adr/0020``).

Django's handler answers no lifespan message, and neither does Channels' router, so
the wrapper answers them itself and passes every other scope through untouched.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING
from typing import Any

from .configure import SHUTDOWN_TIMEOUT_MILLIS
from .configure import shutdown

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

logger = logging.getLogger(__name__)

# The whole of a shutdown, however the exporters behave inside it: what stops this
# worker is a signal that will be re-raised, and a deployment waits for neither
MILLISECONDS = 1000
SHUTDOWN_TIMEOUT_SECONDS = SHUTDOWN_TIMEOUT_MILLIS / MILLISECONDS


async def flush() -> None:
    """Flush the exporters, in a thread and under a deadline of our own.

    The SDK's own timeouts are best-effort, so the deadline that decides how long a
    worker takes to go is this one. A flush that overruns it is given up on and said
    so; the process is on its way out either way.
    """
    try:
        await asyncio.wait_for(
            asyncio.to_thread(shutdown),
            timeout=SHUTDOWN_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        logger.warning(
            "Telemetry was not flushed within %ss of shutdown",
            SHUTDOWN_TIMEOUT_SECONDS,
        )


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
                await flush()
                await send({"type": "lifespan.shutdown.complete"})
                return

    return with_lifespan
