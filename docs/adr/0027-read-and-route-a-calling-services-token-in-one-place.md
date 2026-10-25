---
status: accepted
---

# Read and route a calling service's token in one place

`docs/adr/0019` gave the metrics endpoint the routing of the API's `either_auth` policy: the
credential's unverified `iss` claim picks the branch, a configured provider issuer means the
verifier decides, and neither branch falls back to the other. It moved `unverified_issuer` into
`identity/verification.py` for both to read, and left the rest of the routing to each caller: the
parse of the `Authorization` header, written once as `bearer_token` in `identity/auth.py` and once
as `presented_credential` in `metrics.py`, and the rule on the issuer, `isinstance(issuer, str)
and issuer in settings.IDENTITY_SERVICE_ISSUERS`, written in both. Two routers that must decide
alike had two copies of the decision.

The tests had the same shape. `identity/tests/test_verification.py` holds the verifier's rules in
`BROKEN`, and `identity/tests/test_services.py` held the same rules again in `REJECTED`, driven
through the principal endpoint, with the verifier's other refusals (a disabled registration,
another algorithm, an unknown key) and its logging tested a second time the same way. And the
verifier's key source, a protocol so that a source could be injected, was reachable only by
rebinding the `DiscoveredKeys` class in the module, which the test file imported first so that its
own tests of that class ran on the real one.

So what the routers share now lives in the verifier's module, and what each decides stays its
own. `bearer_token` and `is_configured_issuer` sit beside `unverified_issuer` in
`identity/verification.py`; `either_auth` and the metrics endpoint call them, and with a provider
but no Django Ninja the endpoint is the only caller. Without a provider there is no identity app,
and `metrics.py` keeps a parse of its own under that arm: the one copy left, in a module that
already forks on the same answer throughout. `provider_keys` is the one function that says where
the provider's keys come from; `key_source` still decides whether to ask for them at all, and
`use_keys` in the test support replaces `provider_keys` and nothing else. The verifier's rules are
tested once, against the verifier; `test_services.py` tests the router: which branch a token goes
to, that a refusal is the answer, who the route then sees. The generated `tests/test_metrics.py`
was the endpoint's router tests already and is unchanged.

## Considered options

- **Leave the two copies**, as `docs/adr/0019` did, because the alternative it weighed was the
  endpoint calling the Ninja policy. Rejected: that option tied the endpoint to Django Ninja, and
  the shared functions do not; the module both callers already import from is where they belong.
- **A module of their own, `identity/routing.py`.** Rejected: `unverified_issuer` moved into the
  verifier's module one decision ago, and the three functions are forty lines that every reader
  of the verifier needs beside it. A module earns its name with a reader of its own.
- **A predicate on the token, `names_a_configured_issuer(token)`**, which would read best at the
  endpoint. Rejected: `either_auth` reads the issuer once to tell a token without one (the app's
  own) from one no branch verifies, and a predicate on the token would parse it a second time. The
  predicate takes the issuer `unverified_issuer` read.
- **A parse the whole project shares**, outside the identity app, so that `metrics.py` never
  forks on it. Rejected: a module for five lines, generated for every project, whose only readers
  are generated with a provider or with Prometheus.
- **The tests inject through `key_source`.** Rejected: that bypasses `configured()`, which the
  tests of a deployment naming no provider rely on.

## Consequences

A change to how a credential is read, or to which issuers route to the verifier, is made once and
holds for the API and the endpoint alike; the wiring test asserts that `metrics.py` imports the
parse from the identity app exactly when the verifier is generated. `test_verification.py` gains
the direct tests of what a router reads (`TestWhatARouterReads`) and of the keys' seam
(`TestWhereTheKeysComeFrom`, which overrides the module's injecting fixture to reach the real
`provider_keys`); `test_services.py` is half its length. The generated project behaves as it did:
every status, record and branch is what it was.
