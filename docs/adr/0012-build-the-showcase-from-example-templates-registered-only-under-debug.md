---
status: accepted
---

# Build the showcase from example templates, registered only under DEBUG

The showcase at `/ui/components/` shows every component of the UI library, its states and
how to write it. It is a development tool: its forms have nothing behind them, and its theme
preview writes to the session.

Each example is a template under `templates/ui/examples/`. The showcase renders it live and
shows it as written through the `example_source` tag, which reads only the examples
`ui/showcase.py` names, from the template file rather than from Cotton's compiled output. A
component's contract is shown the same way, from the comment its own template opens with.
The routes are registered in the `DEBUG` block of `config/urls.py`, next to the error page
previews, and the tests reach them through a URL configuration of their own.

## Considered options

- **Snippets written by hand beside each example, inside `verbatim`.** They drift from the
  live example beside them.
- **Routes always registered, the views answering 404 without `DEBUG`.** Simpler to test,
  but the routes would exist in production.

## Consequences

An example cannot show one thing and render another. Adding a component to the showcase
means an example template, its name in `ui/showcase.py` and a section on the page. The tags
read template files while rendering, which only the development server's showcase does.
The generated tests do not load the project's URL configuration under `DEBUG`; the
template's generation test checks that the registration sits in its `DEBUG` block.
