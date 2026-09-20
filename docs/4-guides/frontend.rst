.. _frontend-guide:

Frontend: htmx, Tailwind CSS and daisyUI
========================================

Generated projects ship a server-rendered frontend with no Node.js toolchain:

- `htmx`_ adds partial page updates on top of regular links and forms. It is provided by `django-htmx`_, which bundles the htmx script and its extensions.
- `Tailwind CSS`_ and `daisyUI`_'s components give the pages their look, through `django-tailwind-cli`_, which downloads Tailwind's standalone CLI with daisyUI bundled and runs it from ``manage.py``. The project's own daisyUI theme, every value written out, is the default look and the place a developer restyles the site from. The generated project's ``docs/frontend.rst`` is the guide for downstream developers; the decision is in ``docs/adr/0016``.

Every page works without JavaScript: links keep their ``href`` and forms keep their ``action``, htmx only enhances them, and the project ships no script of its own, so what does not involve the server is one of daisyUI's CSS-only mechanisms. All assets are served from the project's own origin, and in production the manifest static files storage gives them hashed, cacheable file names.

.. _htmx: https://htmx.org
.. _django-htmx: https://django-htmx.readthedocs.io
.. _Tailwind CSS: https://tailwindcss.com
.. _daisyUI: https://daisyui.com
.. _django-tailwind-cli: https://django-tailwind-cli.readthedocs.io

Tailwind CSS and daisyUI
------------------------

django-tailwind-cli is pinned in the generated ``pyproject.toml`` as a runtime dependency, because the production image builds the stylesheet without the dev group. ``config/settings/base.py`` installs ``django_tailwind_cli`` and holds every ``TAILWIND_CLI_*`` setting, in that module only, since the image builds under the test settings: ``TAILWIND_CLI_USE_DAISY_UI`` selects the ``tailwindcss-extra`` build of the CLI, ``TAILWIND_CLI_VERSION`` pins its release, ``TAILWIND_CLI_SRC_CSS`` names the source stylesheet and ``TAILWIND_CLI_DIST_CSS`` the built one. ``TEMPLATES`` uses Django's own loaders. ``test_tailwind_and_daisyui`` in ``tests/test_cookiecutter_generation.py`` checks the wiring, that no other settings module names a Tailwind setting, and that a generated project holds neither a built stylesheet, nor the CLI, nor a script of its own; ``test_docker_builds_and_watches_the_stylesheet`` checks the image build and the watcher service. Neither runs the Tailwind CLI: the integration scripts do.

The source stylesheet is ``<project_slug>/styles/main.css``, outside the static directories, because a manifest storage cannot resolve its ``@import "tailwindcss"``. It turns Tailwind's automatic source detection off and names the package as its source, so the scan is the same on every machine and in the production image, where ``.dockerignore`` leaves ``.gitignore`` out; it enables daisyUI's ``light`` and ``dark`` (the latter for a browser that prefers a dark colour scheme) and the typography plugin, and it holds the ``.htmx-indicator`` rules that htmx may not inject under the policy. ``styles/theme.css`` is the project's own theme, ``brand``, the default: it starts from daisyUI's ``light``, with secondary, accent and the status colours darkened to a contrast of at least 4.5:1 as text on the base colours and beneath their ``-content`` colours, which was computed once for the shipped values and is checked by no test. Neither file may hold ``{{``, ``{%`` or ``{#``, because Cookiecutter renders them.

The built stylesheet, ``<project_slug>/static/css/tailwind.css``, is never generated and never committed. The watcher rebuilds it in development; the production image builds it in its build stage, with the CLI in a build cache. The generated ``<project_slug>/tests/test_staticfiles.py`` builds the stylesheet with the Tailwind CLI into a temporary directory, which leaves the working tree as it was, collects the static files into another under a manifest storage, and looks the rules the templates rely on up in the built file, so a source stylesheet that does not build, a broken reference or a variant that compiles to nothing fails in the project's own suite. Its first run downloads the CLI that ``TAILWIND_CLI_VERSION`` names (``docs/adr/0016``). The template's own suite does not run it; the CI integration rows do. ``Python 3.12 & WhiteNoise`` collects under WhiteNoise's storage, the one its production settings configure; every other row collects under Django's local manifest storage override. The default cloud provider's production storage, ``S3ManifestStaticStorage``, is the same ``ManifestFilesMixin`` over a bucket, so what no test exercises is the upload rather than the hashing. The error pages are daisyUI heroes on ``base.html``, and ``<project_slug>/tests/test_error_pages.py`` renders them with database access blocked.

Every theme daisyUI ships is enabled next to ``brand``, listed one by one in ``main.css`` (``themes: all`` would make daisyUI's ``light`` a second default), and the navigation offers them in the theme picker (``docs/adr/0017``): a form of ``theme-controller`` radio buttons, which daisyUI applies in CSS alone, posted through htmx to ``set_theme`` in ``<project_slug>/themes.py``, which keeps the choice in a cookie; the ``theme`` context processor reads it back and ``base.html`` writes it as ``data-theme``. ``THEMES`` is a tuple, so that the reader can read it past the functions of its module, and it repeats the stylesheet's list: the generated ``tests/test_themes.py`` compares the two, and ``test_themes`` here checks that a generated project starts with all of daisyUI's. ``<main>`` carries ``hx-history-elt`` so that htmx's history never restores a picker of the past.

The examples page, ``<project_slug>/examples/`` with its templates under ``templates/examples/``, shows daisyUI components and htmx patterns as the project writes them: a form validated on the server, a filtered and paged table that pushes its address, a toggle, lazy tabs, a dialog held open by daisyUI's ``modal-open`` and messages out of band. Each example is rendered live and shown as written, from the template's source, of the examples ``examples/content.py`` names only. The page is routed in every environment and linked from the navigation, which asks for the route first, so a project deletes the package, the templates and one line of ``config/urls.py`` and nothing else. Because it is public it keeps nothing on the server: its views open no transaction, and their tests run without database access. It is not an installed app. ``test_examples_page`` checks the route's place outside the ``DEBUG`` block, the conditional link and that the templates are the ones the page names.

Tailwind generates a rule only for a class name it finds written out in a scanned file, so templates choose between whole class names and never assemble one; ``test_class_names_are_written_whole`` checks the templates for a name glued to an interpolation, which does not prove that every class used is in the built stylesheet. There is no component layer between a template and daisyUI's classes: markup used twice is an ``{% include %}`` or a partial.

Forms render through the project's overrides of Django's form templates: ``django/forms/field.html`` keeps Django's associations between a widget, its label, its help text and its errors, the widget templates under ``django/forms/widgets/`` give each control daisyUI's class for its kind and merge the widget's own, ``aria-invalid``, which Django sets, is what colours an invalid control, and ``errors/list/ul.html`` styles the error list. Django's ``attrs.html`` is not overridden, because the admin's widgets include it; the renderer is global, so the admin's fields come through the same templates, keep their own classes and ignore daisyUI's, since the admin never loads the stylesheet.

django-allauth's elements are all overridden under ``templates/allauth/elements/``, because Tailwind's preflight leaves a bare element without a look: ``button``, ``alert``, ``badge``, ``panel``, ``button_group``, ``provider``, ``provider_list``, ``table``, ``h1``, ``h2``, ``hr``, ``details``, ``form`` and ``img`` in daisyUI's classes, ``field`` by hand with the classes and associations of the form templates, and ``fields`` through Django's renderer. The entrance layout and the password pages are one card, the management pages stack their panels, and both layouts underline the links allauth writes bare. The opt-in email and phone change pages carry an inline ``style`` attribute in allauth's templates and stay documented exclusions. The generated ``tests/test_forms.py``, ``test_allauth.py`` and ``test_pages.py`` render all of these.

Template Python, templates and stylesheets in this repository avoid ``{{``, ``{%`` and ``{#`` outside cookiecutter's own syntax and ``{% raw %}`` blocks, because Cookiecutter renders every file; the test fixtures under ``<project_slug>/tests/templates/`` are wrapped in ``{% raw %}`` like every template. Write template HTML the way djlint leaves it, ``profile = "django"`` with the generated ``[tool.djlint]``: this repository has no djlint configuration of its own, and ``test_djlint_check_passes`` holds the generated output to it. ``test_no_trace_of_a_removed_frontend`` scans every generated file of every combination for what this template's earlier frontends left behind and for a Node.js toolchain's tokens, so generated prose avoids those words.

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
        <article class="card" id="user-profile">...</article>
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

``base.html`` renders Django's messages inside ``<div id="messages">`` from a partial named ``messages``, each a daisyUI alert that is announced to assistive technology, ``role="status"`` or ``role="alert"`` by its level, and dismissed without a script: its close control is a visually hidden checkbox, and the alert carries ``has-[:checked]:hidden``. Fragments include the same partial with ``{% include "base.html#messages" %}`` when ``htmx_fragment`` is set, and it is then marked with ``hx-swap-oob="true"``, so messages added during an htmx request (for example the "Information successfully updated" notice) are swapped into the page out-of-band. Because both the include and the attribute hang off that one flag, a full page renders exactly one messages container and never marks it for an out-of-band swap.

Expired sessions
~~~~~~~~~~~~~~~~

When a session expires, ``LoginRequiredMixin`` redirects to the login page. htmx would follow that redirect inside the request and swap the login page into the target element. ``HtmxLoginRedirectMiddleware`` (in ``<project_slug>/htmx.py``, listed right after ``HtmxMiddleware``) turns a redirect to ``LOGIN_URL`` into django-htmx's ``HttpResponseClientRedirect`` for htmx requests: a ``200`` with the ``HX-Redirect`` header, which makes the browser navigate to the login page with the ``?next=`` parameter intact. Boosted requests and redirects to any other URL, such as the redirect after a successful form post, are left alone.

Content Security Policy
-----------------------

Every response carries a nonce-based `Content Security Policy`_ from Django's ``ContentSecurityPolicyMiddleware``, configured as ``SECURE_CSP`` in ``config/settings/base.py``: scripts, styles, images, fonts and connections are limited to the project's own origin (plus ``data:`` images for the QR code of allauth's TOTP activation page and the few parts daisyUI draws with them), inline scripts need the per-request nonce, and inline styles, ``eval`` and framing are not allowed.

Rules for templates:

- Load scripts and styles from static files. There is no ``'unsafe-inline'``, so an inline ``<style>`` block, a ``style="..."`` attribute, an ``onclick="..."`` handler or an ``hx-on*`` attribute is blocked. ``style-src`` carries no nonce either, so a nonce does not rescue an inline style the way it does an inline script. The template's test suite checks generated templates for such code, and fragments hold no ``<script>``, ``<style>`` or ``<link>`` at all.
- The rare inline ``<script>`` needs ``nonce="{{ csp_nonce }}"``; the ``csp_nonce`` variable comes from the ``django.template.context_processors.csp`` context processor, and ``{% htmx_script %}`` adds it to the htmx tag on its own.
- htmx is configured through the ``htmx-config`` meta tag in ``base.html`` with ``allowEval: false``, ``allowScriptTags: false`` and ``includeIndicatorStyles: false``. That disables ``hx-on*`` attributes, ``js:`` prefixes in ``hx-vals``/``hx-headers`` and event filters such as ``click[ctrlKey]``; such logic becomes a request to the server or one of daisyUI's CSS-only mechanisms, since the project ships no script. The ``.htmx-indicator`` rules that htmx would otherwise inject live in ``styles/main.css``. daisyUI documents a few components with a ``style`` attribute for a value (``radial-progress``, ``countdown``); write it as an arbitrary property class, ``[--value:70]``, instead.
- Never cache a full page that renders the nonce: a cached nonce is no nonce. ``HtmxTemplateMixin`` only sets ``Vary`` headers and caches nothing.

Third-party pages: the Django admin, django-debug-toolbar and django-allauth work under the policy. The Swagger UI of drf-spectacular loads from a CDN with inline scripts, so ``config/urls.py`` exempts the admin-only ``api/docs/`` view with ``csp_override({})``; django-ninja serves its Swagger UI from local static files because ``ninja`` is in ``INSTALLED_APPS``. Django REST framework's browsable API keeps working but loses its inline syntax-highlighting styles. If you enable social login, add the provider's origin to ``form-action``; if you enable allauth's email or phone change pages, override their templates, which carry an inline ``style`` attribute. With ``realtime`` set to ``channels``, ``connect-src`` additionally allows ``ws:`` in ``local.py`` and ``wss:`` in ``production.py``.

Rolling out in production: set ``DJANGO_CSP_REPORT_URI`` to have browsers report violations (Sentry and most CSP services provide an endpoint) and ``DJANGO_CSP_REPORT_ONLY=True`` to switch the header to ``Content-Security-Policy-Report-Only`` while you check the reports; both are read in ``config/settings/production.py``.

.. _Content Security Policy: https://docs.djangoproject.com/en/6.0/ref/csp/

Forms
-----

Forms are rendered by Django's own form renderer. ``FORM_RENDERER = "django.forms.renderers.TemplatesSetting"`` lets the project override ``django/forms/field.html`` and the widget templates (in ``<project_slug>/templates/django/forms/``), so every field of ``{{ form }}`` gets daisyUI's classes with the label, the widget, the errors and the help text in that order and Django's ``aria-invalid`` and ``aria-describedby`` associations kept. Non-field errors and hidden fields stay as Django writes them. django-allauth's forms go through the same renderer via ``templates/allauth/elements/fields.html``.
