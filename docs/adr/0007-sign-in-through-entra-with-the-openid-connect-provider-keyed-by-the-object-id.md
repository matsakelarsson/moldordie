---
status: accepted
---

# Sign in through Entra with the OpenID Connect provider, keyed by the object id

The `identity_provider` option adds sign-in through Microsoft Entra ID or Google next to
password login. For Entra the generated project uses allauth's generic `openid_connect`
provider rather than its `microsoft` provider: one app with `provider_id` `entra`, the
tenant's v2.0 discovery endpoint as `server_url`, `oid` as the `uid_field`,
`fetch_userinfo` off, the scopes `openid`, `profile` and `email`, PKCE on, and
`client_secret_basic` token authentication.

The account is keyed by `oid`, the object id of the user in the tenant, because it is
the same for every application in the tenant and never changes; `sub` is pairwise per
app registration, so a second registration, or a re-created one, would make every user a
stranger. UserInfo is not fetched because Entra's UserInfo answer lacks `oid`, and
allauth prefers the UserInfo answer over the ID token whenever it is fetched, so the
uid lookup would fail on the very claim the account is keyed by.

## Considered options

- **allauth's `microsoft` provider**: it keys the account by `id` from Microsoft Graph
  and cannot verify an ID token, which the single-page application flow posts to
  allauth's provider-token endpoint; the generic provider verifies the token against the
  tenant's published keys.
- **`sub` as the account key**: stable within one app registration only. The login
  registration serves both the server-rendered login and the single-page application,
  and a project that later splits or re-creates it would orphan every account.
- **Fetching UserInfo as well**: gives the same profile claims the ID token carries, and
  makes allauth read the account id from the answer that lacks it.

## Consequences

An Entra user has one account across the tenant's applications. The generated project
carries a provider subclass that refuses a token without a usable `oid` with allauth's
provider exception, so the callback and the token endpoint answer with allauth's own
error rather than a server error. The trust decisions around the login are recorded in
`docs/adr/0008`.
