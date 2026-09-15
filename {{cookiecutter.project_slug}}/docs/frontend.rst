{% raw %}Frontend
========

The frontend is server rendered: Django templates, `htmx`_ for partial page updates, and
the UI library, which is `django-cotton`_ for reusable components, project-owned CSS and
a colour theme served for each request. Every asset comes from this origin and nothing is
built: there is no bundler and no package manager for the frontend. Every response carries
a nonce-based Content Security Policy, so templates hold no inline scripts, styles or event
handlers; the rules below keep the library within it.

.. _htmx: https://htmx.org
.. _django-cotton: https://django-cotton.com

Cotton
------

django-cotton compiles the ``<c-name>`` tags of a template into Django template tags before
Django parses it, through a template loader. ``config/settings/base.py`` configures it
explicitly rather than through Cotton's default app config, so the configuration is in the
settings where it can be read:

- ``django_cotton.apps.SimpleAppConfig`` is installed. Cotton's default config rewrites
  ``TEMPLATES`` at startup; this one leaves the settings as written. Both patch Django's
  template lexer globally at startup, so that a component's attributes may hold template
  syntax; that patch is Cotton's way of working and is not opted out of.
- ``APP_DIRS`` is off and the loaders are listed: Django's cached loader around Cotton's
  loader, then the filesystem and app directories loaders. Cotton's loader comes first so
  that every template is compiled before it is parsed, and its own directories cover the
  project's ``templates/`` and every installed app's.
- ``builtins`` lists Cotton's tag library and the UI library's filters, so no template
  loads them.
- ``COTTON_ENABLE_CONTEXT_ISOLATION = True``: a component renders with its own inputs,
  the request and the context processors, and never sees the calling template's variables.
  What a component needs, it is given. The next Cotton release renames the setting
  ``COTTON_ISOLATE_BY_DEFAULT`` and keeps the old name with a deprecation warning;
  ``ui/tests/test_isolation.py`` shows which name the installed release honours.

A component is a template under ``templates/cotton/``: ``<c-ui.button>`` is
``templates/cotton/ui/button.html``, dots naming directories and hyphens becoming
underscores. It declares the inputs it consumes with ``<c-vars>``; every other attribute
it is given reaches it as ``attrs``. Its content is the default slot, ``{{ slot }}``, and
a ``<c-slot name="header">`` inside it a named slot, ``{{ header }}``; slots are rendered
in the caller's template context before the component sees them.

Under ``DEBUG`` an error raised while a component renders can surface as a ``TypeError``
from Django's debug lexer rather than as the error itself, because Cotton's compiled tags
carry no source position. Read the underlying error in the traceback, or reproduce it in a
test, where the tests run with ``DEBUG`` off.

Writing attributes and URLs
---------------------------

Three filters, builtins of every template, are the only way a component writes a value
into an attribute. They live in ``ui/templatetags/ui.py``; the rules are in
``ui/attrs.py`` and ``ui/links.py``.

``{{ attrs|ui_attrs }}``
    The attributes the component did not declare, written onto its element. Forwarding is
    a developer interface: values come from the templates that call the component, not
    from users. The filter refuses, with ``ValueError``, a name that is not an attribute
    name, ``class`` (a component declares it and merges it once), ``style``, ``on*``,
    ``hx-on*`` and ``data-hx-on*`` (the policy forbids inline code), a name given twice in
    any letter case, a boolean where text is expected and text where a boolean is, and an
    htmx destination that leaves this origin. It refuses a dict, a list or any other
    structured value with ``TypeError`` rather than writing its Python representation.

    ``None`` writes nothing. ``True`` and ``False`` write HTML's boolean attributes such
    as ``disabled`` or ``required`` as present or absent; ``hidden`` also takes
    ``"until-found"``; ``aria-``, ``data-`` and ``hx-`` attributes take the words
    ``true`` and ``false``. Text is escaped. A marked-safe string keeps its entities and
    has its literal double quotes encoded, so it can never end the attribute. The htmx
    destinations ``hx-get``, ``hx-post``, ``hx-put``, ``hx-patch`` and ``hx-delete``, and
    ``hx-push-url`` or ``hx-replace-url`` when they carry a URL rather than a word, must
    be local: a relative reference with no scheme and no host. The ``data-hx-`` spellings
    follow the same rules.

``{{ value|ui_attr }}``
    One declared input in an attribute position, with the same encoding: escaped, or a
    marked-safe string with its double quotes encoded. Use it for every interpolation
    inside an attribute of a component, never a bare ``{{ value }}``.

``{{ url|ui_url }}`` and ``{{ url|ui_url:"local" }}``
    A URL, validated as the browser will receive it and then encoded. The ``navigation``
    policy, the default, accepts a relative reference or an absolute ``http`` or
    ``https`` URL with a hostname; the ``local`` policy, for htmx destinations, accepts a
    relative reference only. Both refuse an empty value, surrounding whitespace, control
    characters, backslashes and protocol-relative ``//host`` forms. A marked-safe value,
    the output of ``{% url %}`` for one, is decoded once before validation so an entity
    cannot hide a scheme; ordinary text is validated as written and escaped, so
    ``javascript&#58;`` stays the harmless literal it is. Other schemes, ``mailto:`` or
    ``tel:`` say, are written as plain HTML by the calling template, not through a
    component.

Tokens and palettes
-------------------

A token is a design value the components read, a CSS custom property with the ``--ui-``
prefix. The tokens that are not colours are in ``static/css/ui/tokens.css``: the font
stacks, the type sizes, the spacing scale, the radii, the shadows, the focus ring's width
and offset, the container width, and ``color-scheme``. The colour tokens are owned by
Python, in ``ui/palettes.py``, and served by the theme stylesheet described below.

There are 26 colour tokens. Ten may be overridden by a brand:

- ``bg`` and ``surface``, the page and the raised surfaces on it;
- ``fg`` and ``fg-muted``, the text and the secondary text;
- ``border``, the decorative border of cards and dividers, and ``border-control``, the
  boundary of inputs and buttons;
- ``accent``, ``accent-hover`` and ``accent-fg``, the brand colour of links and primary
  buttons, its hover state and the text on it;
- ``focus``, the focus ring.

Sixteen belong to the palette, four for each status ``info``, ``success``, ``warning`` and
``error``: the solid ``<status>`` for badges and indicators, ``<status>-fg`` for text on
the solid, ``<status>-text`` for text on the page and inside a tinted alert, and
``<status>-tint``, the alert's background. Inside a tinted alert, body text, links and the
dismiss control all use ``<status>-text``, and links are underlined.

A palette is a complete set of all 26 tokens in both a light and a dark set. Three are
built in, ``blue``, ``teal`` and ``violet``, and every one meets WCAG AA in every pair of
tokens that meet on the page, the adjacency table ``PAIRS`` in ``ui/palettes.py``: 4.5:1
for text (``fg`` and ``fg-muted`` on ``bg`` and ``surface``; ``accent`` and
``accent-hover`` on both as links; ``accent-fg`` on ``accent`` and ``accent-hover``; each
``<status>-text`` on ``bg``, ``surface`` and its tint; each ``<status>-fg`` on its solid)
and 3:1 for what is not text (``border-control`` on ``bg`` and ``surface``; ``focus`` on
``bg``, ``surface`` and every tint; each solid status on ``bg``, ``surface`` and its
tint). The focus ring is drawn outward with an offset, so the colour next to it is the
page, the surface or the tint, which the table checks. Hover states either switch between
checked pairs, the primary button from ``accent`` to ``accent-hover`` for one, or change
decoration only, so no unchecked colour appears. ``ui/tests/test_palettes.py`` checks
every palette against the table with the arithmetic in ``ui/contrast.py``, whose own tests
pin the reference ratios; a palette edit that breaks a pair fails there. To add a palette,
add its two sets to ``PALETTES``.

The theme
---------

A theme is both resolved colour sets, light and dark, plus the mode the page asked for.
Two settings choose it:

.. code-block:: python

    UI_PALETTE = "blue"  # blue, teal or violet
    UI_MODE = "system"  # system, light or dark

``system`` leaves the choice between the sets to the browser's preference; ``light`` or
``dark`` forces one, through the ``data-ui-mode`` attribute that ``base.html`` puts on the
root element and a matching ``color-scheme``, so native controls agree with the page. An
unknown palette or mode is reported by the system checks (``ui.E001``, ``ui.E002``).

The theme is served as a stylesheet, ``/ui/theme.css``, that ``base.html`` loads after
``tokens.css``: the light set on ``:root``, the dark set under
``prefers-color-scheme: dark`` unless light is forced, and again under
``[data-ui-mode="dark"]``. Its selectors and property names are fixed and its values are
validated colours; nothing else is interpolated. The response is ``Cache-Control:
private, no-store`` because it can depend on the request, and it opens no database
transaction, so an error page keeps its colours. It is a route, not a static file: it is
not collected and not hashed.

``ui/themes.py`` holds the pure functions, ``resolve``, ``validate`` and
``render_stylesheet``, and ``resolve_theme(request)``, the one place that reads the
settings and the request. The result is resolved once per request and shared by the
``ui_theme`` context processor and the stylesheet view. ``resolve_theme`` is the extension
point for an application's own source of colours, a company record for one: resolve the
record as an override of the configured theme with ``resolve(palette, mode, override)``,
``validate`` the result, and fall back to ``configured_theme()`` when it cannot be served,
logging which source failed. The configured theme is validated too; one that fails is a
configuration error, raised rather than served.
{%- endraw %}
