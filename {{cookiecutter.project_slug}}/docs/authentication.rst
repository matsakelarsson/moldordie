{%- set entra = cookiecutter.identity_provider == 'entra' -%}
{%- set provider = 'Microsoft Entra ID' if entra else 'Google' -%}
{%- set headless = cookiecutter.rest_api == 'Django Ninja' -%}
.. _authentication:

Authentication
======================================================================

Users sign in with a password or through {{ provider }}: the login page offers both, and
password reset, email management and two-factor authentication keep working for every
account. An account created through {{ provider }} has no usable password until its user
sets one.

Signing in through {{ provider }}
----------------------------------------------------------------------
{% if entra %}
The project uses allauth's generic OpenID Connect provider against the tenant's v2.0
endpoint, ``https://login.microsoftonline.com/<tenant>/v2.0``, with PKCE and the client
secret sent as HTTP basic authentication. The account is keyed by the token's ``oid``
claim, the immutable object id of the user in the tenant, not by the pairwise ``sub``
claim, which is specific to the app registration. The UserInfo endpoint is never called:
its answer lacks ``oid``, and allauth would prefer it over the ID token if it were fetched.
allauth's own ``microsoft`` provider is not used because it cannot verify an ID token,
which the single-page application flow below posts.

Register the login application in the tenant, in the Microsoft Entra admin center under
*App registrations*:

#. Create a registration for accounts in this organizational directory only. The
   *Directory (tenant) ID* and the *Application (client) ID* of its overview page are
   ``ENTRA_TENANT_ID`` and ``ENTRA_LOGIN_CLIENT_ID``.
#. Under *Authentication*, add a *Web* platform with one redirect URI per deployed
   environment: ``https://{{ cookiecutter.domain_name }}``,
   ``https://dev.{{ cookiecutter.domain_name }}`` and
   ``https://test.{{ cookiecutter.domain_name }}``, each followed by
   ``/accounts/oidc/entra/login/callback/``; for development add
   ``http://localhost:8000/accounts/oidc/entra/login/callback/`` as well.
#. Under *Certificates & secrets*, create a client secret: ``ENTRA_LOGIN_CLIENT_SECRET``.
   It expires; note the date.
#. Under *API permissions*, the delegated Microsoft Graph permissions ``openid``,
   ``profile`` and ``email`` cover the scopes the project requests. Grant admin consent
   when the tenant does not let users consent themselves; otherwise each user consents at
   their first sign-in.
#. If the tenant's ID tokens carry no ``email`` claim although the ``email`` scope is
   consented, add ``email`` as an optional claim of the ID token under *Token
   configuration*.

Registering the API for calling services is a separate registration, described below.
{% else %}
The project uses allauth's Google provider with the ``profile`` and ``email`` scopes, an
online access type (no refresh token is requested or stored) and PKCE. The account is keyed
by the token's ``sub`` claim, Google's stable account id.

Register the web client in the Google Cloud console under *APIs & Services*:

#. Configure the *OAuth consent screen*: the application name and support addresses that
   users see, and the user type, *Internal* for a Google Workspace organisation or
   *External* for any Google account.
#. Under *Credentials*, create an *OAuth client ID* of type *Web application*, with one
   authorised redirect URI per deployed environment:
   ``https://{{ cookiecutter.domain_name }}``,
   ``https://dev.{{ cookiecutter.domain_name }}`` and
   ``https://test.{{ cookiecutter.domain_name }}``, each followed by
   ``/accounts/google/login/callback/``; for development add
   ``http://localhost:8000/accounts/google/login/callback/`` as well.
#. Its client id and secret are ``GOOGLE_LOGIN_CLIENT_ID`` and
   ``GOOGLE_LOGIN_CLIENT_SECRET``.
{% endif %}
Settings
----------------------------------------------------------------------

The credentials are read from the environment by ``config/settings/base.py`` and default
to empty, so the project starts without them; ``python manage.py check`` (and the
development server on startup) reports each empty one, because sign-in through
{{ provider }} cannot work until it is set. In development, export them in the shell{% if cookiecutter.use_docker == 'y' %} or
put them in ``.envs/.local/.django``{% else %} or
in a ``.env`` file read with ``DJANGO_READ_DOT_ENV_FILE=True``{% endif %}; in a deployed
environment they belong with the other secrets of its ``.django`` file, one of
``.envs/.dev/``, ``.envs/.test/`` and ``.envs/.production/``. A registration may be shared
by the environments or given one per environment; either way each environment reads its
own file.

{% if entra -%}
==========================  ================================================================
Variable                    Meaning
==========================  ================================================================
ENTRA_TENANT_ID             The tenant whose users may sign in; also the issuer of tokens
ENTRA_LOGIN_CLIENT_ID       The login app registration's application (client) id
ENTRA_LOGIN_CLIENT_SECRET   Its client secret
==========================  ================================================================
{%- else -%}
==========================  ================================================================
Variable                    Meaning
==========================  ================================================================
GOOGLE_LOGIN_CLIENT_ID      The web client's id
GOOGLE_LOGIN_CLIENT_SECRET  Its client secret
==========================  ================================================================
{%- endif %}

What the project trusts
----------------------------------------------------------------------
{% if entra %}
**The tenant's email address.** The login app is configured with ``verified_email`` on,
so the address in the token is recorded as verified and no verification mail is sent. This
is a policy, not a property of the token: Microsoft documents the ``email`` claim as
mutable and not guaranteed to be correct, and for guest accounts it is whatever the
invitation used. Trusting it means trusting the tenant's email administration, guest
policy included. To require a verification mail instead, set ``verified_email`` to
``False`` in ``SOCIALACCOUNT_PROVIDERS``.
{% else %}
**Google's verified flag.** The address in the token is recorded as verified only when
Google's ``email_verified`` claim says so; otherwise the ordinary verification mail is
sent before the user can sign in, as after a password signup.
{% endif %}
**Registration follows** ``DJANGO_ACCOUNT_ALLOW_REGISTRATION``. With registration off, a
sign-in through {{ provider }} by someone without an account is refused with the same
"sign up closed" page as a password signup.

**A token without an email address** is not a problem: allauth asks for one on its
third-party signup form and verifies it by mail, and the account is created after that.

**Linking is explicit.** A sign-in through {{ provider }} whose address belongs to an
existing local account does not sign in to that account: the local account's owner is
told by mail that an account exists, and nothing is linked (the provider's claim could be
an address the local account never verified). To link the two, sign in with the password
and connect {{ provider }} under *Account connections*, ``/accounts/3rdparty/``. allauth
can link automatically instead: ``SOCIALACCOUNT_EMAIL_AUTHENTICATION = True`` signs in to
the local account with a matching verified address, and
``SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True`` also connects the provider
account to it. Both are off, and turning them on lets anyone {{ provider }} vouches for
sign in to a local account with that address, so do it only for a provider whose
addresses you trust completely.

**Single sign-on only.** ``SOCIALACCOUNT_ONLY = True`` removes password login, signup and
password reset, leaving {{ provider }} as the only way in. allauth requires
``ACCOUNT_EMAIL_VERIFICATION = "none"`` with it, and refuses it while ``allauth.mfa`` is
installed, so an SSO-only deployment drops the second factors from
``INSTALLED_APPS`` and leaves them to the provider.

Content Security Policy
----------------------------------------------------------------------

The policy's ``form-action`` directive names the provider's authorization origin,
{% if entra %}``https://login.microsoftonline.com``{% else %}``https://accounts.google.com``{% endif %}, next to ``'self'``. allauth starts a login with
a POST to the project, which answers with a redirect to the provider; Chrome applies
``form-action`` to the target of that redirect, Firefox does not. A federated login, where
the provider redirects the browser on to another identity provider, needs that provider's
origin listed too: add it to ``SECURE_CSP["form-action"]`` in ``config/settings/base.py``
as an exact origin, never a wildcard.

{% if headless -%}
The single-page application
----------------------------------------------------------------------

A single-page application served from another origin signs in through allauth's
headless API, under ``/_allauth/app/v1/``, as its *app* client: the answers carry
tokens, never cookies. The origins the application is served from go in
``DJANGO_FRONTEND_ORIGINS`` (comma-separated; ``http://localhost:5173`` in development),
which lets them call the API and the headless endpoints across origins. The API of the
endpoints is allauth's `headless specification`_; the project does not serve allauth's
own specification page, whose viewer loads from a CDN the Content Security Policy blocks.

.. _headless specification: https://docs.allauth.org/en/latest/headless/openapi-specification/

**Login.** ``POST /_allauth/app/v1/auth/login`` with ``{"{% if cookiecutter.username_type == 'email' %}email{% else %}username{% endif %}": ..., "password": ...}``
answers ``200`` with ``meta.access_token`` and ``meta.refresh_token``. The access token is a
JWT signed by the project with a key of its own (``DJANGO_HEADLESS_JWT_PRIVATE_KEY``),
valid for ``DJANGO_HEADLESS_JWT_ACCESS_TOKEN_EXPIRES_IN`` seconds (five minutes); the
refresh token for ``DJANGO_HEADLESS_JWT_REFRESH_TOKEN_EXPIRES_IN`` seconds (a day). A
token is valid only while the session behind it exists on the server, so a logout, a key
rotation or an administrator ending the session invalidates it at once.

**Pending flows.** When the login is not complete, the answer is ``401`` with the
pending flow in ``data.flows`` (``"is_pending": true``) and a ``meta.session_token``:
a second factor (``mfa_authenticate``, completed with a code at
``POST /_allauth/app/v1/auth/2fa/authenticate``), or an address still to verify
(``verify_email``). The session token identifies the pending login: send it in the
``X-Session-Token`` header of the calls that complete the flow, and drop it once the
answer carries the tokens.

**Refresh.** ``POST /_allauth/app/v1/tokens/refresh`` with ``{"refresh_token": ...}``
answers a new access token and a new refresh token. The old refresh token is invalid as
soon as it is used; an expired one means signing in again.

**Logout.** ``DELETE /_allauth/app/v1/auth/session`` with the access token as
``Authorization: Bearer`` ends the session behind the tokens, and both stop working.

**The frontend contract.** allauth's mails and flows send the user to pages the
application serves at ``DJANGO_FRONTEND_URL`` (``http://localhost:5173`` in development;
its origin must be one of ``DJANGO_FRONTEND_ORIGINS``, which ``python manage.py check``
enforces), so the application implements these five paths:

==========================================  ===========================================
Path                                        The page
==========================================  ===========================================
``/account/verify-email/{key}``             confirms the address by posting ``key`` to
                                            ``/_allauth/app/v1/auth/email/verify``
``/account/password/reset``                 asks for the address and requests a reset
``/account/password/reset/key/{key}``       sets the new password with ``key``
``/account/signup``                         the signup form
``/account/provider/callback``              where a provider redirect returns, with
                                            ``error`` and ``error_process`` on failure
==========================================  ===========================================

The mails link to these pages for every flow, the server-rendered signup included:
once the application exists, it is where addresses are verified and passwords reset. A
login may name a return destination (``callback_url``, ``next``); the project accepts
one on a configured frontend origin, matched by scheme, host and port, and, for the
server-rendered pages, a relative URL or its own origin. Nothing else.

**Calling the API.** Send the access token as ``Authorization: Bearer <token>`` on
every request to ``/api/``. The API treats any ``Authorization`` header, even an empty
or malformed one, as a token attempt and answers ``401`` when it does not validate; it
never falls back to the session for such a request. Without the header, the session
cookie of the server-rendered pages authenticates as before, with Django's CSRF check on
unsafe methods (htmx sends the token from ``hx-headers``). The OpenAPI schema at
``/api/openapi.json`` declares the bearer scheme.

**Signing in through {{ provider }} from the application.** The application runs
the provider's own browser flow and posts the ID token it obtains to
``POST /_allauth/app/v1/auth/provider/token``:

.. code-block:: json

    {"provider": "{% if entra %}entra{% else %}google{% endif %}", "process": "login",
     "token": {"client_id": "<the login registration's client id>", "id_token": "<the ID token>"}}

The answer is the same as a password login's: the app tokens, or a pending flow. The
project verifies the token against the provider's published keys and the login
registration's client id, and resolves the account exactly as the server-rendered
login does, so a user has one account whichever way they sign in.
{% if entra %}
With `MSAL Browser`_, use the authorization code flow with PKCE (``loginPopup`` or
``loginRedirect`` with the scopes ``openid``, ``profile`` and ``email``) and post the
``idToken`` of the authentication result. The SPA and the server-rendered login share
the login registration: add a *Single-page application* platform to it, under
*Authentication*, with the application's redirect URI (the origin the SPA is served
from). The *Web* platform of the server-rendered login stays. The API's registration
and the identities of calling services are separate registrations, as described below.

.. _MSAL Browser: https://learn.microsoft.com/entra/identity-platform/msal-overview
{% else %}
With `Google Identity Services`_, use ``google.accounts.id`` (the *Sign in with Google*
button or One Tap), which hands the application an ID token as the ``credential`` of
the response; there is no code to exchange. Post that credential as the ``id_token``.
The SPA and the server-rendered login share the web client: add the application's
origin to the client's *Authorised JavaScript origins* in the Google Cloud console.
Calling services use their own identities, as described below.

.. _Google Identity Services: https://developers.google.com/identity/gsi/web
{% endif %}
allauth also serves ``POST /_allauth/app/v1/auth/provider/redirect`` for the app
client. It drives the login through the project's own redirects and ends on the
application's ``/account/provider/callback`` page without handing it tokens, which suits
a browser client with cookies, not this application; the token endpoint above is the
supported path.

**Rotating the signing key.** Rotation is forced re-authentication: every access and
refresh token fails as soon as every process uses the new key, and the sessions behind
them are deleted so that a retained session token stops working as well. The operation
is brief, and its order matters, because a login served between the purge and the new
key would create a session the purge misses:

#. Drain requests: stop routing traffic to the application.
#. Replace ``DJANGO_HEADLESS_JWT_PRIVATE_KEY`` and restart every process that serves
   requests, so that no process signs or accepts tokens with the old key.
#. Run ``python manage.py revoke_jwt_sessions``, which reports how many sessions it
   removed.
#. Resume traffic. Every user of the application signs in again; the server-rendered
   pages' sessions are untouched.

The command identifies a session by the refresh-token state allauth keeps in it, so a
login still pending when the key is rotated, a second factor not yet entered, is not
identified; it holds no tokens, and completing it after the rotation issues tokens with
the new key.

**Storing the credentials.** Keep the access token in memory and send it as a bearer
token. Persist the refresh token only if the application must survive a page reload,
in a store its own origin controls (session storage, or a service worker), never in a
cookie the browser would attach on its own; treat it like a password, and prefer signing
in again over keeping it for long. The session token of a pending flow is short-lived and
belongs in memory.

{% endif -%}
{% if headless -%}
Calling services
----------------------------------------------------------------------

A service that calls the API, a batch job or another application, presents a token
{% if entra %}the tenant{% else %}Google{% endif %} issued for it, as ``Authorization: Bearer``. The project verifies
the token against the provider's published keys, applies the provider's rules and
looks the caller up among the *service registrations* of the admin: a valid signature
alone authorises nothing, an unregistered or disabled service is refused with ``401``,
and a service is never a user. Each calling service has one identity of its own;
services do not share one. The example endpoint ``GET /api/principal/`` answers who is
calling, ``{"kind": "service", "name": ...}`` for a service and
``{"kind": "user", "name": ...}`` for a user; the users routes stay user-only.
{% if entra %}
**Registering the API.** In the Microsoft Entra admin center, create a second app
registration for the API itself (the login registration stays what it is):

#. Under *Expose an API*, set the application ID URI (``api://<client id>``), and in
   the manifest set ``api.requestedAccessTokenVersion`` to ``2``, so that the tokens
   issued for the API carry the v2.0 issuer the project accepts.
#. Under *App roles*, add a role for applications, value ``Service.Access`` (or set
   ``ENTRA_SERVICE_ROLE`` to the value you choose), allowed member type *Applications*.
#. Under *Token configuration*, add the optional claim ``idtyp`` to the access token:
   the project refuses a token that does not say it was issued to an application.
#. In *Enterprise applications*, open the API's service principal and set *Assignment
   required* to *Yes*, so that only assigned services obtain a token for it.
#. Set ``ENTRA_API_CLIENT_ID`` to the registration's application (client) id: the
   audience a service's token must name. An empty one is reported by the checks.

**Registering a service.** Each calling service gets its own app registration with a
client secret or certificate; under its *API permissions*, add the API's
``Service.Access`` application permission and grant admin consent, which assigns the
role. Then, in the project's admin under *Service registrations*, add the service with
its name and, as the subject, the *Object ID* of its service principal (the enterprise
application's object id, not the registration's). The subject cannot be changed
afterwards: a new identity is a new registration.

**Obtaining a token.** As the service, with the Azure CLI::

    az login --service-principal --tenant <tenant id> \
        --username <the service's client id> --password <its secret>
    TOKEN="$(az account get-access-token --scope api://<the API's client id>/.default \
        --query accessToken --output tsv)"
    curl --header "Authorization: Bearer $TOKEN" https://{{ cookiecutter.domain_name }}/api/principal/

The project checks the token's issuer (the tenant's v2.0 endpoint), audience (the API),
tenant, ``idtyp`` (``app``), the role, and finally the registration for the token's
``oid``. Signing keys are read from the tenant's discovery endpoint when the first
token arrives, and refreshed when a token names a key id the cached set lacks.

**Deactivating a service.** Untick *Enabled* on its registration: its tokens are
refused from the next request on, whatever the provider still issues. Removing the role
assignment in the tenant stops the provider issuing tokens as well.
{% else %}
**Setting up a service.** In Google Cloud IAM, each calling service runs as a
service account of its own; create one per service, and prefer a keyless setup, an
attached service account or impersonation, over a downloaded key. In the project's
admin under *Service registrations*, add the service with its name and, as the
subject, the service account's *Unique ID* (the ``sub`` claim of its tokens, a
number, not the email address). The subject cannot be changed afterwards: a new
identity is a new registration.

**Obtaining a token.** The service asks Google for an ID token whose audience is
``GOOGLE_SERVICE_AUDIENCE`` (the site's ``https://`` URL by default):

- On Compute Engine, Cloud Run, GKE or Cloud Functions with the service account
  attached, from the metadata server::

      curl --header "Metadata-Flavor: Google" \
          "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity?audience=https://{{ cookiecutter.domain_name }}"

  The token in this standard format carries no email claim, which is why the project
  never checks one.
- From a workstation or a pipeline whose identity may impersonate the service account
  (the *Service Account OpenID Connect Identity Token Creator* role on it), with an
  explicit audience::

      TOKEN="$(gcloud auth print-identity-token \
          --impersonate-service-account=billing@project.iam.gserviceaccount.com \
          --audiences=https://{{ cookiecutter.domain_name }})"
      curl --header "Authorization: Bearer $TOKEN" https://{{ cookiecutter.domain_name }}/api/principal/

The project checks the token's issuer (``https://accounts.google.com``, with or without
the scheme), its audience and finally the registration for the token's ``sub``. An
ordinary user's ID token names the login client as its audience and its subject is
registered nowhere, so it fails twice over; no email domain is checked. Google's
signing keys are read from its discovery endpoint when the first token arrives, and
refreshed when a token names a key id the cached set lacks.

**Deactivating a service.** Untick *Enabled* on its registration: its tokens are
refused from the next request on, whatever Google still issues.
{% endif %}
**Diagnostics.** A refused token is one log record of the ``identity.verification``
logger with fixed codes and nothing from the token: the branch that refused
(``branch=service``, the verifier, or ``branch=router``, when the token's issuer
matched no branch) and the reason, ``reason=expired`` at info, the routine case, and
the suspicious ones at warning (``bad_issuer``, ``bad_audience``, ``bad_signature``,
``unknown_key``, ``key_lookup_failed``, ``unregistered``, ``disabled``, ...). A warning
repeats for the same codes at most once a minute, and then says how many the minute
swallowed, so a burst is one record.
The provider's key rotation needs nothing: a token naming a key id the cached set lacks
makes the verifier fetch the set again, at most once a minute, and a key set is
refreshed every hour regardless. A provider that cannot be reached refuses the token
(``key_lookup_failed``) and is tried again on the next one; the discovery document is
read when the first token arrives, never when the settings load, and read again on the
next token if that fails.

**Permissions.** A registration holds Django permissions, granted in the admin next
to the users' (*Service registrations*, *Permissions*), and answers ``has_perm`` with
the full ``app_label.codename`` like a user does; a disabled registration holds none. A
route both users and services may call, one under ``either_auth``, asks for a
permission with ``require_permission`` from ``identity/permissions.py``, which answers
``403`` for a caller that lacks it, a user or a service alike, where missing or invalid
credentials are the policy's ``401``:

.. code-block:: python

    @router.get("/reports/", auth=either_auth)
    def list_reports(request: PrincipalHttpRequest) -> list[ReportSchema]:
        require_permission(request, "reports.view_report")
        ...

A permission says what a caller may do, not which rows it may see. The data-access
boundary, which records a service or a user may read or change, is the project's to
add to its own models and queries (the users API, for one, answers only the caller's
own row); these permissions do not enforce it.
{% endif -%}
Smoke test
----------------------------------------------------------------------

Nothing in the test suite talks to {{ provider }}: ``users/tests/test_social_login.py``
drives allauth's callback with the token verification patched out. After registering the
application, check the real thing by hand, in Chrome as well as another browser, because
only Chrome enforces ``form-action`` on the redirect:

#. With the credentials set, open the login page: the {{ provider }} button is there.
#. Sign in through it with a browser console open. The consent screen appears the first
   time; the profile page follows, and the console shows no policy violation.
#. Sign out and sign in again: the same account.
#. Sign in with an account whose address already belongs to a local account: no link is
   made, and that address receives the notice.
{% if not entra %}#. Sign in with a Google account whose address is not verified: the verification mail
   arrives before the profile page.
{% endif %}
