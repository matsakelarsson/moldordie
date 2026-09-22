"""What rows of answers keep of the paths the removal rules list, computed without a bake.

``REMOVALS`` in ``hooks/post_gen_project.py`` states which generated paths depend on the
answers. The functions here are handed rules of that shape, ``(applies, paths)`` pairs, and
complete answers (``tests/answers.py``). They import nothing from the hook, from pytest or
from the workflow, and they assert nothing: what a result means is the calling test's to say.
"""

from collections.abc import Callable
from collections.abc import Iterable
from collections.abc import Mapping
from collections.abc import Sequence
from itertools import combinations
from itertools import product
from pathlib import PurePosixPath

Answers = Mapping[str, str]
Rule = tuple[Callable[[Answers], bool], Sequence[str]]

# How many answers the search for a missing row may change. Three is what the nginx image
# takes: Docker, no cloud provider, and the WhiteNoise that the hook then insists on.
MOST_CHANGED_ANSWERS = 3


def removed_paths(rules: Iterable[Rule], answers: Answers) -> list[str]:
    """The paths the rules that apply to ``answers`` list, as written.

    The rules' share of pruning: a cleanup step that depends on the generated tree is not a
    rule, and what it deletes is not here.
    """
    return [path for applies, paths in rules if applies(answers) for path in paths]


def survives(path: str, removed: Iterable[str]) -> bool:
    """Is ``path`` left once ``removed`` are deleted: neither listed itself nor below a listed directory."""
    removed = {PurePosixPath(listed) for listed in removed}
    return not any(above in removed for above in (PurePosixPath(path), *PurePosixPath(path).parents))


def paths_kept(rules: Sequence[Rule], rows: Iterable[Answers]) -> dict[str, bool]:
    """For every path ``rules`` list, whether some row of ``rows`` keeps it.

    A row keeps a path when no rule that applies to the row lists the path or a directory
    above it: the rule for no Docker removes the whole ``compose`` directory, which other
    rules list paths under. A path no row keeps is one nothing generated from ``rows`` has.
    """
    removed_by_row = [removed_paths(rules, row) for row in rows]
    return {path: any(survives(path, removed) for removed in removed_by_row) for _, paths in rules for path in paths}


def coverage_gaps(kept: Mapping[str, bool], exemptions: Mapping[str, str]) -> tuple[list[str], list[str]]:
    """The paths of ``kept`` that no row keeps and no exemption excuses, and the stale exemptions.

    ``exemptions`` maps a path to the reason some rows may go without it. One is stale when it
    excuses nothing: a row keeps its path after all, or no rule lists the path any more.
    """
    gaps = [path for path, is_kept in kept.items() if not is_kept and path not in exemptions]
    stale = [path for path in exemptions if kept.get(path, True)]
    return gaps, stale


def fewest_answers_keeping(
    path: str,
    rules: Sequence[Rule],
    complete: Callable[[dict[str, str]], Answers],
    choices: Mapping[str, Sequence[str]],
    supported: Callable[[Answers], bool] = lambda answers: True,
) -> dict[str, str] | None:
    """The smallest row that keeps ``path``: the row that is missing.

    ``complete`` turns a row into its complete answers, which is what the rules and
    ``supported`` are asked about, and ``choices`` holds the answers each option that may
    change can take. Rows are tried by the number of answers they change from the defaults, up
    to ``MOST_CHANGED_ANSWERS``, and one that ``supported`` refuses is passed over, since a row
    that does not generate keeps nothing. None means no such row keeps the path.
    """
    defaults = complete({})
    for size in range(MOST_CHANGED_ANSWERS + 1):
        for names in combinations(choices, size):
            for values in product(*(choices[name] for name in names)):
                row = dict(zip(names, values, strict=True))
                if any(defaults[name] == value for name, value in row.items()):
                    continue  # a smaller row already had these answers
                answers = complete(row)
                if supported(answers) and survives(path, removed_paths(rules, answers)):
                    return row
    return None
