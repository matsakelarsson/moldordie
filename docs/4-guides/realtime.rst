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


If you don't use Traefik, you might have to configure your reverse proxy accordingly (example with Nginx_).

.. _Django Channels: https://channels.readthedocs.io/
.. _Nginx: https://www.nginx.com/blog/websocket-nginx/
