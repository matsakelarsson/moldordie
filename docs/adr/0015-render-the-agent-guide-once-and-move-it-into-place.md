---
status: accepted
---

# Render the agent guide once and move it into place

The `coding_agent` option writes the generated project's instructions for AI coding agents: what
the project is, the answers it was generated from, its commands, its layout and its conventions.
Each agent reads that from a file of its own — Claude Code from `CLAUDE.md`, Codex and Cursor
from `AGENTS.md`, GitHub Copilot from `.github/copilot-instructions.md` — while the text itself
is the same document, forked by a dozen answers over some two hundred lines.

The template holds that document once, as `AGENTS.md` at the project root. The removal rule for
`coding_agent == "none"` deletes it; for every other answer `place_agent_guide` moves it to the
file that agent reads, after pruning, creating the directory when it has to.

## Considered options

- **A copy of the guide per agent**: three template files rendering three names, and every
  sentence about the project's conventions written three times. Nothing would keep them in step
  but a reviewer's eye, and the guide is the file most likely to be extended.
- **Render the file name from the answer**, since Cookiecutter renders path components as
  templates: it reaches `CLAUDE.md` and `AGENTS.md`, but not
  `.github/copilot-instructions.md`, because a name cannot create a directory, and it leaves a
  template file whose name is a Jinja conditional.
- **Write `AGENTS.md` always, with the tool's file as a one-line pointer to it** — what this
  repository does for itself, where several agents work on the same tree. A generated project
  answers with the one agent it is for, so the pointer would be a second file to explain for no
  reader it has.
- **Build the guide's text in the post-generation hook**: the hook would grow the one piece of
  templated prose that does not live with the templates, and the answers it forks on are
  exactly what Jinja conditionals express in every other file.
- **Move the guide inside `prune`**: pruning only deletes, which is what lets its rules be
  checked as a table and applied in any order (see Prune in `CONTEXT.md`). A move is a content
  change, and content changes belong in `main`.

## Consequences

There is one guide to maintain, and one set of conditionals to keep true. `place_agent_guide`
must stay behind `prune` in `main`, because Copilot's guide goes into `.github/`, which pruning
deletes when the project was generated without GitHub Actions; a test asserts that order in the
hook's source, as `docs/adr/0014` does for the example dotenv.

Adding an agent is a choice in `cookiecutter.json` and a row in `AGENT_FILES`; the tests check
that the table names a file for every choice but `none`, and that a generated project holds the
guide under that name and no file for any other agent.

The guide's own claims are checked against the tree it describes:
`test_agent_guide_records_the_answers_the_project_was_generated_from` compares its table of
choices with the answers, over the list and flag options the catalogue reports, and
`test_agent_guide_lays_out_the_tree_that_was_generated` requires every path its layout names to
exist in the generated project. Both run on the combinations that write a guide, which is why
`PAIRED_COMBINATIONS` pairs a coding agent with the answers the guide has arms for: without that
pairing its conditional rows would never be rendered against a tree that has those files.
