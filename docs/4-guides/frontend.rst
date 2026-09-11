.. _frontend-guide:

Frontend: htmx and Pico CSS
===========================

Generated projects ship a server-rendered frontend with no Node.js toolchain:

- `htmx`_ adds partial page updates on top of regular links and forms. It is provided by `django-htmx`_, which bundles the htmx script and its extensions.
- `Pico CSS`_ styles semantic HTML (``<nav>``, ``<article>``, ``<form>``, ``<table>``...) without utility classes. A pinned release is vendored in the project.

Every page works without JavaScript: links keep their ``href`` and forms keep their ``action``, htmx only enhances them. All assets are served from the project's own origin, and in production the manifest static files storage gives them hashed, cacheable file names.

.. _htmx: https://htmx.org
.. _django-htmx: https://django-htmx.readthedocs.io
.. _Pico CSS: https://picocss.com

Pico CSS
--------

Pico lives in ``<project_slug>/static/vendor/pico/``:

- ``pico.min.css``: the stylesheet, byte-for-byte identical to the upstream release.
- ``LICENSE.md``: the MIT licence of that release.
- ``pico.json``: the vendored version, the upstream source URL, the licence and the SHA-256 checksum of ``pico.min.css``.

The stylesheet is loaded by ``base.html`` through ``{% static 'vendor/pico/pico.min.css' %}``. The vendored files are excluded from pre-commit hooks and from editor clean-ups (see ``.editorconfig``) so the checksum stays valid.

To upgrade Pico:

#. Download ``css/pico.min.css`` and ``LICENSE.md`` from the new tag of the `Pico repository`_ into ``static/vendor/pico/``.
#. Compute the checksum, ``shasum -a 256 pico.min.css``, and update ``version``, ``source`` and ``sha256`` in ``pico.json``.
#. Run the test suite: ``tests/test_vendored_assets.py`` (template) and ``test_vendored_pico_intact`` (generated project) fail when the file and the metadata disagree.

.. _Pico repository: https://github.com/picocss/pico/releases

Project-specific styles go in ``static/css/project.css``, which is loaded after Pico and uses Pico's CSS variables (``--pico-primary``, ``--pico-del-color``...).

htmx
----

``django-htmx`` is installed in ``INSTALLED_APPS`` and its ``HtmxMiddleware`` sets ``request.htmx`` on every request. The script is rendered by ``{% htmx_script %}`` in ``base.html`` from django-htmx's own static files, so upgrading django-htmx upgrades htmx. When ``DEBUG`` is on the tag also loads the django-htmx debug extension, which shows Django error pages for failed htmx requests. With ``realtime`` set to ``channels`` the tag becomes ``{% htmx_script extensions="hx-ws" %}`` and the websocket extension is available as ``hx-ext="ws"`` (see :ref:`realtime`).

CSRF
~~~~

``base.html`` puts Django's CSRF token on the ``<body>`` element so htmx sends it with every request, including ones that are not form submissions:

.. code-block:: html

    <body hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'>

The ``CsrfViewMiddleware`` stays enabled, so an unsafe request without the header (or without the form's hidden field) is rejected with a 403. This works with ``CSRF_COOKIE_HTTPONLY = True`` because the token comes from the template, not from the cookie. The navigation is deliberately not boosted with ``hx-boost``: a boosted page swap would keep the ``<body>`` attribute, and with it a token that logging in has rotated.

Template partials
~~~~~~~~~~~~~~~~~

Views that answer htmx requests with a fragment instead of a full page keep the fragment in the same template, as a Django `template partial`_, and use ``HtmxTemplateMixin`` from ``<project_slug>/htmx.py``:

.. code-block:: django

    {% extends "base.html" %}

    {% block content %}
      {% partialdef profile inline %}
        <article id="user-profile">...</article>
      {% endpartialdef profile %}
    {% endblock content %}

.. code-block:: python

    class UserDetailView(LoginRequiredMixin, HtmxTemplateMixin, DetailView):
        model = User
        htmx_partial = "profile"

``inline`` renders the partial in place for normal requests. For a request carrying the ``HX-Request`` header the mixin renders ``"users/user_detail.html#profile"``, that is only the partial, using Django's ``template.html#partial`` syntax. Boosted requests (``HX-Boosted``) expect a whole page and get the full template. The mixin adds ``Vary: HX-Request`` to every response because the body depends on that header; add the same header, with ``django.views.decorators.vary.vary_on_headers``, to any other view whose body depends on it, otherwise a cache could serve a fragment to a full-page request. Function-based views do the same thing with ``render(request, "users/user_detail.html#profile", context)``.

The mixin also puts ``htmx_fragment`` in the context, true only when the partial is being rendered on its own. Templates branch on that flag rather than on ``request.htmx`` directly, which keeps the two apart: a template that reads the request varies by the header on *every* page that includes it, and ``base.html`` is included by all of them, so pages whose view sends no ``Vary`` would start varying silently.

The user profile pages show the pattern: the "My Info" button loads the edit form into the profile card with ``hx-get``/``hx-target``/``hx-push-url``, the form posts with ``hx-post``, and after the redirect the profile card is swapped back. The same links and form work as plain full-page navigation when JavaScript is off.

.. _template partial: https://docs.djangoproject.com/en/6.0/ref/templates/language/#template-partials

Messages
~~~~~~~~

``base.html`` renders Django's messages inside ``<div id="messages">`` from a partial named ``messages``. Fragments include the same partial with ``{% include "base.html#messages" %}`` when ``htmx_fragment`` is set, and it is then marked with ``hx-swap-oob="true"``, so messages added during an htmx request (for example the "Information successfully updated" notice) are swapped into the page out-of-band. Because both the include and the attribute hang off that one flag, a full page renders exactly one messages container and never marks it for an out-of-band swap.

Expired sessions
~~~~~~~~~~~~~~~~

When a session expires, ``LoginRequiredMixin`` redirects to the login page. htmx would follow that redirect inside the request and swap the login page into the target element. ``HtmxLoginRedirectMiddleware`` (in ``<project_slug>/htmx.py``, listed right after ``HtmxMiddleware``) turns a redirect to ``LOGIN_URL`` into django-htmx's ``HttpResponseClientRedirect`` for htmx requests: a ``200`` with the ``HX-Redirect`` header, which makes the browser navigate to the login page with the ``?next=`` parameter intact. Boosted requests and redirects to any other URL, such as the redirect after a successful form post, are left alone.

Content Security Policy
-----------------------

Every response carries a nonce-based `Content Security Policy`_ from Django's ``ContentSecurityPolicyMiddleware``, configured as ``SECURE_CSP`` in ``config/settings/base.py``: scripts, styles, images, fonts and connections are limited to the project's own origin (plus ``data:`` images for Pico's icons), inline scripts need the per-request nonce, and inline styles, ``eval`` and framing are not allowed.

Rules for templates:

- Load scripts and styles from static files. There is no ``'unsafe-inline'``, so an inline ``<style>`` block, a ``style="..."`` attribute or an ``onclick="..."`` handler is blocked. ``style-src`` carries no nonce either, so a nonce does not rescue an inline style the way it does an inline script. The template's test suite checks generated templates for such code.
- The rare inline ``<script>`` needs ``nonce="{{ csp_nonce }}"``; the ``csp_nonce`` variable comes from the ``django.template.context_processors.csp`` context processor, and ``{% htmx_script %}`` adds it to the htmx tag on its own.
- htmx is configured through the ``htmx-config`` meta tag in ``base.html`` with ``allowEval: false``, ``allowScriptTags: false`` and ``includeIndicatorStyles: false``. That disables ``hx-on*`` attributes, ``js:`` prefixes in ``hx-vals``/``hx-headers`` and event filters such as ``click[ctrlKey]``; put such logic in ``static/js/project.js`` instead. The ``.htmx-indicator`` rules that htmx would otherwise inject live in ``static/css/project.css``.
- Never cache a full page that renders the nonce: a cached nonce is no nonce. ``HtmxTemplateMixin`` only sets ``Vary`` headers and caches nothing.

Third-party pages: the Django admin, django-debug-toolbar and django-allauth work under the policy. The Swagger UI of drf-spectacular loads from a CDN with inline scripts, so ``config/urls.py`` exempts the admin-only ``api/docs/`` view with ``csp_override({})``; django-ninja serves its Swagger UI from local static files because ``ninja`` is in ``INSTALLED_APPS``. Django REST framework's browsable API keeps working but loses its inline syntax-highlighting styles. If you enable social login, add the provider's origin to ``form-action``; if you enable allauth's email or phone change pages, override their templates, which carry an inline ``style`` attribute. With ``realtime`` set to ``channels``, ``connect-src`` additionally allows ``ws:`` in ``local.py`` and ``wss:`` in ``production.py``.

Rolling out in production: set ``DJANGO_CSP_REPORT_URI`` to have browsers report violations (Sentry and most CSP services provide an endpoint) and ``DJANGO_CSP_REPORT_ONLY=True`` to switch the header to ``Content-Security-Policy-Report-Only`` while you check the reports; both are read in ``config/settings/production.py``.

.. _Content Security Policy: https://docs.djangoproject.com/en/6.0/ref/csp/

Forms
-----

Forms are rendered by Django's own form renderer. ``FORM_RENDERER = "django.forms.renderers.TemplatesSetting"`` lets the project override ``django/forms/field.html`` (in ``<project_slug>/templates/django/forms/``), which produces Pico markup: a ``<label>``, the widget, the error list and a ``<small>`` help text. Django adds ``aria-invalid`` and ``aria-describedby`` to widgets with errors, which Pico uses for its validation styles. ``{{ form }}`` is all a template needs; django-allauth's forms go through the same renderer via ``templates/allauth/elements/fields.html``.
