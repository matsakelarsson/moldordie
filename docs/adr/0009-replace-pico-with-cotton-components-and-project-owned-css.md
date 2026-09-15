---
status: accepted
---

# Replace Pico with Cotton components and project-owned CSS

The generated project's frontend was semantic HTML styled by a vendored release of Pico
CSS, with the markup of forms, messages and django-allauth's elements written by hand in
each template. Pico was chosen without a recorded reason. A specification for the
frontend asked for a starter library of reusable components, a visual foundation the
project owns, and colour tokens that a deployment or a company record can override.

Replace Pico because its default appearance does not meet the project's visual goals. Use
Cotton for reusable Django components, and project-owned CSS so the starter library's
appearance, variants and company-colour tokens are directly editable. Keep assets
self-hosted, require no frontend build, and keep scripts out of components and fragments.
This trades an upstream styling dependency for responsibility for our own styling,
accessibility and browser compatibility.

django-cotton is configured explicitly, in the settings rather than by its default app
config: the loaders listed with Cotton's first behind Django's cache, its tags and the
library's filters as builtins, and context isolation on, so a component reads only what it
is given. Python owns the colour tokens and serves them per request (`docs/adr/0010`).

## Considered options

- **Keep Pico underneath Cotton components.** Pico exposes CSS variables for branding at
  runtime, and components could encapsulate its variant classes. Rejected because the
  appearance would still be Pico's, edited through overrides of a stylesheet the project
  does not own, which is the visual goal the specification set aside.
- **Tailwind or Basecoat.** Tailwind has a standalone compiler and Basecoat ships
  prebuilt assets, so neither requires Node. Rejected as a preference: the project avoids
  their build or distribution model, and owned CSS keeps every rule readable in the tree.
- **Cotton UI Kit.** A component set for Cotton whose additional dependencies, Tailwind
  and Alpine, and whose interaction model are what the project does not take on; the
  no-build rule is not what excludes it.
- **A CSS preprocessor.** A compile step for stylesheets the project can write directly.

## Consequences

The project styles, tests and documents its own components; accessibility, WCAG contrast
of the palettes and browser compatibility are its responsibility, checked by its tests and
a browser pass rather than inherited from a library. The migration is staged: Cotton and
the tokens land first with Pico still loaded, the components and the pages follow, and
Pico is removed only when they render every page. Any claim about the size of the finished
stylesheets waits for a measurement of them.
