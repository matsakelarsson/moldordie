"""The copy that becomes a new app: every file of the app template under new names, and
then the project's own formatters over it.

The renaming leaves the layout to them. The order of a file's imports within the
package's section depends on how the app's name sorts against the package's other
modules, so the copy's imports are sorted for its name; a longer name can push a line
past the limit, so the Python is formatted and the linter's fixes applied, and a tag's
attributes past djLint's, so the templates are formatted too. The formatters are found
on the path, as Django's own ``startapp`` finds black; without them the copy stands,
and the pre-commit hooks of the first commit finish it.

Standard library only, so the repository's tests load it by path.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

# Byte code, which a copy never carries
SKIPPED_DIRECTORIES = frozenset({"__pycache__"})


def copy_renamed(
    source: Path,
    target: Path,
    rename: Callable[[str], str],
) -> list[Path]:
    """Copy the tree at ``source`` to ``target``, which must not exist, with ``rename``
    applied to every part of every path and to every file's text. Returns the files
    written, relative to ``target``."""
    if target.exists():
        msg = f"{target} exists"
        raise FileExistsError(msg)
    written = []
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        if path.is_dir() or SKIPPED_DIRECTORIES.intersection(relative.parts):
            continue
        renamed = Path(*(rename(part) for part in relative.parts))
        destination = target / renamed
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(rename(path.read_text()))
        written.append(renamed)
    return written


def run_formatters(directory: Path) -> list[str]:
    """Run the formatters the pre-commit hooks run over ``directory``, each under the
    project's configuration, which both find from the directory upwards: ruff's fixes
    and its formatter over the Python, twice, since a call the formatter splits over
    lines wants the trailing comma the linter then adds and the formatter then lays
    out one argument per line; and djLint's formatter over the templates. Returns the
    names of the formatters not on the path, which ran nothing."""
    missing = []
    ruff = shutil.which("ruff")
    if ruff is None:
        missing.append("ruff")
    else:
        fix = [ruff, "check", "--fix", "--exit-zero", "--quiet", "."]
        for _ in range(2):
            subprocess.run(fix, cwd=directory, check=True)  # noqa: S603
            fmt = [ruff, "format", "--quiet", "."]
            subprocess.run(fmt, cwd=directory, check=True)  # noqa: S603
    djlint = shutil.which("djlint")
    if djlint is None:
        missing.append("djlint")
    else:
        # Exits 1 for a file it changed, which is the point
        reformat = [djlint, "--reformat", "--quiet", "."]
        subprocess.run(reformat, cwd=directory, check=False)  # noqa: S603
    return missing
