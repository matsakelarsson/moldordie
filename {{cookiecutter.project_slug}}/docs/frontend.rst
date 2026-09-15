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
underscores (``<c-ui.empty-state>`` is ``empty_state.html``). The library's components are
listed under `Components`_ below. It declares the inputs it consumes with ``<c-vars>``; every other attribute
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
Three settings configure it:

.. code-block:: python

    UI_PALETTE = "blue"  # blue, teal or violet
    UI_MODE = "system"  # system, light or dark
    UI_BRAND: dict[str, dict[str, str]] = {"light": {}, "dark": {}}

``system`` leaves the choice between the sets to the browser's preference; ``light`` or
``dark`` forces one, through the ``data-ui-mode`` attribute that ``base.html`` puts on the
root element and a matching ``color-scheme``, so native controls agree with the page. An
unknown palette or mode is reported by the system checks (``ui.E001``, ``ui.E002``).

``UI_BRAND`` is the deployment's brand: for each set, colours for the ten tokens a brand
may override, named without the ``--ui-`` prefix, each a ``#RRGGBB`` colour. A set or a
token left out keeps the palette's colour:

.. code-block:: python

    UI_BRAND = {
        "light": {"accent": "#0b57d0", "accent-hover": "#0842a0", "focus": "#0842a0"},
        "dark": {"accent": "#a8c7fa", "accent-hover": "#d3e3fd", "focus": "#d3e3fd"},
    }

The status tokens belong to the palette, so a brand never changes what an error looks
like; it can still change the surfaces a status colour sits on, so the palette with the
brand over it is checked against the whole adjacency table. The system checks report a
``UI_BRAND`` that is not such a mapping, a token a brand may not override and a value that
is not a ``#RRGGBB`` colour (``ui.E003``), and every pair the result no longer meets
(``ui.E004``).

The theme is served as a stylesheet, ``/ui/theme.css``, that ``base.html`` loads after
``tokens.css``: the light set on ``:root``, the dark set under
``prefers-color-scheme: dark`` unless light is forced, and again under
``[data-ui-mode="dark"]``. Its selectors and property names are fixed and its values are
validated colours; nothing else is interpolated. The response is ``Cache-Control:
private, no-store`` because it can depend on the request. It opens no database transaction
and, without ``DEBUG``, when no session preview is read, needs no database at all, so an
error page keeps its colours. It is a route, not a static file: it is not collected and not
hashed.

``ui/themes.py`` holds the pure functions: ``resolve`` applies overrides to a palette,
``validate`` says what keeps a theme from being served, ``override_problems`` what keeps an
override from applying, ``servable_theme`` runs them and raises ``InvalidThemeError`` with
every problem found, ``preview_theme`` resolves a preview, and ``render_stylesheet`` writes
the CSS. ``configured_theme()`` resolves the settings; a configured theme that cannot be
served is a configuration error, raised rather than served. ``resolve_theme(request)``
resolves a request's theme once, for the ``ui_theme`` context processor and the stylesheet
view alike: the configured theme or, under ``DEBUG``, the preview the showcase keeps in the
session (see `The showcase`_). A preview that can no longer be served, because a palette or
``UI_BRAND`` changed beneath it, is logged as a warning, removed from the session and
replaced by the configured theme. ``resolve_theme`` is also where an application resolves
its own source of colours; see `From a preview to a company's colours`_.

Stylesheets
-----------

``base.html`` loads the stylesheets in this order, and nothing else does:

#. ``css/ui/tokens.css``: the tokens that are not colours.
#. ``css/ui/base.css``: a small reset, the typography, the focus ring, the page header and
   navigation, the layout helpers (``ui-container``, ``ui-main``, ``ui-stack``,
   ``ui-actions``, ``ui-muted``, ``ui-visually-hidden``) and the reduced-motion rule.
#. ``css/ui/components.css``: the components' rules, the form controls inside the field
   component's wrappers, and htmx's ``htmx-indicator`` rules, which htmx would otherwise
   inject as an inline stylesheet the policy forbids.
#. ``/ui/theme.css``: the colours, resolved for the request.
#. ``css/project.css``: the project's own rules, empty to begin with. Override a token
   there to change every component that reads it, or add rules of your own.

Every class of the library starts with ``ui-`` and every token with ``--ui-``. Form
controls are styled only inside the field component's wrappers, so the admin and other
pages with their own styles are untouched. Expandable content is the browser's
``<details>`` element, which ``base.css`` styles; there is no component for it.

Components
----------

Every component follows the same rules. It declares the inputs it consumes with
``<c-vars>``; ``class`` is one of them, merged once into the element's own classes, so an
element never carries two ``class`` attributes. A variant it does not know gets the
default. Every other attribute it is given is forwarded to its documented element through
``ui_attrs``, under the contract above: an id, ``data-`` and ``aria-`` attributes, and the
htmx attributes that stay on this origin. Text in a slot is the caller's markup, escaped
by Django as usual; a label is translated where the component writes it. A component
queries no model, decides no permission, embeds no URL and invents no id.

``<c-ui.button>``
    A native ``<button>``. ``type`` defaults to ``button``; pass ``type="submit"`` for the
    button that submits a form. ``variant`` is ``primary`` (the default), ``secondary``,
    ``danger`` or ``quiet``; ``size`` is ``normal`` or ``small``. ``disabled`` is the native
    attribute, forwarded. The content is the label.

``<c-ui.link>``
    A native ``<a>``; ``href`` is required and validated under the navigation policy.
    ``appearance`` is ``plain`` (the default, an underlined link) or ``button``, which
    takes the button's ``variant`` and ``size``. A link is never disabled and never
    ``role="button"``: leave it out instead.

``<c-ui.card>``
    An ``<article>`` on a raised surface. The content is the body, when there is any; the
    ``header`` slot holds the caller's heading markup and the ``actions`` slot the controls
    that act on the card, laid out as an action group. The caller gives it an ``id`` when
    something targets it.

``<c-ui.alert>``
    A notice. ``level`` is ``info`` (the default, which Django's ``debug`` also gets),
    ``success``, ``warning`` or ``error``; ``title`` is a leading line. ``dismissible``
    adds a button marked ``data-ui-dismiss`` that ``project.js`` answers by removing the
    root, marked ``data-ui-alert``. ``announce`` is for a message that arrives after the
    page loaded: it adds ``role="status"`` for info and success and ``role="alert"`` for
    warning and error. The messages partial passes both; a notice that is in the page from
    the start passes neither.

``<c-ui.badge>``
    A short label whose meaning is in its text. ``level`` is ``neutral`` (the default),
    ``info``, ``success``, ``warning`` or ``error``.

``<c-ui.field>``
    One field of a form, given a bound field: ``<c-ui.field :field="form.name" />``. It
    writes the label, the widget as Django renders it, the errors and the help text, in
    that order, and keeps Django's associations: ``aria-invalid`` and ``aria-describedby``
    on the widget, the ``<id>_error`` id on the error list and ``<id>_helptext`` on the
    help text. A hidden field is its widget alone; a widget that asks for a fieldset,
    radio buttons or a checkbox group, gets one with a ``<legend>``; a checkbox sits inside
    its label. See `Forms`_.

``<c-ui.table>``
    A native ``<table>`` in a container that scrolls sideways on narrow screens.
    ``caption`` names it; the ``head`` slot holds the header row, wrapped in ``<thead>``;
    the content is the body rows, wrapped in ``<tbody>``. There is no client-side sorting.

``<c-ui.pagination>``
    Navigation between the pages of a Django page object, ``:page="page_obj"``. The view
    supplies the URLs: ``previous_url``, ``next_url`` and optionally ``page_urls``, pairs
    of a page number and its URL, in which a pair with an empty URL is an ellipsis; without
    ``page_urls`` the page's position is written as text. The current page carries
    ``aria-current="page"``; a previous or next page that does not exist is text, not a
    link. ``target``, a CSS selector, makes every link also an htmx request: ``hx-get`` to
    the same URL under the local policy, ``hx-target`` to the selector,
    ``hx-swap="outerHTML"`` and ``hx-push-url="true"``. The target must then contain both
    the results and the component, and the fragment the view returns must reproduce it
    with its id. ``label`` names the navigation for assistive technology, "Pagination" by
    default.

``<c-ui.empty-state>``
    What a card or a results area shows when there is nothing to list: ``title``, the
    content as the explanation, and an ``actions`` slot with what the reader can do.

A page uses them like this:

.. code-block:: django

    <c-ui.card id="user-profile">
      <c-slot name="header">
        <h1>{{ object.display_name }}</h1>
      </c-slot>
      <c-slot name="actions">
        <c-ui.link href="{% url 'users:update' %}"
                   appearance="button"
                   hx-get="{% url 'users:update' %}"
                   hx-target="#user-profile"
                   hx-swap="outerHTML"
                   hx-push-url="true">{% translate "My Info" %}</c-ui.link>
      </c-slot>
    </c-ui.card>

The tests in ``ui/tests/test_components.py`` render every component from a page under
``ui/tests/templates/tests/``, so Cotton's compiler and loader run on them, and read the
result with the parser in ``ui/tests/markup.py``. In development, every component is also
on `The showcase`_, rendered from an example shown beside it as written.

Forms
-----

``FORM_RENDERER`` is Django's ``TemplatesSetting`` renderer, and
``templates/django/forms/field.html`` is one line: ``<c-ui.field :field="field" />``. So
``{{ form }}``, ``form.as_div`` and ``field.as_field_group`` all render every field
through the component, non-field errors and hidden fields staying as Django writes them,
and a field placed by hand with ``<c-ui.field>`` looks the same. The component renders the
widget itself, ``{{ field }}``, never the field group, so nothing recurses.

The label comes from ``ui_label``, a filter of the library: ``{{ field|ui_label }}`` is
Django's ``label_tag`` with the library's class and without the form's label suffix,
``{{ field|ui_label:"legend" }}`` the same as a ``<legend>``. Django writes no tag for a
field without an id (``auto_id=False``), and the filter then wraps the text in a
``<span>`` of the same class. A widget with an id of its own keeps it, and a label set on
the bound field is the one shown. ``ui/tests/test_field.py`` covers each of these.

Messages and scripts
--------------------

``base.html`` renders Django's messages inside ``<div id="messages">`` from the partial
``messages``, one ``<c-ui.alert>`` per message with ``dismissible`` and ``announce``, its
level from the message's level tag. A fragment includes ``base.html#messages`` when
``htmx_fragment`` is set, and the container is then marked ``hx-swap-oob="true"``, so
messages added during an htmx request are swapped into the page out of band.

Behaviour lives in ``static/js/project.js`` and in files like it, loaded by ``base.html``:
the policy allows no inline code, and a component or a fragment holds no ``<script>``,
``<style>`` or ``<link>`` at all; the profile views' tests check their fragments for them.
``project.js`` listens on the document, so markup htmx swaps in later needs no new
listeners; it dismisses an alert from its ``data-ui-dismiss`` button by removing the
``data-ui-alert`` root.

django-allauth
--------------

allauth's pages are its own templates, built from elements it renders through
``templates/allauth/elements/``. The overrides there bridge its elements onto the
components:

- ``button`` is a link drawn as a button when it has an ``href``, else a button that
  submits, as allauth's own does; its tags choose the variant, ``danger`` or ``delete``,
  ``link`` (quiet) and ``secondary``, and the ``form``, ``id``, ``name`` and ``value`` it
  names are forwarded when given, even empty.
- ``alert`` is an alert without ``announce``; ``badge`` maps the tags ``success``,
  ``warning``, ``danger`` (error) and ``primary`` (info) onto the levels; ``panel`` is a
  card with a second-level heading; ``button_group`` is an action group, stacked when
  allauth asks for ``vertical``; ``provider_list`` and ``provider`` are a list of secondary
  button-links.
- ``table`` gets the table component's markup by hand, because allauth's content carries
  its own ``<thead>`` and ``<tbody>``.
- ``field``, for the inputs allauth writes outside a Django form, is written by hand with
  the field component's classes and associations. ``fields`` renders the form through
  Django, so through the component.
- ``form``, the headings, ``p``, ``hr``, ``img``, ``details`` and the table cells stay
  allauth's own.

The entrance layout (sign in, sign up, ...) and the password pages are one card; the
management pages stack their panels. The opt-in email and phone change pages carry an
inline ``style`` attribute in allauth's templates and are not overridden: override them
before enabling those flows. ``ui/tests/test_allauth.py`` renders the elements and the
pages.

Error pages
-----------

``403.html``, ``404.html`` and ``500.html`` are cards on ``base.html``. They read nothing
from the database. ``500.html`` is rendered without a request, so without the context
processors: the theme stylesheet is still linked, but a mode forced by ``UI_MODE`` does not
reach the page's root element, and the browser's preference decides. The package's
``tests/test_error_pages.py`` renders them with database access blocked.

Static files
------------

The package's ``tests/test_staticfiles.py`` collects the static files into a temporary
directory under a manifest storage, Django's, or WhiteNoise's when the project was generated with it, and
checks that the library's files were hashed: a reference that does not resolve fails
there. The deployment's storage, S3 for one, is not exercised. The theme stylesheet is a
route, not a static file, and is not collected.

The showcase
------------

Under ``DEBUG``, ``config/urls.py`` registers the showcase at ``/ui/components/``, next to
the error page previews, and the navigation links to it; without ``DEBUG`` the routes do not
exist. For every component it shows the contract its template opens with, its example
rendered live in the page's theme, and the example as written. An example is a template
under ``templates/ui/examples/``, so what the page shows and what it renders cannot drift
apart. The ``showcase`` tag library, which ``templates/ui/showcase.html`` loads, reads them:
``example_source`` writes an example's source, escaped, and ``component_contract`` a
component's opening comment as one paragraph. Both read only the examples and components
``ui/showcase.py`` names, from the template files as written rather than as Cotton compiles
them. To show a new component, add its example template, name the example in ``EXAMPLES``
and the component in ``COMPONENTS``, and give it a section in ``templates/ui/showcase.html``.

Three parts of the page are working examples of the patterns above:

- The sample form, ``SampleForm`` in ``ui/forms.py``, validates on the server and has
  nothing behind it. With htmx it posts into its own container, ``#showcase-sample``, which
  the ``sample`` partial reproduces. An invalid submission answers ``200`` with the errors,
  because htmx's default configuration swaps no error response; a valid one shows the
  result, with a message swapped in out of band. While the request runs, htmx disables the
  submit button (``hx-disabled-elt``) and shows the ``htmx-indicator``. Without JavaScript
  the same form posts to the same view and gets the whole page. A copy of the form bound to
  wrong answers shows the field component's error, choice, checkbox and disabled states.
- The results page through sample tasks: the ``results`` partial holds the table and the
  pagination inside ``#showcase-results``, the target of every page link and of the filter,
  and a filter that matches nothing shows an empty state in the same place. The page links
  keep the filter's query.
- The theme preview takes a palette, a mode and, for each set, colours for the brand's
  tokens, a blank one keeping the colour beneath it, which its placeholder shows. A valid
  submission is kept in the session and the view redirects to the showcase, whose next load
  fetches ``/ui/theme.css`` again; an invalid one, a colour that is not ``#RRGGBB`` or a
  result that breaks a pair over the palette and ``UI_BRAND``, shows the form's errors and
  leaves the theme as it was. The reset button removes the preview. A preview applies to the
  session that made it, and only under ``DEBUG``.

``ui/tests/test_showcase.py`` renders the page through ``ui/tests/urls.py``, the project's
URLs with the showcase added as ``config/urls.py`` adds it under ``DEBUG``, since the tests
run without it, and checks that the project's own URLs have no showcase.

From a preview to a company's colours
-------------------------------------

A preview already has the shape a company's colours take: a palette, a mode and the colours
given for each set, never a resolved theme, so it follows later changes to the palettes and
to ``UI_BRAND``. An application that lets each company choose its colours keeps the same data
on its own model and resolves it where the preview is resolved:

#. Store the palette, the mode and the ``light`` and ``dark`` colours on the company, the
   colours in a ``JSONField`` for one, and validate them when they are saved:
   ``servable_theme(palette, mode, settings.UI_BRAND, colours)`` raises
   ``InvalidThemeError`` with every problem, which a form turns into its errors the way
   ``PreviewForm`` does.
#. Resolve the request's company in ``resolve_theme``, before the configured theme. Saved
   colours can still stop being servable when a palette or ``UI_BRAND`` changes: catch
   ``InvalidThemeError`` only, log which company failed, and fall back to the configured
   theme, leaving the record for its owner to correct.
#. Nothing else changes: components and templates read colours only through the theme
   stylesheet, which is private and uncached. Keep it that way, since its content now depends
   on the user, and note that finding the company reads the database, which the stylesheet
   otherwise does not.

With a ``company`` relation on the user, for example:

.. code-block:: python

    def resolve_theme(request: HttpRequest) -> Theme:
        theme = _resolved.get(request)
        if theme is None:
            theme = (
                _previewed_theme(request)
                or _company_theme(request)
                or configured_theme()
            )
            _resolved[request] = theme
        return theme


    def _company_theme(request: HttpRequest) -> Theme | None:
        company = getattr(request.user, "company", None)
        if company is None:
            return None
        try:
            theme = servable_theme(
                company.palette,
                company.mode,
                settings.UI_BRAND,
                company.colours,
            )
        except InvalidThemeError as error:
            logger.warning("The colours of company %s cannot be served: %s", company.pk, error)
            return None
        return theme
{%- endraw %}
