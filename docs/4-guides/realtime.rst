.. _realtime:

========
Realtime
========

Every generated project is served through ASGI: Uvicorn in development and Gunicorn with the Uvicorn worker in production. Selecting ``channels`` for the ``realtime`` option additionally wires `Django Channels`_ into ``config/asgi.py``, so the project can accept websocket connections.

What you get
------------

- ``config/asgi.py`` routes HTTP to Django and websockets through ``AllowedHostsOriginValidator`` and ``AuthMiddlewareStack`` to the URL patterns in ``config/websocket.py``.
- ``config/websocket.py`` contains a ``PingConsumer`` mounted at ``/ws/ping/`` as a starting point for your own consumers.
- ``CHANNEL_LAYERS`` uses the in-memory layer in the local and test settings, so no Redis is needed while developing, and ``channels_redis`` on ``REDIS_URL`` in the production settings.
- ``<project_slug>/tests/test_websocket.py`` shows how to test a consumer with ``asgiref.testing.ApplicationCommunicator``. The helpers in ``channels.testing`` import Daphne, so add ``daphne`` to the development dependencies if you prefer them.
- The ``types-channels`` stubs are installed, so consumers are covered by the strict mypy configuration.

Usage
-----

JavaScript example: ::

    > ws = new WebSocket('ws://localhost:8000/ws/ping/') // or 'wss://<mydomain.com>/ws/ping/' in prod
    WebSocket {url: "ws://localhost:8000/ws/ping/", readyState: 0, bufferedAmount: 0, onopen: null, onerror: null, …}
    > ws.onmessage = event => console.log(event.data)
    event => console.log(event.data)
    > ws.send("ping")
    undefined
    pong!


From templates with htmx
~~~~~~~~~~~~~~~~~~~~~~~~

``base.html`` loads htmx with its websocket extension, ``{% htmx_script extensions="hx-ws" %}``, so templates can talk to a consumer without writing JavaScript. The Content Security Policy allows websocket connections to the project's own origin (``ws:`` in ``local.py``, ``wss:`` in ``production.py``). In markup the extension is ``hx-ext="ws"``:

.. code-block:: html

    <div hx-ext="ws" ws-connect="/ws/ping/">
      <form ws-send>
        <input type="hidden" name="message" value="ping" />
        <button type="submit">Ping</button>
      </form>
      <div id="pong"></div>
    </div>

Two things differ from the JavaScript example above. ``ws-send`` transmits the form as JSON, ``{"message": "ping", "HEADERS": {...}}``, and the extension only swaps incoming HTML that carries an ``id``, out-of-band. A consumer written for it therefore parses JSON and answers with markup::

    class PingConsumer(AsyncWebsocketConsumer):
        async def receive(self, text_data=None, bytes_data=None):
            if json.loads(text_data)["message"] == "ping":
                await self.send(text_data='<div id="pong">pong!</div>')

The shipped ``PingConsumer`` keeps the plain text protocol so both examples stay small; adapt it when you build on the htmx side. Origins are checked by ``AllowedHostsOriginValidator``; websockets need no CSRF token.

If you don't use Traefik, you might have to configure your reverse proxy accordingly (example with Nginx_).

.. _Django Channels: https://channels.readthedocs.io/
.. _Nginx: https://www.nginx.com/blog/websocket-nginx/
