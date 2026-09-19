.. _frontend-guide:

Frontend: htmx and the UI library
=================================

Generated projects ship a server-rendered frontend with no Node.js toolchain:

- `htmx`_ adds partial page updates on top of regular links and forms. It is provided by `django-htmx`_, which bundles the htmx script and its extensions.
- `django-cotton`_ compiles ``<c-...>`` components, and the project's UI library supplies them: nine components under ``templates/cotton/ui/``, the stylesheets under ``static/css/ui/``, the ``ui`` app with the filters that write a component's attributes and URLs, the colour palettes, the theme stylesheet and the development showcase. Its contract for downstream developers is the generated project's ``docs/frontend.rst``; the decisions are in ``docs/adr/0009`` to ``docs/adr/0012``.

Every page works without JavaScript: links keep their ``href`` and forms keep their ``action``, htmx only enhances them. All assets are served from the project's own origin, and in production the manifest static files storage gives them hashed, cacheable file names.

.. _htmx: https://htmx.org
.. _django-htmx: https://django-htmx.readthedocs.io
.. _django-cotton: https://django-cotton.com

Cotton and the UI library
-------------------------

django-cotton is pinned in the generated ``pyproject.toml`` and configured in ``config/settings/base.py`` rather than by its default app config, so the template can read and test the configuration: ``django_cotton.apps.SimpleAppConfig`` is installed, ``APP_DIRS`` is off, the loaders are listed with Cotton's first behind Django's cached loader, Cotton's tag library and the ``ui`` filters are builtins, and ``COTTON_ENABLE_CONTEXT_ISOLATION`` is on so a component sees its inputs, the request and the context processors but not the calling template's variables. The generated ``ui/tests/test_isolation.py`` renders a page variable that a component must not see; when Cotton renames the setting, that test is what fails. ``test_ui_library`` in ``tests/test_cookiecutter_generation.py`` checks the wiring on the generated settings and that the nine components, the three stylesheets and the static collection and error page tests are generated.

The ``ui`` app is the library's Python side. ``ui/attrs.py`` and ``ui/links.py`` are the contracts behind the three filters a component writes attributes with: ``ui_attrs`` for the attributes it did not declare, ``ui_attr`` for a declared value and ``ui_url`` for a URL under the ``navigation`` or ``local`` policy; ``ui_label`` writes a bound field's label for the field component. ``ui/palettes.py`` owns the 26 colour tokens, the adjacency table of token pairs with the WCAG AA ratio each must meet, and the blue, teal and violet palettes; ``ui/contrast.py`` is the arithmetic, with its reference ratios pinned by tests. ``ui/themes.py`` resolves a request's theme with pure functions, the palette with ``UI_BRAND`` over it and, under ``DEBUG``, the showcase's session preview, falling back to the configured theme when a preview can no longer be served (``docs/adr/0011``), and ``ui/views.py`` serves it as ``/ui/theme.css``, private and uncached. ``ui/checks.py`` refuses an unknown palette or mode, a ``UI_BRAND`` that is not a mapping of the two colour sets, names a token a brand may not override or holds a value that is not a ``#RRGGBB`` colour, and a brand that breaks a pair of the adjacency table.

The components are Cotton templates: ``button``, ``link``, ``card``, ``alert``, ``badge``, ``field``, ``table``, ``pagination`` and ``empty-state``, each declaring its inputs with ``<c-vars>``, merging ``class`` once and forwarding every other attribute through ``ui_attrs``. ``test_components_write_attributes_through_the_filters`` scans every template under a ``cotton/`` directory of the generated project: an interpolation inside a start tag must be an attribute value ending in the filter its attribute needs (``ui_url:'local'`` for an htmx destination, ``ui_url`` for ``href`` and the like, ``ui_attr`` for anything else) or the forwarded attributes, and no component holds a ``<script>``, ``<style>`` or ``<link>``. The stylesheets are ``tokens.css``, ``base.css`` and ``components.css``, loaded by ``base.html`` in that order before the theme stylesheet and the project's ``css/project.css``; every class the library writes is prefixed ``ui-`` and every token ``--ui-``, the exceptions being two classes written by other code that it styles, Django's ``errorlist`` and htmx's ``htmx-indicator``; form controls are styled only inside the field component's wrappers, so the admin keeps its own look. The generated ``<project_slug>/tests/test_staticfiles.py`` collects the static files into a temporary directory under a manifest storage, so a broken reference fails in the project's own suite. The template's own suite does not run it; the CI integration rows do. ``Python 3.12 & WhiteNoise`` collects under WhiteNoise's storage, the one its production settings configure; every other row collects under Django's local manifest storage override, and its production storage, S3 for the default cloud provider, is not exercised. The error pages are cards on ``base.html``, and ``<project_slug>/tests/test_error_pages.py`` renders them with database access blocked.

The showcase at ``/ui/components/`` is registered in the ``DEBUG`` block of the generated ``config/urls.py``, next to the error page previews, and the navigation links to it only when its routes exist (``docs/adr/0012``). Each section renders an example template under ``templates/ui/examples/`` and shows it as written through the ``showcase`` tag library, next to the contract its component's template opens with; the sample form, the paged results and the theme preview are working examples of the htmx patterns below. ``test_ui_library`` checks that the examples are generated and that the registration sits in the ``DEBUG`` block. The generated ``ui/tests/test_showcase.py`` renders the page through a URL configuration of its own, since the tests run without ``DEBUG``, and asserts that the project's own configuration has no showcase.

Template Python and templates in this repository avoid ``{{``, ``{%`` and ``{#`` outside cookiecutter's own syntax and ``{% raw %}`` blocks, because Cookiecutter renders every file: the stylesheet is built by concatenation in ``ui/themes.py``, and the test fixtures under ``ui/tests/templates/`` are wrapped in ``{% raw %}`` like every template. Write template HTML the way djlint leaves it, ``profile = "django"`` with the generated ``[tool.djlint]``; ``H026`` is ignored there because ``<c-vars class />``, how a component declares the class it merges, reads to djlint as an empty class.

django-allauth's pages are bridged through ``templates/allauth/elements/``: ``button``, ``alert``, ``badge``, ``panel``, ``button_group``, ``provider`` and ``provider_list`` map onto the components, ``table`` and ``field`` are written by hand with the components' classes because allauth's content carries its own table sections and its own inputs, and the entrance layout and the password pages are one card. The opt-in email and phone change pages carry an inline ``style`` attribute in allauth's templates and stay documented exclusions.

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
        <c-ui.card id="user-profile">...</c-ui.card>
      {% endpartialdef profile %}
    {% endblock content %}

.. code-block:: python

    class UserDetailView(LoginRequiredMixin, HtmxTemplateMixin, DetailView):
        model = User
        htmx_partial = "profile"

``inline`` renders the partial in place for normal requests. For a request carrying the ``HX-Request`` header the mixin renders ``"users/user_detail.html#profile"``, that is only the partial, using Django's ``template.html#partial`` syntax. Boosted requests (``HX-Boosted``) expect a whole page and get the full template, and so does the request htmx sends when the back button reaches a page its history cache no longer holds (``HX-History-Restore-Request``, which htmx sends together with ``HX-Request``): htmx puts that answer where the whole page was. The mixin adds ``Vary: HX-Request, HX-History-Restore-Request`` to every response because the body depends on those headers; add the same headers, with ``django.views.decorators.vary.vary_on_headers``, to any other view whose body depends on it, otherwise a cache could serve a fragment to a full-page request. Function-based views do the same thing with ``render(request, "users/user_detail.html#profile", context)``.

The mixin also puts ``htmx_fragment`` in the context, true only when the partial is being rendered on its own. Templates branch on that flag rather than on ``request.htmx`` directly, which keeps the two apart: a template that reads the request varies by the header on *every* page that includes it, and ``base.html`` is included by all of them, so pages whose view sends no ``Vary`` would start varying silently.

The user profile pages show the pattern: the "My Info" button loads the edit form into the profile card with ``hx-get``/``hx-target``/``hx-push-url``, the form posts with ``hx-post``, and after the redirect the profile card is swapped back. The same links and form work as plain full-page navigation when JavaScript is off.

.. _template partial: https://docs.djangoproject.com/en/6.0/ref/templates/language/#template-partials

Messages
~~~~~~~~

``base.html`` renders Django's messages inside ``<div id="messages">`` from a partial named ``messages``, each an alert component that is dismissible and announced to assistive technology, ``role="status"`` or ``role="alert"`` by its level. Fragments include the same partial with ``{% include "base.html#messages" %}`` when ``htmx_fragment`` is set, and it is then marked with ``hx-swap-oob="true"``, so messages added during an htmx request (for example the "Information successfully updated" notice) are swapped into the page out-of-band. Because both the include and the attribute hang off that one flag, a full page renders exactly one messages container and never marks it for an out-of-band swap.

Expired sessions
~~~~~~~~~~~~~~~~

When a session expires, ``LoginRequiredMixin`` redirects to the login page. htmx would follow that redirect inside the request and swap the login page into the target element. ``HtmxLoginRedirectMiddleware`` (in ``<project_slug>/htmx.py``, listed right after ``HtmxMiddleware``) turns a redirect to ``LOGIN_URL`` into django-htmx's ``HttpResponseClientRedirect`` for htmx requests: a ``200`` with the ``HX-Redirect`` header, which makes the browser navigate to the login page with the ``?next=`` parameter intact. Boosted requests and redirects to any other URL, such as the redirect after a successful form post, are left alone.

Content Security Policy
-----------------------

Every response carries a nonce-based `Content Security Policy`_ from Django's ``ContentSecurityPolicyMiddleware``, configured as ``SECURE_CSP`` in ``config/settings/base.py``: scripts, styles, images, fonts and connections are limited to the project's own origin (plus ``data:`` images for the QR code of allauth's TOTP activation page), inline scripts need the per-request nonce, and inline styles, ``eval`` and framing are not allowed.

Rules for templates:

- Load scripts and styles from static files. There is no ``'unsafe-inline'``, so an inline ``<style>`` block, a ``style="..."`` attribute, an ``onclick="..."`` handler or an ``hx-on*`` attribute is blocked. ``style-src`` carries no nonce either, so a nonce does not rescue an inline style the way it does an inline script. The template's test suite checks generated templates for such code, and components and fragments hold no ``<script>``, ``<style>`` or ``<link>`` at all.
- The rare inline ``<script>`` needs ``nonce="{{ csp_nonce }}"``; the ``csp_nonce`` variable comes from the ``django.template.context_processors.csp`` context processor, and ``{% htmx_script %}`` adds it to the htmx tag on its own.
- htmx is configured through the ``htmx-config`` meta tag in ``base.html`` with ``allowEval: false``, ``allowScriptTags: false`` and ``includeIndicatorStyles: false``. That disables ``hx-on*`` attributes, ``js:`` prefixes in ``hx-vals``/``hx-headers`` and event filters such as ``click[ctrlKey]``; put such logic in ``static/js/project.js`` instead, which listens on the document so markup htmx swaps in needs no new listeners. The ``.htmx-indicator`` rules that htmx would otherwise inject live in ``static/css/ui/components.css``.
- Never cache a full page that renders the nonce: a cached nonce is no nonce. ``HtmxTemplateMixin`` only sets ``Vary`` headers and caches nothing.

Third-party pages: the Django admin, django-debug-toolbar and django-allauth work under the policy. The Swagger UI of drf-spectacular loads from a CDN with inline scripts, so ``config/urls.py`` exempts the admin-only ``api/docs/`` view with ``csp_override({})``; django-ninja serves its Swagger UI from local static files because ``ninja`` is in ``INSTALLED_APPS``. Django REST framework's browsable API keeps working but loses its inline syntax-highlighting styles. If you enable social login, add the provider's origin to ``form-action``; if you enable allauth's email or phone change pages, override their templates, which carry an inline ``style`` attribute. With ``realtime`` set to ``channels``, ``connect-src`` additionally allows ``ws:`` in ``local.py`` and ``wss:`` in ``production.py``.

Rolling out in production: set ``DJANGO_CSP_REPORT_URI`` to have browsers report violations (Sentry and most CSP services provide an endpoint) and ``DJANGO_CSP_REPORT_ONLY=True`` to switch the header to ``Content-Security-Policy-Report-Only`` while you check the reports; both are read in ``config/settings/production.py``.

.. _Content Security Policy: https://docs.djangoproject.com/en/6.0/ref/csp/

Forms
-----

Forms are rendered by Django's own form renderer. ``FORM_RENDERER = "django.forms.renderers.TemplatesSetting"`` lets the project override ``django/forms/field.html`` (in ``<project_slug>/templates/django/forms/``), which is one line, ``<c-ui.field :field="field" />``: every field of ``{{ form }}`` renders through the field component, with its label from ``ui_label`` (Django's ``label_tag`` without the form's suffix), the widget as Django renders it, the errors and the help text, and Django's ``aria-invalid`` and ``aria-describedby`` associations kept. Non-field errors and hidden fields stay as Django writes them. django-allauth's forms go through the same renderer via ``templates/allauth/elements/fields.html``.
