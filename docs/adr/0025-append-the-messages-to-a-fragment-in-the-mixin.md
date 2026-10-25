---
status: accepted
---

# Append the messages to a fragment in the mixin

A message added during an htmx request has to reach the page, and the page's messages
container sits outside whatever element the request swaps, so a fragment carries the
container marked `hx-swap-oob="true"`. Until now each partial included `base.html#messages`
under the `htmx_fragment` flag: six includes across three templates, one partial (the tabs)
without, and a rule every new partial had to remember, with no failure when it forgot.
`HtmxTemplateMixin` now appends the rendered messages partial to every fragment, in a
post-render callback, so a message the view adds while the partial renders is carried too.
A partial holds its content alone; the notices demo's partial is empty, and the messages
are its whole answer. `fragment_or_redirect` on the mixin answers a post with the fragment
or, without htmx, with a redirect, which three example views had each spelled out.

## Considered options

- **Each partial includes the messages**, the state until now. Rejected: the repetition,
  and the omission that nothing reports.
- **A wrapping template or a template tag** that renders the partial and the messages
  together. Rejected: a second template per view, or a tag standing between the view and
  its template, for what the view already decides when it selects the partial.
- **The mixin appends the messages after rendering**, the choice: the one place that knows
  a fragment is being rendered, and the callback runs after the partial has, so the
  messages are complete.

## Consequences

Every fragment carries the container, empty or not, so an htmx request replaces the
messages on screen; five of the six partials already did so, the tabs now do as well. A
function-based view appends `render_messages(request)` itself, as the mixin's docstring
shows. `fragment` in the generated `tests/responses.py` holds every fragment the view tests
receive to the contract: nothing a page loads, and the container marked for the swap, once;
`page` holds a page to the container once, unmarked.
