"""The copy that becomes a new app: every file of the app template under new names, and
then the project's own formatters over it.

The renaming leaves the layout to them. The order of a file's imports within the
package's section depends on how the app's name sorts against the package's other
modules, so the copy's imports are sorted for its name; a longer name can push a line
past the limit, so the Python is formatted and the linter's fixes applied, and a tag's
attributes past djLint's, so the templates are formatted too. The formatters are found
on the path, as Django's own ``startapp`` finds black; without them, or when one fails,
the copy stands and the pre-commit hooks of the first commit finish it.

Standard library only, so the repository's tests load it by path.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


def skipped(relative: Path) -> bool:
    """Byte code, and a hidden file, an editor's or the system's: a copy has neither."""
    return any(part == "__pycache__" or part.startswith(".") for part in relative.parts)


def copy_renamed(
    source: Path,
    target: Path,
    rename: Callable[[str], str],
) -> list[Path]:
    """Copy the tree at ``source`` to ``target``, which must not exist, with ``rename``
    applied to every part of every path and to every file's text; a file that is not
    UTF-8 text is copied as it is. Returns the files written, relative to ``target``.
    A copy that fails leaves nothing behind."""
    if not source.is_dir():
        msg = f"{source} is not a directory"
        raise FileNotFoundError(msg)
    if target.exists():
        msg = f"{target} exists"
        raise FileExistsError(msg)
    written = []
    try:
        for path in sorted(source.rglob("*")):
            relative = path.relative_to(source)
            if path.is_dir() or skipped(relative):
                continue
            renamed = Path(*(rename(part) for part in relative.parts))
            destination = target / renamed
            destination.parent.mkdir(parents=True, exist_ok=True)
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                shutil.copyfile(path, destination)
            else:
                destination.write_text(rename(text), encoding="utf-8")
            written.append(renamed)
    except BaseException:
        shutil.rmtree(target, ignore_errors=True)
        raise
    return written


def run_formatters(directory: Path) -> list[str]:
    """Run the formatters the pre-commit hooks run over ``directory``, each under the
    project's configuration, which both find from the directory upwards: ruff's fixes
    and its formatter over the Python, twice, since a call the formatter splits over
    lines wants the trailing comma the linter then adds and the formatter then lays
    out one argument per line; and djLint's formatter over the templates. Returns what
    kept a formatter from finishing, a line each: not on the path, or an exit that is
    no result of its own, with what it said."""
    problems = []
    ruff = shutil.which("ruff")
    if ruff is None:
        problems.append("ruff is not on the path")
    else:
        fix = [ruff, "check", "--fix", "--exit-zero", "--quiet", "."]
        fmt = [ruff, "format", "--quiet", "."]
        try:
            for _ in range(2):
                run(fix, directory, check=True)
                run(fmt, directory, check=True)
        except subprocess.CalledProcessError as error:
            said = error.stderr.decode().strip()
            problems.append(f"ruff exited with {error.returncode}: {said}")
    djlint = shutil.which("djlint")
    if djlint is None:
        problems.append("djlint is not on the path")
    else:
        # Exits 1 for a file it changed, which is the point
        run([djlint, "--reformat", "--quiet", "."], directory, check=False)
    return problems


def run(command: list[str], directory: Path, *, check: bool) -> None:
    """``command`` in ``directory``, its output kept for the error it may raise."""
    subprocess.run(command, cwd=directory, check=check, capture_output=True)  # noqa: S603
