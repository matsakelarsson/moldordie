import datetime as dt
import os
import re
import subprocess
from collections.abc import Iterable
from pathlib import Path

import git
import github.PullRequest
import github.Repository
from github import Auth
from github import Github
from jinja2 import Template

CURRENT_FILE = Path(__file__)
ROOT = CURRENT_FILE.parents[1]
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPOSITORY")
GIT_BRANCH = os.getenv("GITHUB_REF_NAME")

# How a pull request's labels decide where it goes in the release notes. These strings
# have to match this repo's tracker exactly to have any effect: a label that does not
# exist there silently leaves every pull request in DEFAULT_SECTION, which is how
# documentation went unsectioned while this read "docs" and the tracker said
# "documentation". Labels are checked in the order listed.
EXCLUDED_LABEL = "project infrastructure"
SECTION_LABELS = {
    "update": "Updated",
    "bug": "Fixed",
    "documentation": "Documentation",
}
DEFAULT_SECTION = "Changed"
# The order the sections appear in the release notes.
SECTIONS = (DEFAULT_SECTION, "Fixed", "Documentation", "Updated")


def main() -> None:
    """
    Script entry point.
    """
    repo = Github(auth=Auth.Token(GITHUB_TOKEN)).get_repo(GITHUB_REPO)

    # The release covers everything merged since the previous one, so a manual run
    # picks up whatever has accumulated rather than one fixed day's worth.
    release = todays_release()
    if release_exists(repo, release):
        print(f"Release {release} already exists, exiting.")
        return

    warn_about_missing_labels(repo)

    since = last_release_time(repo)
    print(f"Collecting pull requests merged since {since or 'the first commit'}")
    merged_pulls = list(iter_pulls(repo, since))
    print(f"Merged pull requests: {merged_pulls}")
    if not merged_pulls:
        print("Nothing was merged, exiting.")
        return

    # Group pull requests by type of change
    grouped_pulls = group_pulls_by_change_type(merged_pulls)
    if not any(grouped_pulls.values()):
        print("Pull requests merged aren't worth a changelog mention.")
        return

    # Generate portion of markdown
    release_changes_summary = generate_md(grouped_pulls)
    print(f"Summary of changes: {release_changes_summary}")

    # Update CHANGELOG.md file
    changelog_path = ROOT / "CHANGELOG.md"
    write_changelog(changelog_path, release, release_changes_summary)
    print(f"Wrote {changelog_path}")

    # Update version
    pyproject_path = ROOT / "pyproject.toml"
    update_version(pyproject_path, release)
    print(f"Updated version in {pyproject_path}")

    # Run uv lock
    uv_lock_path = ROOT / "uv.lock"
    subprocess.run(["uv", "lock", "--no-upgrade"], cwd=ROOT, check=False)  # noqa: S607

    # Commit changes, create tag and push
    update_git_repo([changelog_path, pyproject_path, uv_lock_path], release)

    # Create GitHub release
    github_release = repo.create_git_release(
        tag=release,
        name=release,
        message=release_changes_summary,
    )
    print(f"Created release on GitHub {github_release}")


def warn_about_missing_labels(repo: github.Repository.Repository) -> list[str]:
    """Warn about grouping labels the tracker does not have.

    Nothing can carry a label that does not exist, so such a label quietly stops
    selecting anything: pull requests keep landing in the default section and nothing
    fails. Say so where whoever ran the release will see it.
    """
    known = {label.name for label in repo.get_labels()}
    missing = sorted({EXCLUDED_LABEL, *SECTION_LABELS} - known)
    if missing:
        print(f"WARNING: not labels of this tracker, so they group nothing: {', '.join(missing)}")
    return missing


def todays_release() -> str:
    """The calendar version for a release cut now."""
    today = dt.datetime.now(tz=dt.UTC).date()
    return f"{today.year}.{today.month}.{today.day}"


def release_exists(repo: github.Repository.Repository, release: str) -> bool:
    """Whether ``release`` has already been published, so a re-run is a no-op."""
    try:
        repo.get_release(release)
    except github.UnknownObjectException:
        return False
    return True


def last_release_time(repo: github.Repository.Repository) -> dt.datetime | None:
    """When the most recent release was published, or ``None`` if there is none yet."""
    try:
        return repo.get_latest_release().published_at
    except github.UnknownObjectException:
        return None


def iter_pulls(
    repo: github.Repository.Repository,
    since: dt.datetime | None,
) -> Iterable[github.PullRequest.PullRequest]:
    """Fetch the pull requests merged after ``since``, or all of them when it is ``None``.

    The listing is sorted by update time rather than merge time, but merging updates a
    pull request, so anything merged after the cutoff sorts before anything last touched
    at or before it. Walking until that point is reached therefore sees every pull
    request in the window, however many pages it spans.
    """
    for pull in repo.get_pulls(state="closed", sort="updated", direction="desc"):
        if since is not None and pull.updated_at <= since:
            return
        if pull.merged and (since is None or pull.merged_at > since):
            yield pull


def group_pulls_by_change_type(
    pull_requests_list: list[github.PullRequest.PullRequest],
) -> dict[str, list[github.PullRequest.PullRequest]]:
    """Group pull requests by the section of the release notes they belong to."""
    grouped_pulls: dict[str, list[github.PullRequest.PullRequest]] = {section: [] for section in SECTIONS}
    for pull in pull_requests_list:
        label_names = {label.name for label in pull.labels}
        if EXCLUDED_LABEL in label_names:
            # Don't mention it in the changelog
            continue
        section = next(
            (section for label, section in SECTION_LABELS.items() if label in label_names),
            DEFAULT_SECTION,
        )
        grouped_pulls[section].append(pull)
    return grouped_pulls


def generate_md(grouped_pulls: dict[str, list[github.PullRequest.PullRequest]]) -> str:
    """Generate markdown file from Jinja template."""
    changelog_template = ROOT / ".github" / "changelog-template.md"
    # The template renders Markdown, not HTML: escaping turned the apostrophe of
    # "admin's" into an entity in the 2026.9.14 notes.
    template = Template(changelog_template.read_text(), autoescape=False)
    return template.render(grouped_pulls=grouped_pulls)


def write_changelog(file_path: Path, release: str, content: str) -> None:
    """Write Release details to the changelog file."""
    content = f"## {release}\n{content}"
    old_content = file_path.read_text()
    updated_content = old_content.replace(
        "<!-- GENERATOR_PLACEHOLDER -->",
        f"<!-- GENERATOR_PLACEHOLDER -->\n\n{content}",
    )
    file_path.write_text(updated_content)


def update_version(file_path: Path, release: str) -> None:
    """Update template version in pyproject.toml."""
    old_content = file_path.read_text()
    updated_content = re.sub(
        r'\nversion = "\d+\.\d+\.\d+"\n',
        f'\nversion = "{release}"\n',
        old_content,
    )
    file_path.write_text(updated_content)


def update_git_repo(paths: list[Path], release: str) -> None:
    """Commit, tag changes in git repo and push to origin."""
    repo = git.Repo(ROOT)
    for path in paths:
        repo.git.add(path)
    message = f"Release {release}"

    user = repo.git.config("--get", "user.name")
    email = repo.git.config("--get", "user.email")

    repo.git.commit(
        m=message,
        author=f"{user} <{email}>",
    )
    repo.git.tag("-a", release, m=message)
    server = f"https://{GITHUB_TOKEN}@github.com/{GITHUB_REPO}.git"
    print(f"Pushing changes to {GIT_BRANCH} branch of {GITHUB_REPO}")
    repo.git.push(server, GIT_BRANCH)
    repo.git.push("--tags", server, GIT_BRANCH)


if __name__ == "__main__":
    if GITHUB_REPO is None:
        raise RuntimeError("No github repo, please set the environment variable GITHUB_REPOSITORY")
    if GIT_BRANCH is None:
        raise RuntimeError("No git branch set, please set the GITHUB_REF_NAME environment variable")
    main()
