---
status: accepted
---

# Side with the boundary in the identity provider's trust decisions

Sign-in through an identity provider, app-issued tokens for a single-page application and
provider-issued tokens for calling services each rest on a decision about what the
generated project trusts. They are recorded here together because each one was a choice
between a convenience and a boundary, and the defaults side with the boundary.

**The tenant's email address is trusted, as an explicit policy.** With Entra, the login
app sets allauth's `verified_email`, so the address in the token is recorded as verified
and no verification mail is sent. Microsoft documents the `email` claim as mutable and
not guaranteed to be correct, and for a guest account it is whatever the invitation
used. The setting therefore trusts the tenant's email administration, guest policy
included, and the documentation says so; a project that does not want that turns the
setting off and gets the ordinary verification mail. Google keeps its own
`email_verified` claim: the address is verified when Google says it is.

**Linking stays explicit.** A provider login whose address belongs to an existing local
account never signs in to that account: allauth's `SOCIALACCOUNT_EMAIL_AUTHENTICATION`
and its auto-connect stay off, and the documentation names them as the opt-in. Linking
means signing in with the password and connecting the provider from the account pages.

**App-issued user tokens have one trust domain.** allauth's headless JWTs are signed
with HS256 and a dedicated key drawn per application and environment, never Django's
`SECRET_KEY`; the algorithm is fixed, allauth's token-purpose claim is checked, validation
is stateful (the session behind a token must exist) and refresh tokens rotate. The tokens
carry no issuer or audience claims: only this application issues and accepts them, and a
claim asserting so would add a check without adding a boundary.

**Rotation is forced re-authentication.** Replacing the signing key invalidates every
access and refresh token at once; a management command then deletes the sessions those
tokens pointed at, so retained session tokens stop working too. The runbook drains
requests, replaces the key in every process, runs the command and resumes traffic, so
that no session is created between the purge and the new key.

## Considered options

- **Verification mail for every provider login**: safe by construction, and pointless for
  a tenant whose addresses are administered; kept as the one-setting alternative.
- **Automatic linking by verified address**: convenient, and it lets anyone the provider
  vouches for into a local account with that address; left as an opt-in.
- **Issuer and audience claims on app tokens, or a shared key with `SECRET_KEY`**: the
  claims describe a boundary the project does not have, and a shared key would let a
  leaked token strategy key forge sessions, or the reverse.
- **Rotation as a grace period with two keys**: keeps users signed in through a rotation,
  and keeps a compromised key valid for the length of the grace period.

## Consequences

The defaults never link, never forge and never keep a compromised key alive; the
conveniences are settings the documentation names. A deployment that trusts the tenant's
addresses gets password-less sign-in without mail; one that does not flips one setting.
