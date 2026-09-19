---
status: accepted
---

# Keep the chosen theme in a cookie and apply it without JavaScript

The generated project enables every theme daisyUI ships next to its own, and the navigation
offers them in a theme picker. daisyUI applies a theme two ways, from a `data-theme` attribute
and, in CSS alone, from a checked input of the class `theme-controller`
(`:root:has(input.theme-controller[value=X]:checked)`). The Content Security Policy allows no
inline script, and the project writes no JavaScript of its own (`docs/adr/0016`), so the choice
has to be applied and remembered without one.

The picker is a form of radio buttons. Checking one restyles the page at once through daisyUI's
CSS, and the form posts the same change to `set_theme` through htmx, which checks the name
against `THEMES` and keeps it in a cookie. The `theme` context processor reads the cookie back
and `base.html` writes it as `data-theme`, so the next page arrives in the chosen theme. htmx
gets no content for a theme, because the radio has restyled the page already. For the "system"
choice it gets `HX-Refresh`, because nothing on the page can undo the `data-theme` it was served
with: the `:has` selector outweighs the attribute, but no selector can take an attribute away.
`base.html` leaves the attribute out for "system" rather than writing it empty, since daisyUI's
rule for a dark colour scheme applies to a root element without one. Without JavaScript the
radio still restyles the page, and a button in a `noscript` element posts the form, which the
view answers with a redirect back.

## Considered options

- **A script that keeps the choice in `localStorage`**, which is daisyUI's documented recipe.
  The theme has to be applied before the first paint, which takes a script in the head, inline
  or blocking, and it is JavaScript of the project's own, which it has none of.
- **The session.** Sessions are in the database, and the context processor would read one for
  every page, the error pages included: `404.html` and `403.html` are rendered with the context
  processors, and `tests/test_error_pages.py` holds them to rendering with database access
  blocked. A visitor who is not signed in would also get a session row for choosing a colour.
- **A field on the user.** It covers signed-in visitors only, needs a migration, and reads the
  database in the same place.

## Consequences

The choice belongs to the browser, not to the account: it does not follow a user to another
device. Only a name in `THEMES` reaches the cookie, and only a cookie naming one reaches the
attribute, so the value written into the markup is never the visitor's text. `set_theme` opens
no transaction (`non_atomic_requests`), and its tests run without database access, which holds
it to touching no table. `500.html` is rendered without a request, so it shows the default theme
and has no picker.

htmx snapshots a page for its history, and a snapshot would bring back the picker as it was,
whose checked radio then outweighs the theme the page was served in. `base.html` therefore
marks `<main>` with `hx-history-elt`, so history saves and restores the content and leaves the
navigation alone, and the picker's form turns the browser's own state restoration off with
`autocomplete="off"`.

`THEMES` and the list in `styles/main.css` say the same thing twice, in two languages. The
generated `tests/test_themes.py` compares them, with the own theme's name from
`styles/theme.css`, so a theme is dropped from both or the suite fails; this repository's
`test_themes` checks that a generated project starts with all of daisyUI's.
