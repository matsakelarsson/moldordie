"""Which generated files cite a path that the answers removed, decided on plain text.

A generated project should send its reader nowhere that its own answers deleted. The check
is handed the project's text files, the removed paths and the citations a maintainer allowed;
like the reader it asserts nothing, and it imports nothing from the hook or from pytest.
"""

import re
from collections.abc import Iterable
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class Citation:
    """A generated file naming a path its project does not have."""

    file: str
    """The file that cites, relative to the project root."""
    path: str
    """The removed path it cites, as it was handed in."""


@dataclass(frozen=True)
class Allowance:
    """A citation a maintainer allowed, with the reason: a listing that sends nobody anywhere."""

    file: str
    path: str
    reason: str


def spellings(path: str, package: str) -> list[str]:
    """How a file may name ``path``: as written, and relative to the project package if it lies in it."""
    inside = path.removeprefix(f"{package}/")
    return [path] if inside == path else [path, inside]


# A web address: its path segments name nothing in the project, so they are blanked before matching
RE_WEB_ADDRESS = re.compile(r"\w+://\S+")


def names(text: str, spelling: str) -> bool:
    """Does ``text`` name the path spelt ``spelling``, and not another path that merely contains it?

    A top-level directory comes with its trailing slash, and whatever follows it lies below
    it; its bare name may be prose ("docker compose up"). A directory below the top, whose
    spelling has a slash inside it, is a path however it ends, so it is matched with or without
    the trailing one. A file is matched by its whole name: what follows may not continue the
    name or make it a directory, though a full stop may end the sentence. Before either,
    nothing that would make it part of a longer name; a slash is no such thing, since ``./`` and
    an absolute path inside an image lead to the same file.
    """
    is_directory = spelling.endswith("/")
    if is_directory and "/" in spelling[:-1]:
        after = r"(?:/|(?![\w.-]))"
        pattern = re.escape(spelling[:-1]) + after
    elif is_directory:
        pattern = re.escape(spelling)
    else:
        pattern = re.escape(spelling) + r"(?![\w/-])(?!\.\w)"
    return re.search(rf"(?<![\w.-]){pattern}", RE_WEB_ADDRESS.sub(" ", text)) is not None


def citations(
    files: Mapping[str, str],
    removed: Iterable[str],
    allowed: Iterable[Allowance],
    *,
    package: str,
) -> tuple[list[Citation], list[Allowance]]:
    """The citations of ``removed`` paths in ``files`` that no allowance covers, and the allowances that covered none.

    ``files`` maps each text file of a generated project, by its path from the project root, to
    its content. ``removed`` are the paths the project's answers deleted, from the project root,
    a directory with its trailing slash. Both results are in the order of ``files``, then of
    ``removed``; and of ``allowed``.
    """
    removed = list(removed)
    allowed = list(allowed)
    cited = [
        Citation(file, path)
        for file, text in files.items()
        for path in removed
        if any(names(text, spelling) for spelling in spellings(path, package))
    ]
    covered = {(allowance.file, allowance.path) for allowance in allowed}
    found = [citation for citation in cited if (citation.file, citation.path) not in covered]
    unused = [allowance for allowance in allowed if Citation(allowance.file, allowance.path) not in cited]
    return found, unused
