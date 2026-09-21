---
status: accepted
---

# Serve every machine caller from one verifier

`docs/adr/0018` gave the metrics endpoint a credential of its own: `METRICS_TOKEN`, drawn per
deployed environment. That is the right answer for a deployment whose scraper has no identity
anywhere, and the wrong one for a deployment that already runs its machines on Microsoft Entra
ID or Google. There the scraper has a service principal, the tenant will issue it a token, and
a shared string is a second secret to distribute, store and rotate — one that says nothing
about who presented it.

The project already verifies exactly those tokens, in `identity/verification.py`, and already
records what a calling service may do, in `identity/models.py`. Only the removal rules stood in
the way: the identity app was deleted as one unit unless the answers were Django Ninja *and* a
provider, because Django Ninja's routes were the only thing that read a service token.

So the app is carved in two. The machine half — `verification.py`, `models.py`, `admin.py`, the
migrations and the token-minting helper its tests use — is generated whenever a provider is
chosen and something reads a service token: Django Ninja's routes, or the metrics endpoint. The
API half — the Ninja policies in `auth.py`, `permissions.py`, `api.py`, allauth's headless login
and everything driving it — stays tied to Django Ninja. `unverified_issuer` moves down into
`verification.py`, because it is now read by two routers rather than one, and
`identity/tests/test_verification.py` calls the verifier instead of calling an API that calls
it, so it runs whichever caller the answers generated.

The metrics endpoint then routes the way `either_auth` does, on the credential's unverified
`iss` claim: a configured provider issuer means the verifier decides, and anything else is
compared with `METRICS_TOKEN` in constant time. Neither falls back to the other, so a provider's
token that fails verification is refused rather than tried again as a string.

A verified service is not admitted by being verified. Its registration has to hold
`identity.read_metrics`, declared on `ServiceRegistration` where there are metrics to read, and
a registered service without it is refused with `403` where an unusable credential is `401`:
one presented nothing this project accepts, the other presented something that does not reach
this far. What the provider decides is which service is calling; what this project may let that
service read is its own to decide.

## Considered options

- **Leave the metrics endpoint on the drawn token alone**: it works, and it asks a corporate
  deployment to run a secret distribution for a scraper that already has an identity. The token
  also names nobody: every holder of it is the same caller in the logs.
- **Admit every service the provider vouches for**: an app role at the tenant is a grant to
  obtain a token for this application, not a grant to read every URL pattern, the errors each
  returned and how long the database took. The permission is where this project says which.
- **Declare `read_metrics` in every arm of the identity app**: one migration whatever the
  answers, and a permission in the admin's picker that grants nothing wherever there are no
  metrics. Declaring it with the metrics costs a conditional migration, which
  `makemigrations --check` covers in both arms.
- **Move the verifier into a package outside `identity`**: the registrations and their admin
  would have to move with it, and every import in the generated project would change, for a
  carving that two removal rules already express.
- **Have the endpoint call `identity/auth.py`'s policy**: that module imports Django Ninja and
  answers with Ninja principals, so the endpoint would exist only with Django Ninja — the tie
  this change removes.

## Consequences

A deployment whose scrapers have identities at the provider registers them, grants the
permission and leaves `DJANGO_METRICS_TOKEN` unset; one without them keeps the drawn token and
registers nothing. Both are in the generated `docs/observability.rst`, with the `oauth2:` scrape
stanza Prometheus fills from Entra's client credentials — for Google it mints no ID token
itself, so that deployment refreshes a credentials file beside it or keeps the drawn token.

The identity app now forks on three answers rather than two. `identity/apps.py` and
`identity/checks.py` carry arms for the headless login, and `checks.py` goes altogether when
neither its frontend check nor Entra's registration check is generated. The removal rules grew
from one to four, checked over every combination of the answers they read as the others are.

The router branch that `identity/tests/test_verification.py` used to reach through the API is
Django Ninja's alone, and stays covered there by `identity/tests/test_services.py`.
