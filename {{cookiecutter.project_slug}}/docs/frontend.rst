{% raw %}Frontend
========

The frontend is server rendered: Django templates, `htmx`_ for partial page updates, and
`Tailwind CSS`_ with `daisyUI`_'s components for the look. `django-tailwind-cli`_ runs
Tailwind's standalone CLI from ``manage.py``, so there is no Node.js toolchain, and the
project ships no JavaScript of its own: what involves the server is an htmx request, and
what does not is one of daisyUI's CSS-only mechanisms. Every response carries a nonce-based
Content Security Policy, so templates hold no inline scripts, styles or event handlers;
the rules at the end of this page keep a template within it.

Two commands matter from day to day::

    python manage.py tailwind watch    # rebuild the stylesheet whenever a file changes
    python manage.py tailwind build    # build it once, minified, as a deployment does

.. _htmx: https://htmx.org
.. _Tailwind CSS: https://tailwindcss.com
.. _daisyUI: https://daisyui.com
.. _django-tailwind-cli: https://django-tailwind-cli.readthedocs.io

The stylesheet
--------------

There are two stylesheets, and only one of them is yours to edit.

The **source stylesheet** is ``<project_slug>/styles/main.css``, with the project's theme
beside it in ``theme.css``. It imports Tailwind CSS, enables daisyUI, names the files whose
class names count, and holds the few rules no class can say, such as htmx's request
indicator. It is committed. It sits outside the static directories on purpose: under a
manifest storage ``collectstatic`` would try to resolve its ``@import "tailwindcss"`` as a
file and fail.

The **built stylesheet** is ``<project_slug>/static/css/tailwind.css``, the one stylesheet
``base.html`` loads, through the ``{% tailwind_css %}`` tag. The Tailwind CLI writes it
from the source stylesheet and from the class names it finds in the project. It is an
artefact: generation does not write it, ``.gitignore`` keeps it out of version control,
and a fresh checkout has none until the watcher or a build has run. A page without styles
means exactly that.

The CLI itself is a standalone binary with daisyUI bundled, ``tailwindcss-extra``.
django-tailwind-cli downloads the release that ``TAILWIND_CLI_VERSION`` names into
``.django_tailwind_cli/`` the first time a command needs it, about 80 to 110 MB depending
on the platform, and git ignores that directory too. Every ``TAILWIND_CLI_*`` setting is
in ``config/settings/base.py`` and in no other settings module, because the production
image builds the stylesheet under the test settings: an override elsewhere would build
one file and ask for another.

Keep the watcher running while you work. It prints nothing as it rebuilds, errors
included, so when a change to the source stylesheet seems to have no effect, run
``tailwind build``, which reports them. Uvicorn serves the rebuilt file on the next
request without restarting.

Which class names count
~~~~~~~~~~~~~~~~~~~~~~~

Tailwind generates a rule only for a class name it has seen. The source stylesheet turns
automatic detection off and names its sources itself::

    @import "tailwindcss" source(none);
    @source "../";
    @source not "../media";
    @source not "../static";

so the scan covers this package, its templates and its Python modules (a class given to a
widget in a form counts), and is the same on every machine and in the production image,
where there is no ``.gitignore`` to steer it. Templates of an app you keep outside the
package need an ``@source`` line of their own.

The scan reads text, not templates, which gives the one rule to remember: **write class
names whole**. ``alert-{{ level }}`` never produces ``alert-success``, because that name
appears nowhere. Choose between whole names instead, as the messages in ``base.html`` do:

.. code-block:: html+django

    <div class="alert {% if message.level_tag == 'success' %}alert-success{% else %}alert-info{% endif %}">

A name that exists only in data, in the database for one, is declared in the source
stylesheet with ``@source inline("alert-success alert-error");``.

The project's theme
-------------------

``styles/theme.css`` is the project's own daisyUI theme, ``brand``, and the default look.
Every value daisyUI reads is written out in it: the surfaces and the text on them, the
brand's colours each with the colour of what is written on it, the status colours, the
corner radii, the sizes, the border width and the depth effects. **Restyling the site is
editing that block**, not overriding daisyUI's classes: change ``--color-primary`` and
every primary button, link and focus ring follows; change ``--radius-field`` and every
input and button does. The `theme generator`_ edits the same values visually and hands
back a block to paste.

The colours start from daisyUI's ``light`` theme. Secondary, accent and the status
colours are darker than daisyUI's, so that each has a contrast of at least 4.5:1 both as
text on the base colours and beneath its ``-content`` colour. Nothing checks that for the
values you put there: when you change a colour, check the pairs you use.

A browser that prefers a dark colour scheme gets daisyUI's ``dark``, because ``main.css``
enables it with ``--prefersdark``. For a dark counterpart of your own, add a second block
named ``brand-dark`` with ``prefersdark: true`` and ``color-scheme: dark``, start it from
the values of daisyUI's ``dark``, and take ``--prefersdark`` off ``dark`` in ``main.css``:
only one theme can answer a dark colour scheme.

.. _theme generator: https://daisyui.com/theme-generator/

Themes and the picker
---------------------

Next to ``brand``, ``main.css`` enables every theme daisyUI ships, and the navigation
offers them all in the theme picker, with "System" for no choice at all. The picker
involves no script:

- It is a form of radio buttons of daisyUI's ``theme-controller`` class. daisyUI applies
  the theme of a checked one in CSS alone, so the page is restyled the moment a visitor
  picks.
- The form posts the change to ``set_theme``, in ``<project_slug>/themes.py``, through
  htmx (``hx-trigger="change"``, ``hx-swap="none"``). The view keeps the name in the
  ``theme`` cookie for a year and answers 204: there is nothing to swap.
- The ``theme`` context processor reads the cookie back, and ``base.html`` writes it as
  ``data-theme`` on the root element, so every later page arrives in the chosen theme.
  Only a name in ``THEMES`` reaches the cookie, and only a cookie naming one reaches the
  attribute.
- "System" deletes the cookie, and the view answers it with ``HX-Refresh``, because
  nothing on the page can undo the ``data-theme`` it was served with. ``base.html`` then
  writes no attribute at all, never an empty one: daisyUI's rule for a dark colour scheme
  applies to a root element without it.
- Without JavaScript the radio still restyles the page, and the "Apply" button of the
  form's ``noscript`` element posts it; the view redirects back to the page.

The choice belongs to the browser, not to the account. ``500.html`` is rendered without a
request, so it is always in the default theme and has no picker. ``<main>`` carries
``hx-history-elt``, so htmx's history saves and restores the content and leaves the
navigation alone; without it, going back would bring back the picker as it was, and its
checked radio would outweigh the theme the page was served in.

``THEMES`` in ``themes.py`` and the ``themes:`` list in ``main.css`` say the same thing in
two languages, and ``tests/test_themes.py`` in the package compares them. To offer fewer
themes, delete the same names from both; the built stylesheet shrinks by about a
kilobyte for each. To add a theme of your own to the picker, add its block to
``theme.css`` and its name to ``THEMES`` after ``OWN_THEME``.

Building pages
--------------

A page extends ``base.html`` and fills ``content``; ``title``, ``css``, ``javascript``,
``bodyclass``, ``main`` (the width-limited column around ``content``), ``body`` and
``modal`` are there to be overridden as well. Markup is daisyUI's component classes
(``btn``, ``card``, ``alert``, ``badge``, ``table``, ``navbar``, ``menu`` and the rest,
documented at daisyui.com) with Tailwind's utilities for layout and spacing, written in
the template where they apply. There is no component layer of the project's own between a
template and daisyUI: a piece of markup used twice is a Django ``{% include %}`` or a
``partialdef`` partial rendered with ``{% partial %}``, as the navigation's links are.

Tailwind's preflight removes the browser's default look from bare elements, headings and
lists included, so an element is styled by its classes or not at all. Running text is the
exception worth a tool: ``prose``, from Tailwind's typography plugin, styles whatever it
wraps, as ``templates/pages/about.html`` shows.

daisyUI's interactive components work without a script, and those are the variants to
use under the policy: a ``dropdown`` opens while it holds the focus (the navigation's
menu), a ``collapse`` rides on ``<details>``, and tabs, drawers and swaps ride on radio
buttons and checkboxes. Its documentation shows some components with a ``style``
attribute for a value, ``radial-progress`` and ``countdown`` among them; write that value
as an arbitrary property class instead, ``[--value:70]``, which the policy allows.

Forms
-----

``FORM_RENDERER`` is Django's ``TemplatesSetting`` renderer, so ``{{ form }}``,
``form.as_div`` and ``field.as_field_group`` render through the project's templates under
``templates/django/forms/``, and a form needs no classes set in Python to look right:

- ``field.html`` writes each field: daisyUI's ``fieldset`` wrapper, the label, the widget,
  the errors, the help text, in that order. It keeps Django's associations: the label
  names the widget, the widget names its help text and its error list in
  ``aria-describedby``, and an invalid widget carries ``aria-invalid``. A radio or
  checkbox group is a real ``<fieldset>`` with a ``<legend>``, which carries the
  ``aria-describedby``; a checkbox sits inside its label; a hidden field is its widget
  alone; a form without ids (``auto_id=False``) gets a ``<span>`` for a label.
- ``widgets/input.html``, ``select.html``, ``textarea.html`` and
  ``clearable_file_input.html`` give each control daisyUI's class for its kind, ``input``,
  ``checkbox``, ``radio``, ``file-input``, ``range``, ``select`` or ``textarea``, and merge
  a class of the widget's own into the same attribute. A checkbox whose widget asks for
  ``toggle``, ``forms.CheckboxInput(attrs={"class": "toggle"})``, is a toggle.
  ``widgets/input_option.html`` and ``multiple_input.html`` lay out the options of a group.
- The error colour of a control comes from ``aria-invalid``, which Django sets: the class
  is ``aria-invalid:input-error`` and its siblings, so no view or form adds a class to an
  invalid field. daisyUI's ``validator`` class, which colours a control from the browser's
  own validation as the user types, is available per widget the same way as ``toggle``.
- ``errors/list/ul.html`` is Django's error list with its ``errorlist`` class, the id the
  widget names, and the error colour.

``widgets/attrs_without_class.html`` is Django's ``attrs.html`` minus the ``class``
attribute, which the widget templates write themselves. Django's own ``attrs.html`` is
deliberately not overridden: the admin's widgets and third-party ones include it and
expect the class from it. The renderer is global, so the admin's fields come through these
templates too. That is harmless: the admin never loads the built stylesheet, its own
classes (``vTextField`` and the rest) are merged in like any widget's, and the templates
use none of the few utility names the admin's stylesheets define (``hidden``, ``small``,
``inline``): keep it that way when you edit them. ``tests/test_forms.py`` in the package
covers each of these points.

django-allauth
--------------

allauth's pages are its own templates, built from elements it renders through
``templates/allauth/elements/``. Every element is overridden there, because under
Tailwind's preflight an element without classes has no look:

- ``button`` is a link drawn as a button when it has an ``href``, else a button that
  submits, as allauth's own does. Its tags choose the look: ``danger`` or ``delete``,
  ``link`` (daisyUI's ghost button), ``secondary`` (the plain button: allauth means a
  lesser action, not daisyUI's secondary colour), ``outline`` and ``prominent`` (full
  width). The ``form``, ``id``, ``name`` and ``value`` it names are written when given,
  even empty.
- ``alert`` is an alert without a role, since it is in the page from the start; ``badge``
  maps the tags ``success``, ``warning``, ``danger`` and ``primary`` onto daisyUI's
  colours; ``panel`` is a card with a second-level heading and its actions at the end;
  ``button_group`` is a row, or a column when allauth asks for ``vertical``;
  ``provider_list`` and ``provider`` are a column of full-width button links; ``table``
  is daisyUI's table around allauth's own rows and cells.
- ``field``, for the inputs allauth writes outside a Django form, is written by hand with
  the classes and the associations of ``django/forms/field.html``. ``fields`` renders the
  form through Django, so through that template.
- ``h1``, ``h2``, ``hr``, ``details`` (a ``collapse``), ``form`` and ``img`` get their
  classes; ``img`` also gets a white background, because the QR code of the authenticator
  setup is a dark drawing on a transparent one. ``p`` and the table's rows and cells stay
  allauth's own: the layouts space the paragraphs, and daisyUI's table styles the cells.

The entrance layout (sign in, sign up, ...) and the password pages are one card; the
management pages stack their panels. allauth writes the links in its running text bare,
so the two layouts underline every link that is not a button. The opt-in email and phone
change pages carry an inline ``style`` attribute in allauth's templates and are not
overridden: override them before enabling those flows. ``tests/test_allauth.py`` in the
package renders the elements and the pages.

Messages
--------

``base.html`` renders Django's messages inside ``<div id="messages">`` from the partial
``messages``, one daisyUI alert per message. The level tag chooses between whole class
names, and the role: ``alert`` for a warning or an error, ``status`` otherwise, so a
message that arrives later is announced. The container sticks to the top of the viewport,
which keeps a message in view on a page that has been scrolled.

A message is dismissed without a script: its close control is a visually hidden checkbox
inside a label, and the alert carries ``has-[:checked]:hidden``, so checking the box
hides it. A screen reader announces the control as a checkbox named "Dismiss".

A fragment includes ``base.html#messages`` when ``htmx_fragment`` is set, and the
container is then marked ``hx-swap-oob="true"``, so messages added during an htmx request
are swapped into the page out of band.

htmx
----

``django-htmx`` is installed and its ``HtmxMiddleware`` sets ``request.htmx`` on every
request. ``base.html`` loads the script with ``{% htmx_script %}`` from django-htmx's own
static files, so upgrading django-htmx upgrades htmx; under ``DEBUG`` the tag also loads
django-htmx's debug extension, which shows Django's error page for a failed htmx request.
The ``htmx-config`` meta tag in ``base.html`` sets ``allowEval``, ``allowScriptTags`` and
``includeIndicatorStyles`` to false, because the policy allows no inline code and no
injected stylesheet. That also switches off ``hx-on*`` attributes, ``js:`` prefixes in
``hx-vals`` and ``hx-headers``, and event filters such as ``click[ctrlKey]``: what they
would do becomes a request to the server or a CSS-only mechanism. The rules of
``htmx-indicator``, which htmx would otherwise inject, are in ``styles/main.css``; put the
class on daisyUI's ``loading`` element to show a spinner while a request runs.

Django's CSRF token rides on the ``<body>`` element in ``hx-headers``, so htmx sends it
with every request, not only with form submissions, and ``CsrfViewMiddleware`` stays on.
The navigation is deliberately not boosted: a boosted page swap would keep the body's
attribute, and with it a token that signing in has rotated.

The examples page shows the patterns below at work. A view answers an htmx request with one fragment of its own template. The fragment is a
``{% partialdef name inline %}`` block, and the view names it:

.. code-block:: python

    class UserDetailView(LoginRequiredMixin, HtmxTemplateMixin, DetailView):
        model = User
        htmx_partial = "profile"

``HtmxTemplateMixin``, in ``<project_slug>/htmx.py``, then renders
``"users/user_detail.html#profile"`` for a request carrying the ``HX-Request`` header and
the whole template for every other request, so the page keeps working without JavaScript;
a boosted request expects a page and gets one, and so does the request htmx sends to
restore a page its history cache no longer holds, which carries ``HX-Request`` too. The
mixin adds ``Vary: HX-Request, HX-History-Restore-Request`` to every response, because the
body depends on those headers. A view of your own that answers both
needs the same headers, from ``django.views.decorators.vary.vary_on_headers``.

The mixin also puts ``htmx_fragment`` in the context, true only while the partial is
rendered on its own. Templates branch on that flag rather than on ``request.htmx``: a
template that reads the request varies by the header on every page that includes it, and
``base.html`` is included by all of them.

htmx swaps a 2xx or 3xx response and nothing else, so a view that answers an invalid form
over htmx answers 200 with the form re-rendered. When a session has expired,
``HtmxLoginRedirectMiddleware`` (listed after ``HtmxMiddleware``) turns the redirect to
the login page into django-htmx's ``HttpResponseClientRedirect``, a 200 carrying
``HX-Redirect``, so the browser leaves the page instead of swapping the login form into
it. Every other redirect is left alone.

The profile pages are the worked example: the edit link loads the form into the profile
card with ``hx-get``, ``hx-target`` and ``hx-push-url``, the form posts with ``hx-post``,
and the saved card is swapped back with its message beside it. A fragment holds no
``<script>``, ``<style>`` or ``<link>``; the profile views' tests check theirs for them.

The examples page
-----------------

``/examples/`` shows daisyUI components and htmx patterns as this project writes them, and
the navigation links to it. Each example is a small template under
``templates/examples/``, rendered live and shown beneath as it is written: the view reads
the template's source, of the examples ``examples/content.py`` names and of no other
template, so an example cannot show one thing and render another. Its first section shows
the colours of the theme in use, which makes it the page to keep open while you edit
``styles/theme.css``.

The htmx demos are the patterns worth copying:

- **A form validated on the server** posts into its own container with ``hx-post`` and gets
  it back with its errors, or with the result and a message swapped in out of band.
  ``hx-disabled-elt`` keeps a second click from posting twice, and daisyUI's ``loading``
  element carries ``htmx-indicator``.
- **A filtered table with pagination** replaces its container and pushes the address
  (``hx-push-url``), so a result can be bookmarked and the back button works. The filter's
  ``hx-trigger`` names events only (``input changed delay:300ms``), because the policy turns
  htmx's bracketed event filters off, and the page links are built with
  ``{% querystring %}``, which keeps the filter.
- **A toggle** posts its state on ``change`` and is swapped for what the server made of it.
- **Tabs** fetch their panel when they are chosen; each is a link, so without htmx it loads
  the page with that tab. Under ``DEBUG`` the view answers a little late, so the indicator
  shows on a developer's machine.
- **A dialog** is fetched into ``<div id="modal">``, which ``base.html`` provides, and
  emptied again by the dialog's answer. daisyUI's ``modal-open`` class holds it open
  without a script, which also means it has no Escape key and no focus trap: a dialog
  that needs them is the place for the project's first script and ``<dialog>``.
- **Notices** answer with the messages alone, which htmx swaps in out of band even though
  the form asked for no swap of its own.

Every demo works without JavaScript: a plain request gets the whole page in the state it
asked for, or a redirect to it. Every view is ``HtmxTemplateMixin`` on
``examples/index.html`` naming one of its partials.

The page is routed in every environment, so it keeps nothing on the server: no table, no
session, only the query string, the posted form and one cookie for the toggle. Its views
open no transaction, and their tests run without database access to hold them to it. The
copy is plain English rather than translated, which keeps the examples readable as
written.

It is starter content. To delete it, remove ``<project_slug>/examples/`` (its tests go
with it), ``<project_slug>/templates/examples/`` and the ``examples/`` line in
``config/urls.py``. The navigation asks for the route before it links to it, so nothing
else changes; ``examples/tests/test_views.py`` renders the home page without the route
to keep that true.

Error pages
-----------

``403.html``, ``404.html`` and ``500.html`` are daisyUI heroes on ``base.html``, and
``403_csrf.html``, the page a rejected CSRF token reaches, extends ``403.html``. They read
nothing from the database. ``500.html`` is rendered without a request, so without the
context processors: it is in the default theme and has no theme picker. The package's ``tests/test_error_pages.py`` renders them with database
access blocked.

Static files and deployment
---------------------------

Build, then collect::

    python manage.py tailwind build
    python manage.py collectstatic --noinput

The order matters, and the wrong order fails late: ``collectstatic`` succeeds without the
built stylesheet, and under a manifest storage the first page that renders then fails
with ``Missing staticfiles manifest entry for 'css/tailwind.css'``.
{%- endraw %}{% if cookiecutter.use_docker == 'y' %}{% raw %} The production image
runs the build in its build stage, with the CLI in a build cache so that the image never
holds it; a container only collects when it starts. The build downloads the CLI from
GitHub's releases when that cache is cold.{% endraw %}{% endif %}{% raw %}

The package's ``tests/test_staticfiles.py`` does both in temporary directories: it builds
the stylesheet, which leaves the working tree as it was, collects everything under a
manifest storage, Django's, or WhiteNoise's when the project was generated with it, and
checks that every file was hashed and that the built stylesheet holds the rules the
templates rely on. Its first run downloads the CLI. The deployment's own storage, S3 for
one, is not exercised.
{%- endraw %}{% if cookiecutter.cloud_provider == 'AWS' and cookiecutter.use_whitenoise == 'n' %}{% raw %}

Static files on S3 keep their names, and ``AWS_S3_OBJECT_PARAMETERS`` lets a browser
cache them for a week. A stylesheet built from the class names in use changes with most
deployments, so a returning visitor can get new markup with the stylesheet of the
deployment before: shorten that cache for the stylesheet, or serve the static files with
hashed names, before the first visitors arrive.{% endraw %}{% endif %}{% raw %}

The policy's rules for templates
--------------------------------

- No inline ``<script>`` and no ``<style>`` block; no ``style`` attribute; no ``on*``
  handler and no ``hx-on*``. ``tests/test_csp.py`` checks the policy the pages send.
- Styling is classes in the markup. What classes cannot say goes into ``styles/main.css``.
- A script, if the project ever needs one, is a static file loaded with ``defer`` in the
  ``javascript`` block of ``base.html``. The one that truly must be inline carries
  ``nonce="{{ csp_nonce }}"``.
- Every asset comes from this origin: no stylesheet, script or font from another host.
- ``img-src`` allows ``data:`` URIs, which allauth's QR code and a few of daisyUI's parts
  (the loading indicator among them) are drawn with.

Upgrading Tailwind CSS and daisyUI
----------------------------------

``TAILWIND_CLI_VERSION`` in ``config/settings/base.py`` names a release of
`tailwind-cli-extra`_, whose number is its own: its release notes say which Tailwind CSS
and which daisyUI it bundles. Nothing bumps it for you, since it is neither a package nor
an image. Change the setting and the comment above it; a running watcher restarts and
downloads the new CLI beside the old one, and ``tailwind build`` does the same. Look the
pages over, commit, and delete the old binary from ``.django_tailwind_cli/`` when you
like. A new major version of Tailwind CSS or of daisyUI renames classes: read its upgrade
guide first.

.. _tailwind-cli-extra: https://github.com/dobicinaitis/tailwind-cli-extra/releases
{%- endraw %}
