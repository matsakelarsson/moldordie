---
status: accepted
---

# Serve the theme as a request-rendered stylesheet

The UI library's colours must be editable per deployment and, in a downstream
application, per company record, and previewed in development; its brand overrides must
be validated for contrast against the palette they land on. The generated project's
Content Security Policy allows styles from its own origin only, with no nonce for
`style-src`, so an inline `<style>` block or a `style` attribute is not an option.

Python owns the colour tokens: the three palettes in `ui/palettes.py`, complete in both
colour sets, and the overrides that a brand, a preview or a company record contributes.
`ui/themes.py` resolves them for a request, validates the result against the adjacency
table of token pairs, and renders it as a stylesheet with fixed selectors and property
names and validated colour values, which a view serves at `/ui/theme.css` with
`Cache-Control: private, no-store` and no database transaction. `static/css/ui/tokens.css`
holds the tokens that are not colours.

## Considered options

- **The palettes in the static stylesheet, as the specification first described.**
  Validation and the system checks need the values in Python, which leaves either a
  duplicate to keep in step or a parser for the project's own CSS.
- **A static stylesheet per palette, selected by an attribute.** No per-deployment
  colours, no company record, no preview.
- **An inline style block with the nonce.** The policy's `style-src` carries no nonce,
  and inline styles are the thing the policy is written to forbid.
- **The theme through `collectstatic`.** A result that depends on the request cannot be
  an immutable, hashed asset.

## Consequences

Every page fetches one small uncached stylesheet. The palette tests, the validation of an
override and the system checks read the same dictionaries, so they cannot disagree about a
colour. The stylesheet is a route, exercised by the generated tests, not a static file.
