---
status: accepted
---

# Stop merging upstream, and read its releases instead

moldordie began as a fork of cookiecutter-django and merged its releases into `main` until
Release 2026.9.8, the merge base at the time of this decision. Between that release and
Release 2026.10.15, upstream made 100 commits over twelve releases, touching 25 files. Eight of
those files this fork has deleted: the requirements files, `package.json` and its lock, the
webpack and gulp configurations. Of the rest, the generation tests, the post-generation hook,
the settings and the docs are files this fork has rewritten end to end, and upstream's hunks in
them are about things the fork no longer has: a webpack bundle directory in `base.py`, the
package lock in the hook, the frontend build arguments in the production Compose file and the
Dockerfiles, the webpack paragraphs of two docs pages. What is left is two base-image bumps, of
the aws-cli and nginx images, and upstream's own changelog, contributors and lock. Not one
hunk applied through a merge: the two image bumps are the kind this repository's
`.github/dependabot.yml` is configured to make, and the first thing to port by hand under the
practice below.

That is not a bad month; it is the shape the fork has taken. The generated project now pins its
dependencies in a templated `pyproject.toml` under uv rather than in requirements files, builds
its stylesheet with Tailwind's standalone CLI and ships no Node.js, no bundler and no JavaScript
of its own, signs in through an identity provider, exports metrics or telemetry, runs three
deployed environments from one shared source, binds derived answers before any file renders,
and is generated and tested through a reader, removal rules and wiring functions that upstream
does not have. Its hooks, its tests, its settings and its docs share no lines with upstream's
that a merge could carry a change across. A merge from here on would conflict in every touched
file, and every resolution would be "keep ours".

Upstream is no longer merged. It stays an `upstream` remote and a lineage line in the README,
and it is read: each of its releases is checked for a change that applies to what this fork
still has, which is a Django setting, a Compose or Dockerfile detail, or a hook behaviour, and
such a change is ported by hand in a pull request of its own that names the upstream release.
Twelve releases took a minute to read and offered nothing; that is the expected cost.

## Considered options

- **Keep merging**, resolving the conflicts each time. Rejected: every resolution is "keep
  ours", which is work that produces nothing and a merge commit that says otherwise.
- **Cherry-pick upstream commits** instead of merging the branch. Rejected for the same reason:
  the commits touch the same rewritten files, and a cherry-pick that applies is one that could
  have been ported by hand in less time.
- **Drop the remote and the lineage.** Rejected: upstream's releases are still the cheapest
  watch list for Django-related changes a template of this kind should make, and the history up
  to 2026.9.8 is theirs.
- **Reading and porting by hand**, the choice.

## Consequences

Dependency bumps, which were most of upstream's commits, do not arrive this way; they never
could, since the fork's pins live in a file upstream does not have. Nothing bumps the generated
project's Python pins today, as `docs/6-about/maintainer-guide.md` records, and a mechanism for
that was considered and set aside on the day of this decision; it is a separate decision when it
is taken. Image bumps are what `.github/dependabot.yml` is configured for; it was found while
taking this decision that Dependabot has opened no pull request on this repository since the
fork, so until that is looked into they too arrive by reading. A Django setting that upstream
changes for a security reason arrives only if someone reads the release, so the maintainer
guide names reading upstream's releases as a maintainer's task. The inherited changelog stays
closed at 2026.9.8, where the fork's own begins.
