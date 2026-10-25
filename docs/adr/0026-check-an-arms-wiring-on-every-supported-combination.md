---
status: accepted
---

# Check an arm's wiring on every supported combination

The generation tests checked each option's wiring, what its arm adds to a project beyond
its files, in a function of its own that chose its companion answers by hand: the metrics,
the telemetry and the Tasks framework with `use_docker=y` only, ASGI, Sentry, the identity
provider and the calling services never with it. The tree a project starts from with the
default answers was therefore never examined for the arms that measure, which is how the
arm that measures came to start only where a Compose file started it (#95). Alongside, each
function listed by hand the files its arm adds and asserted their presence, repeating the
removal rules: the identity provider's list and Entra's were the hook tests' sets written
again, in another spelling.

Each wiring is now a function of a generated project and its complete answers, derived
answers included, and one parametrized test runs every wiring on every supported
combination (`WIRINGS`, `test_wiring`). What a wiring expects follows from the answers it
reads, so a row with Docker and a row without check the same wiring, and the wiring forks
on `use_docker` where it reads a file only Docker generates. Which files an arm adds is
left to the removal rules: a second test over the same rows checks that every path a rule
lists is in the bake exactly when the answers keep it
(`test_the_tree_holds_the_paths_the_rules_leave`), the statement the hook's unit tests
pin on the template tree, now made on the bake as well; the hand-written lists are gone.

## Considered options

- **A function per wiring with hand-picked companions**, the state until now. Rejected:
  the companions were chosen once and never revisited, and #95 was what that cost.
- **Rows of companion answers per wiring**, as the calling services' test had. Rejected:
  still a choice to remember per wiring, and the rows are the matrix's rows again, written
  a second time.
- **The matrix**, the choice: the supported combinations are already baked once per
  worker (`docs/adr/0002`), so a wiring checked on all of them costs assertions, not
  bakes, and `test_every_choice_is_baked` and the paired rows guarantee that each arm is
  selected on some row and deselected on the others.

## Consequences

A wiring reads the answers it depends on and nothing else; one that asserts something only
Docker, or only a provider, generates says so in a fork, which is the statement of what it
depends on. A new arm gets a wiring function and a line in `WIRINGS`, and its files a
removal rule; a hand-written file list beside a wiring is the sign that a rule is missing.
A wiring that holds on no row for one of its answers passes without saying so: the rows
are held to the rules at file level (`docs/adr/0021`), not to the conditionals inside a
kept file, and a wiring is a conditional. The seven wirings run on the 45 rows in the time
of their assertions.
