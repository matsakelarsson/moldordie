"""Compare the projects two revisions of this template generate.

    uv run scripts/compare_generated.py [--base REVISION] [--jobs N] ["name=value ..." ...]

Every supported combination of the working tree's generation tests is baked from the base
revision (``main`` unless ``--base`` names another) and from the working tree as it stands,
uncommitted changes included, once with the default free-text answers and once with the
hostile ones. The values drawn on generation are masked, and every file that differs, is
missing or is new is listed per combination, with a unified diff; so is a file whose
executable bit changed, which git records, and a directory left empty on one side only. The
exit status is non-zero if anything differs or a bake fails.

A fork that no supported combination reaches is compared by passing the answers that reach
it: each extra argument is one row, a group of ``name=value`` as ``.github/workflows/ci.yml``
writes them, checked against the option catalogue.

    uv run scripts/compare_generated.py "use_docker=y postgresql_version=14"

What this proves is narrow: that the rows it baked generate the same trees from both
revisions. It says nothing about a row it did not bake, and both revisions are baked by the
working tree's environment, so nothing about a change of Cookiecutter's version either. A
drawn value is compared as a mask, so neither its length, its alphabet nor which files share
it is compared: the hook's tests hold those. It bakes every row twice, which is why it is a
maintainer's script and no part of the suite; ``docs/adr/0005`` records the comparison this
automates.
"""

import argparse
import difflib
import io
import json
import os
import shlex
import subprocess
import sys
import tarfile
import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # the repository root, when run as a script

from local_extensions import OPTIONS
from tests.test_cookiecutter_generation import HOSTILE_ANSWERS
from tests.test_cookiecutter_generation import RE_DRAWN_VALUE
from tests.test_cookiecutter_generation import SECRET_FILES
from tests.test_cookiecutter_generation import SUPPORTED_COMBINATIONS

ROOT = Path(__file__).resolve().parents[1]
# What a drawn value is compared as.
MASK = "<drawn>"


def parse_row(text: str) -> dict[str, str]:
    """The answers of one extra row: a group of ``name=value``, each an option of the catalogue.

    The check is the one the CI rows get in ``tests/test_options.py``: an option the catalogue
    does not have, or a choice the option does not offer, is an error rather than a bake of the
    default project.
    """
    answers = {}
    for token in shlex.split(text):
        name, separator, value = token.partition("=")
        if not separator:
            msg = f"{token!r} is not name=value"
            raise ValueError(msg)
        if name not in OPTIONS:
            msg = f"{name!r} is not an option"
            raise ValueError(msg)
        if OPTIONS[name].choices and value not in OPTIONS[name].choices:
            msg = f"{value!r} is not a choice of {name}"
            raise ValueError(msg)
        answers[name] = value
    return answers


@dataclass(frozen=True)
class Difference:
    """One file the two revisions do not generate alike."""

    path: str
    """Relative to the directory the project was baked into, so it starts with the project slug."""
    change: str
    """``differs``, ``is missing`` (the working tree no longer generates it), ``is new``,
    ``is now executable`` or ``is no longer executable``."""
    diff: str = ""
    """A unified diff from the base revision's content to the working tree's, where both are text."""


def files_of(root: Path) -> dict[str, Path]:
    """Every file below ``root`` by its path relative to it, and every empty directory, which no file reveals."""
    return {
        path.relative_to(root).as_posix(): path
        for path in root.rglob("*")
        if path.is_file() or not any(path.iterdir())
    }


def comparable(path: str, content: bytes) -> str | bytes:
    """``content`` as it is compared: text where it is text, with the drawn values masked.

    The generation tests say which files hold a drawn value (``SECRET_FILES``, relative to the
    project) and what one looks like (``RE_DRAWN_VALUE``). Only those files are masked: a long
    run of letters and digits anywhere else, a pinned digest say, is compared as it stands.
    """
    try:
        text = content.decode()
    except UnicodeDecodeError:
        return content
    _, _, in_project = path.partition("/")
    return RE_DRAWN_VALUE.sub(MASK, text) if in_project in SECRET_FILES else text


def is_executable(path: Path) -> bool:
    return bool(path.stat().st_mode & 0o111)


def differences(base: Path, working_tree: Path) -> list[Difference]:
    """What differs between a project baked from the base revision into ``base`` and the same
    answers baked from the working tree into ``working_tree``, in path order."""
    base_files = files_of(base)
    tree_files = files_of(working_tree)
    found = []
    for path in sorted(base_files.keys() | tree_files.keys()):
        if path not in tree_files:
            found.append(Difference(path, "is missing"))
            continue
        if path not in base_files:
            found.append(Difference(path, "is new"))
            continue
        if base_files[path].is_dir() or tree_files[path].is_dir():
            if base_files[path].is_dir() != tree_files[path].is_dir():
                found.append(Difference(path, "differs"))
            continue
        before = comparable(path, base_files[path].read_bytes())
        after = comparable(path, tree_files[path].read_bytes())
        if before != after:
            diff = ""
            if isinstance(before, str) and isinstance(after, str):
                diff = "".join(
                    difflib.unified_diff(
                        before.splitlines(keepends=True),
                        after.splitlines(keepends=True),
                        fromfile=f"base/{path}",
                        tofile=f"working tree/{path}",
                    ),
                )
            found.append(Difference(path, "differs", diff))
        if is_executable(base_files[path]) != is_executable(tree_files[path]):
            change = "is now executable" if is_executable(tree_files[path]) else "is no longer executable"
            found.append(Difference(path, change))
    return found


@dataclass(frozen=True)
class Bake:
    """One project to generate from both revisions: a row, under one set of free-text answers."""

    row: dict[str, str]
    hostile: bool

    @property
    def answers(self) -> dict[str, str]:
        """What Cookiecutter is given; a free-text answer of the row's own outlasts the hostile one."""
        return {**HOSTILE_ANSWERS, **self.row} if self.hostile else self.row

    @property
    def name(self) -> str:
        answers = " ".join(f"{name}={value}" for name, value in self.row.items()) or "the defaults"
        return f"{answers} (hostile free text)" if self.hostile else answers


def git(*arguments: str) -> bytes:
    return subprocess.run(["git", "-C", str(ROOT), *arguments], check=True, capture_output=True).stdout  # noqa: S603, S607


def materialise(revision: str, target: Path) -> None:
    """Export the template as ``revision`` holds it into ``target``.

    An archive, not a worktree or a checkout: nothing in the repository changes, its
    administrative files included, and no branch is switched.
    """
    with tarfile.open(fileobj=io.BytesIO(git("archive", "--format=tar", revision))) as archive:
        archive.extractall(target, filter="data")


def generate(template: Path, bake: Bake, directory: Path) -> str | None:
    """Bake ``bake`` from ``template`` into ``directory / "out"``; what was said if the bake failed, else None.

    A process per bake, started in ``template``: Cookiecutter imports ``local_extensions`` by
    name, so one process could only ever bake with the first revision's catalogue and filters.
    Whatever else a bake writes stays in ``directory``: the replay file and the clone directory,
    which would go to the home directory, and the rendered hooks, which Cookiecutter leaves in
    the temporary directory.
    """
    temporary = directory / "tmp"
    temporary.mkdir(parents=True)
    config = directory / "config.yaml"
    # YAML reads JSON, which quotes whatever the temporary directory is called.
    settings = {"replay_dir": str(directory / "replay"), "cookiecutters_dir": str(directory / "clones")}
    config.write_text(json.dumps(settings))
    command = [sys.executable, "-B", "-m", "cookiecutter", str(template), "--no-input"]
    command += ["--config-file", str(config), "--output-dir", str(directory / "out")]
    command += [f"{name}={value}" for name, value in bake.answers.items()]
    result = subprocess.run(  # noqa: S603
        command,
        cwd=template,
        env={**os.environ, "TMPDIR": str(temporary)},
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        return None
    # What the hook and Cookiecutter said, without the frames of the tracebacks between.
    said = [line for line in result.stdout.splitlines() if line and not line.startswith((" ", "Traceback"))]
    return "\n".join(said) or f"Cookiecutter exited with status {result.returncode}"


# The two sides of a comparison: the directory each is baked under, and what a report calls it.
SIDES = {"base": "the base revision", "tree": "the working tree"}


def compare(
    base: Path,
    working_tree: Path,
    bakes: list[Bake],
    scratch: Path,
    jobs: int,
) -> list[tuple[Bake, list[str]]]:
    """Bake every one of ``bakes`` from both templates under ``scratch``; what to report for each, in order.

    Nothing to report means the two trees are the same. A bake that either side fails is
    reported as such, never skipped: that row was not compared.
    """
    templates = {"base": base, "tree": working_tree}
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        failures = {
            (side, index): pool.submit(generate, templates[side], bake, scratch / side / f"{index:03}")
            for side in SIDES
            for index, bake in enumerate(bakes)
        }
    report = []
    for index, bake in enumerate(bakes):
        lines = [
            f"{SIDES[side]} fails to bake it:\n{said}"
            for side in SIDES
            if (said := failures[side, index].result()) is not None
        ]
        if not lines:
            found = differences(scratch / "base" / f"{index:03}" / "out", scratch / "tree" / f"{index:03}" / "out")
            lines = [f"{difference.path} {difference.change}\n{difference.diff}".rstrip() for difference in found]
        report.append((bake, lines))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare the projects the base revision and the working tree generate, for every "
        "supported combination and for the extra rows given.",
    )
    parser.add_argument("--base", default="main", help="the revision to compare the working tree with (default: main)")
    parser.add_argument("--jobs", type=int, default=os.cpu_count() or 1, help="bakes to run at once")
    parser.add_argument("rows", nargs="*", metavar="ROW", help='an extra row to bake: "name=value name=value"')
    arguments = parser.parse_args()
    if arguments.jobs < 1:
        parser.error("--jobs takes a positive number")
    try:
        rows = [*SUPPORTED_COMBINATIONS, *(parse_row(row) for row in arguments.rows)]
    except ValueError as error:
        parser.error(str(error))
    bakes = [Bake(row, hostile) for row in rows for hostile in (False, True)]
    try:
        revision = git("rev-parse", "--short", f"{arguments.base}^{{commit}}").decode().strip()
    except subprocess.CalledProcessError:
        parser.error(f"{arguments.base!r} is not a revision of this repository")

    print(f"Baking {len(bakes)} projects from {arguments.base} ({revision}) and from the working tree ...")
    with tempfile.TemporaryDirectory() as scratch:
        base = Path(scratch) / "template"
        materialise(revision, base)
        report = compare(base, ROOT, bakes, Path(scratch) / "bakes", arguments.jobs)

    unlike = [(bake, lines) for bake, lines in report if lines]
    for bake, lines in unlike:
        print(f"== {bake.name}")
        for line in lines:
            print(line)
        print()
    verdict = f"{len(unlike)} of {len(bakes)} differ or failed" if unlike else f"all {len(bakes)} are the same"
    print(
        f"{arguments.base} ({revision}) against the working tree: {verdict}. This is about the rows "
        "baked, with the drawn values masked; it says nothing about a row that was not baked.",
    )
    return 1 if unlike else 0


if __name__ == "__main__":
    sys.exit(main())
