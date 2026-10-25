---
status: accepted
---

# Write a generated module inside the reader's subset

The reader rejects a module as a whole when a name bound to a list, dict or set is mentioned
inside a compound statement (`docs/adr/0001`): the statement could alias or mutate the object
on a path the reader does not follow. With `use_docker=y`, the generated
`config/settings/local.py` appended the Docker host's gateways to `INTERNAL_IPS`, a list,
inside an `if`, so the reader rejected the local settings of every Docker project, and the
tests on them (the mail catcher's port, the Tasks backend) were string probes on the source.
`INTERNAL_IPS` is now a tuple, which the `if` extends by rebinding the name: the module is
read, and the one name the `if` decides is "conditional", explicitly. `THEMES` in
`<project_slug>/themes.py` is a tuple for the same reason.

## Considered options

- **Widen the subset**, applying `+=` inside an `if` to the name alone as a conditional
  binding. Rejected: the subset is closed (`docs/adr/0001`), and the rejection exists because
  the reader cannot tell which other names reach the object the statement changes.
- **Leave the module rejected** and the tests textual, the state until now. Rejected: a string
  probe passes on a commented-out line and says nothing about what the module binds, and the
  local settings of every Docker project were outside what the suite reads.
- **A tuple**, the choice, annotated as one of any length since the `if` extends it: Django
  asks for a sequence of addresses, the module changes it nowhere else, and the reader reads
  the module.

## Consequences

A generated module that a test reads from source is written in the reader's subset where that
costs the module nothing: a sequence that is only ever read is a tuple, and a conditional
change rebinds a name rather than mutating an object. A change that takes a module outside the
subset fails the generation tests with the reader's reason rather than silently. Where the
rewrite would cost the generated code something, the assertion stays textual, as
`docs/adr/0001` says.
