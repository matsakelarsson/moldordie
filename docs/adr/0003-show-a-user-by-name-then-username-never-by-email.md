---
status: accepted
---

# Show a user by name, then username, never by email

The generated project's user model answers "how is a user addressed" once, in
`get_absolute_url()`, forked on `username_type`. Its callers used to answer the question again
under their own copy of the fork: the redirect view, the navigation template and the Ninja API's
current-user route. The templates forked a second question, "how is a user shown", five times:
the `name` under email login, the `username` under username login, with an empty heading when an
email-login user had no name.

Both questions are now answered on the model. The callers of the URL use `get_absolute_url()`.
The templates use `User.display_name`, a read-only property forked once: the stripped `name`,
else the translated label "User" under email login, else the username under username login. A
name of whitespace counts as blank. The address is never the fallback: the detail view is open
to every signed-in user, and only the editing controls are the owner's, so an address shown in
place of a missing name would be disclosed to everyone who can open the page. The Ninja
`retrieve_current_user` route, identical in both arms, is defined once before the parameterized
routes, which matters because Ninja matches routes in registration order.

The forks that describe a structural difference stay where they are: the fields, manager,
migration, forms, admin, factories, allauth settings, the URL pattern with its converter, the
detail view's slug configuration, and the API's own addressing (the Ninja schema's URL, the DRF
serializer's lookup and their tests): web URLs, API identifiers and login identifiers evolve
independently, and a shared model constant would couple them without removing the path-parameter
fork. `test_urls.py` keeps its fork too, as the independent contract that `reverse("users:detail")`
takes `pk` or `username`. The detail template keeps one fork: under username login it shows the
username as a sub-line whenever it differs from the display name, because a visible handle
distinguishes people who share a display name. Zero template forks is not a requirement.

## Considered options

- **Move the template rule into the model unchanged** (`name` or `username` per variant): keeps
  the empty heading for a nameless email-login user.
- **`name`, else the login identifier** (`get_username()`): fork-free, but the login identifier
  under email login is the address, which every signed-in user could then read off a profile.
- **allauth's `{% user_display %}` tag**: no empty heading, but it ignores `name` under both
  variants, and under email login it shows the address.
- **A single fork-free body** for the chosen rule, `name or username or label`, relying on the
  email variant's `username = None`: hides the two fallback policies behind that attribute and
  leaves the label branch dead under username login. The forked body states each policy in one
  line.

## Consequences

Templates and views name a user through two model members and never fork on `username_type`
for it; a new caller does the same. The label "User" is a translatable string with entries in
the shipped fr_FR and pt_BR catalogues, using Django's own wording. The model tests pin the rule
per variant, including that a distinctive address never leaks into the fallback, and a view test
checks the rendered page of a nameless user as another user. Django's `get_full_name()` and
`get_short_name()`, which the admin's object-history page and header read, are repaired
separately to return the stripped `name`: a display fallback is not someone's name.
