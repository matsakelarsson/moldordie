---
status: accepted
---

# Put the pages in a sidebar a page adds its sections to

The navigation of a generated project was a bar: the brand, the site's pages as a horizontal
menu, the theme picker and the account links, with the pages rendered a second time in a
dropdown for a small screen. Nothing drew the current page, and a page with sections of its
own, the examples page first of all, had no index. The owner's instruction: "I also want the
default to have a side instead of the topics being in the top nav-bar. Make sure to make an
example out of it." The standing conditions are those of `docs/adr/0016`: no JavaScript of the
project's own, what does not involve the server is one of daisyUI's CSS-only mechanisms, and
every page works without a script.

`base.html` is now daisyUI's drawer, on a checkbox alone. The sidebar holds the brand and the
pages: a column beside the page on a large screen (`lg:drawer-open`) and, on a small one, a
drawer that the bar's menu button opens and the overlay closes, each a `<label>` for the
checkbox. The bar keeps the theme picker and the account links, and on a small screen the
menu button and the brand. The two are the partials of `partials/navigation.html`, `pages` and
`bar`, which `base.html` includes by name, so the navigation stays one file and the links are
rendered once. The link of the current page carries `aria-current="page"`, as it did; daisyUI's
menu draws such a link as the active one, so no class says which page it is. A page adds
entries of its own to the sidebar through the `sidebar` block, keeping the pages with
`{{ block.super }}`. The examples page puts its sections there, from `examples/sidebar.html`,
which it shows as written beside the other examples: that is the example the owner asked for,
a page with sections of its own and the index they get. A new example shows a dropdown, and
another the progress elements, since each carries a rule the policy sets.

## Considered options

- **The bar above the drawer, full width.** daisyUI's open drawer side is sticky and the
  height of the viewport, so under a bar the page is always taller than the viewport, with a
  scrollbar on the shortest page, and the sidebar's top sits under the bar once the page has
  scrolled. daisyUI documents the bar inside the drawer's content, which is where it is.
- **A column on a large screen and the old dropdown on a small one**, no drawer. Two mechanisms
  for one list, and the links rendered twice, as before.
- **The page's sections nested under its own link**, as a documentation site does. The pages
  are an include a page cannot reach into; a block under them is the same thing, and one a
  page can fill without knowing which of the links is its own.
- **The sections in the drawer of a small screen as well.** A link within the page does not
  uncheck the box, so the drawer would stay open over the content it scrolled to; closing it
  takes a script or a page load. The entries are `hidden lg:flex`, and the template says why.
- **A `menu-active` class set by the template** on the current page's link. daisyUI's menu
  already draws `aria-current="page"` as active, so the attribute the links carried for a
  screen reader is enough, and the markup stays what it was.

## Consequences

Every page is in the drawer, the error pages included: `500.html` renders without a request,
so no link in its sidebar is current, and the shell is the same. The brand is rendered twice,
at the top of the sidebar for a large screen and in the bar for a small one, inside a button
that may shrink, since daisyUI's cannot. The drawer side sits above the sticky messages
(`z-50`), and `<main>` keeps `hx-history-elt`, so htmx's history never touches the sidebar.
Opening the drawer on a small screen locks the page's scroll, which daisyUI does for every
drawer. A page that wants another sidebar overrides the block without `block.super`.
`test_the_pages_are_in_a_sidebar` checks the drawer, the partials and the block in the
templates; the generated `tests/test_pages.py` checks the rendered shell, and the examples'
tests that the sidebar lists the page's sections in their order.
