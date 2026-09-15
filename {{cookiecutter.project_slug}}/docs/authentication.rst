{%- set entra = cookiecutter.identity_provider == 'entra' -%}
{%- set provider = 'Microsoft Entra ID' if entra else 'Google' -%}
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
#. Under *Authentication*, add a *Web* platform with the redirect URI
   ``https://{{ cookiecutter.domain_name }}/accounts/oidc/entra/login/callback/``; for
   development add ``http://localhost:8000/accounts/oidc/entra/login/callback/`` as well.
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
#. Under *Credentials*, create an *OAuth client ID* of type *Web application*, with the
   authorised redirect URI
   ``https://{{ cookiecutter.domain_name }}/accounts/google/login/callback/``; for
   development add ``http://localhost:8000/accounts/google/login/callback/`` as well.
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
in a ``.env`` file read with ``DJANGO_READ_DOT_ENV_FILE=True``{% endif %}; in production they belong with the
other secrets of ``.envs/.production/.django``.

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
