---
status: accepted
---

# Fall back to the configured theme when a request's theme cannot be served

A request's theme can come from more than the settings: under `DEBUG` from the preview the
showcase keeps in the session, and in a downstream application from the colours a company
record holds. Each is validated when it is chosen, by the preview form or by the
application's own form, but can stop being servable later, when a palette or `UI_BRAND`
changes beneath it. The system checks cover only the settings, so `resolve_theme`
validates the merged result on every request.

When a preview or a company's colours cannot be served, `resolve_theme` serves the
configured theme instead and logs a warning naming the source that failed. The fallback is
validated too: a configured theme that cannot be served raises `ImproperlyConfigured`. A
stale preview is removed from the session; a company record is left untouched, for its
owner to correct. Only a theme validation failure, `InvalidThemeError`, is caught, and the
theme is resolved once per request and cached on it.

## Considered options

- **Raise.** One bad company record, or a preview left over from before a palette change,
  would turn every page into a server error.

## Consequences

A company whose colours stop validating sees the deployment's theme until the record is
corrected, and the log names the source. A developer whose preview goes stale loses it with
a warning instead of an error page. Any other error while resolving, a database failure
reading the session for one, still propagates.
