"""The placeholder names of the app template, and the renaming that makes a copy an app.

The app template is written for an app called ``app_template`` whose model is
``Item``. ``rename`` replaces those names in a text, in every form the template uses
them in: the module path ``scaffold.app_template`` becomes the app's, ``AppTemplate``
its name in CapWords, ``app_template`` its name, ``Item`` and ``item`` the model's name
in CapWords and lowercased as Django spells a model's name, ``Items`` and ``items`` the
plurals, with an ``s`` as Django's own ``verbose_name_plural`` adds one. A name is
matched whole: ``ItemForm`` and ``item-card`` are renamed, while ``items-center`` is a
class of Tailwind's, ``join-item`` one of daisyUI's and ``data.items`` an attribute of
something else, so none of them is touched. The text is scanned once, so what a
replacement puts in is never matched again: ``item_tracker`` names an app without
becoming ``tracker_tracker``.

A new name can also be one the template uses for something else: a model called
``Page`` would rename every record ``page``, the name of the test helper that reads a
page, and ``Filter`` would make the record's form a second ``FilterForm``. ``clashes``
finds those, over the identifiers ``identifiers_of`` reads from the template's Python
and the variables its templates name, and the command refuses the name.
``copying`` applies the renaming to the files.

Standard library only, so the repository's tests load it by path.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

PLACEHOLDER_APP = "app_template"
PLACEHOLDER_MODEL = "Item"
# The app template, beside this file
APP_TEMPLATE = Path(__file__).resolve().parent / PLACEHOLDER_APP

# What a Django template binds or reads by name: the variable at the head of an
# expression, a loop's variable and what it loops over, a ``with`` assignment and an
# ``if`` operand. The braces are joined at runtime because Cookiecutter renders this
# file and would read them.
_NAME = r"([A-Za-z_]\w*)"
_VARIABLE = "{" + "{" + r"\s*" + _NAME
_LOOP_OR_IF = rf"(?:for\s+{_NAME}\s+in\s+{_NAME}|(?:if|elif)\s+(?:not\s+)?{_NAME})"
_TAG = "{" + "%" + r"\s*" + _LOOP_OR_IF
_WITH = rf"\bwith\s+{_NAME}="
TEMPLATE_VARIABLES = re.compile(f"{_VARIABLE}|{_TAG}|{_WITH}")


def camel_case(name: str) -> str:
    """``blog_posts`` as ``BlogPosts``: an app's name in CapWords."""
    return "".join(part.capitalize() for part in name.split("_"))


def whole(
    name: str,
    *,
    hyphen_may_follow: bool = False,
    after_a_dot: bool = True,
) -> str:
    """The pattern of ``name`` where no letter, digit or hyphen precedes it and no
    lowercase letter or digit follows: so ``Item`` matches in ``ItemForm`` and not in
    ``Items`` or ``MenuItem``. A hyphen after it is a class name's unless
    ``hyphen_may_follow``. Unless ``after_a_dot``, a dot before it makes it an attribute
    of something else, ``data.items()`` or a template's ``data.items``, and no match."""
    dot = "" if after_a_dot else "."
    hyphen = "" if hyphen_may_follow else "-"
    return rf"(?<![A-Za-z0-9{dot}-]){re.escape(name)}(?![a-z0-9{hyphen}])"


@dataclass(frozen=True)
class Names:
    """What a new app is called: its name, and its model's in CapWords."""

    app: str
    model: str

    @property
    def model_name(self) -> str:
        """The model's name as Django lowercases it: ``blogpost`` for ``BlogPost``."""
        return self.model.lower()

    def rules(self) -> list[tuple[str, str]]:
        """What replaces each placeholder, a longer form before the name it contains."""
        model_name = PLACEHOLDER_MODEL.lower()
        return [
            (whole(f"scaffold.{PLACEHOLDER_APP}"), self.app),
            (whole(camel_case(PLACEHOLDER_APP)), camel_case(self.app)),
            (whole(PLACEHOLDER_APP), self.app),
            (whole(f"{PLACEHOLDER_MODEL}s"), f"{self.model}s"),
            (whole(f"{model_name}s", after_a_dot=False), f"{self.model_name}s"),
            (whole(PLACEHOLDER_MODEL), self.model),
            (
                whole(model_name, hyphen_may_follow=True, after_a_dot=False),
                self.model_name,
            ),
        ]

    def pattern(self) -> re.Pattern[str]:
        """Every rule as one alternative, tried in their order at each position."""
        rules = enumerate(self.rules())
        return re.compile("|".join(f"(?P<r{i}>{pattern})" for i, (pattern, _) in rules))


def rename(text: str, names: Names) -> str:
    """``text`` with every placeholder name replaced by the new app's, in one pass."""
    rules = enumerate(names.rules())
    replacements = {f"r{i}": replacement for i, (_, replacement) in rules}

    def replace(match: re.Match[str]) -> str:
        group = match.lastgroup
        return replacements[group] if group else match[0]

    return names.pattern().sub(replace, text)


def identifiers_of(template: Path) -> frozenset[str]:
    """The names the template's Python binds, imports or uses, and the variables its
    templates name: what a new name must not become."""
    found = set()
    for path in sorted(template.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(), filename=str(path))):
            if isinstance(node, ast.Name):
                found.add(node.id)
            elif isinstance(node, ast.FunctionDef | ast.ClassDef):
                found.add(node.name)
            elif isinstance(node, ast.arg):
                found.add(node.arg)
            elif isinstance(node, ast.alias):
                found.add(node.asname or node.name.rpartition(".")[2])
    for path in sorted(template.rglob("*.html")):
        for groups in TEMPLATE_VARIABLES.findall(path.read_text()):
            found.update(group for group in groups if group)
    return frozenset(found)


def clashes(names: Names, identifiers: Iterable[str]) -> set[str]:
    """The identifiers the renaming would make two of: what it renames to a name it
    leaves alone."""
    identifiers = set(identifiers)
    kept = {name for name in identifiers if rename(name, names) == name}
    renamed = {rename(name, names) for name in identifiers - kept}
    return renamed & kept
