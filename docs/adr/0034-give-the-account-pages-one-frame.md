---
status: accepted
---

# Give the account pages one frame and an account menu

After `docs/adr/0033` the pages of a signed-in user's account had no frame in common. The
two-factor page stacked a card per panel on the page's background; the email addresses, the
authenticator setup and the sign-out confirmation stood bare at the top of an empty column;
the password pages borrowed the entrance card through a template of their own; and the profile
was a card as wide as the page holding a name and three buttons, one of which led to the email
page and one to the two-factor page, while the password page was linked from nowhere. The
owner's instruction: "Now improve the sign-in and account pages with the same skills." The
standing conditions are those of `docs/adr/0016` and `docs/adr/0033`: no JavaScript of the
project's own, daisyUI's components over markup of the project's own, and allauth's pages left
as allauth's templates, overridden at the element and the layout alone.

An account page is now one card, in allauth's management layout: its first-level heading is
the page's title, and its sections start under a rule, each a title beside its body and its
actions on a wide screen and a stack on a small one. allauth's panel element is that section.
A second-level heading allauth writes at the top level of a page, "Add Email Address" and
"Add a Third-Party Account", starts a section the same way, through a selector of the layout
rather than a class of the heading, because on the entrance pages allauth writes a rule of its
own before such a heading ("Or use a third-party", "Alternative options") and on the account
pages nothing. The password pages extend the same layout and lose their template. The entrance
card stays as it was: a visitor's one task fits it.

The account pages add the account menu to the sidebar, the third partial of
`partials/navigation.html` after the pages and the bar: the profile, the email addresses, the
password, two-factor authentication, the account connections when an identity provider is
configured, and sign out, with the current page marked as the pages are. The management
layout includes it through the `sidebar` block, so every page of allauth's gets it, and the
profile templates include it for the user's own profile. Unlike the sections of the examples
page, its entries show in the drawer of a small screen too, since each leaves the page and so
closes the drawer. The profile is built from allauth's panel element, a section for the name
with its edit action and one for the email address with the way to its page, so it is the same
frame without a second copy of the markup; the buttons to the email and the two-factor pages
go, since the menu holds them on every account page. A destructive action is red where it acts
at once, a button, and quiet red text where it opens a page that asks first, a link, which is
what allauth makes of every destructive action that has a confirmation; the badges are soft,
a status beside a line rather than a button.

## Considered options

- **A card per panel, as it was.** The daisyUI pattern that comes first to hand, and the one a
  generated page tends to repeat for everything: identical rounded cards with the same shadow,
  whatever the content. It frames the pages that have panels and none of the others, which was
  the inconsistency.
- **Overriding allauth's page templates** to put every page in panels. Every allauth release
  touches its page templates, and the elements and the layouts have been enough to restyle
  them so far; the page templates stay allauth's, which also keeps the opt-in flows working
  when a project enables them.
- **A page of the project's own gathering allauth's forms**, with tabs. allauth's flows are
  many pages with redirects between them, which such a page cannot absorb, and a tab bar
  would be a second navigation beside the sidebar.
- **Links on the profile**, the three buttons it had. That is navigation, and since
  `docs/adr/0033` navigation lives in the sidebar, where it reaches every account page and
  the drawer of a small screen; the profile keeps the one link that belongs to a fact on it.
- **Hiding the sidebar on the entrance pages.** The frame is the site's; a visitor on the
  sign-in page still has the pages, and the card is centred in the column either way.

## Consequences

- `templates/allauth/layouts/manage.html` is the frame of every account page, and
  `templates/allauth/elements/panel.html` its section; `account/base_manage_password.html` is
  gone. The generated `tests/test_allauth.py` pins the card, the section and the elements'
  classes, `tests/test_pages.py` the menu's entries, order and current mark on the pages that
  carry it and its absence from the others, and `users/tests/test_views.py` the profile's
  sections for the user and their absence for a visitor.
- A page of the account a project adds goes into the `account` partial, and extends allauth's
  management layout or copies the profile's frame.
- The two-column section reads daisyUI's `sm` breakpoint, not the width of the card, since the
  panel appears on the account pages alone; a panel on the entrance card would need a container
  query.
- Recorded in `CONTEXT.md` under Sidebar and Account menu.
