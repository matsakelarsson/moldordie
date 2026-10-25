"""The placeholder names of the app template, and the renaming that makes a copy an app.

The app template is written for an app called ``app_template`` whose model is
``Item``. ``rename`` replaces those names in a text, in every form the template uses
them in: the module path ``scaffold.app_template`` becomes the app's, ``AppTemplate``
its name in CapWords, ``app_template`` its name, ``Item`` and ``item`` the model's name
in CapWords and lowercased as Django spells a model's name, ``Items`` and ``items`` the
plurals, with an ``s`` as Django's own ``verbose_name_plural`` adds one. A name is
matched whole: ``ItemForm`` and ``item-card`` are renamed, while ``items-center`` is a
class of Tailwind's, ``join-item`` one of daisyUI's and ``data.items`` an attribute of
something else, so none of them is touched.
``copying`` applies it to the files.

Standard library only, so the repository's tests load it by path.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

PLACEHOLDER_APP = "app_template"
PLACEHOLDER_MODEL = "Item"
# The app template, beside this file
APP_TEMPLATE = Path(__file__).resolve().parent / PLACEHOLDER_APP


def camel_case(name: str) -> str:
    """``blog_posts`` as ``BlogPosts``: an app's name in CapWords."""
    return "".join(part.capitalize() for part in name.split("_"))


def whole(
    name: str,
    *,
    hyphen_may_follow: bool = False,
    after_a_dot: bool = True,
) -> re.Pattern[str]:
    """``name`` where no letter, digit or hyphen precedes it and no lowercase letter or
    digit follows: so ``Item`` matches in ``ItemForm`` and not in ``Items`` or
    ``MenuItem``. A hyphen after it is a class name's unless ``hyphen_may_follow``.
    Unless ``after_a_dot``, a dot before it makes it an attribute of something else,
    ``data.items()`` or a template's ``data.items``, and no match."""
    dot = "" if after_a_dot else "."
    hyphen = "" if hyphen_may_follow else "-"
    return re.compile(rf"(?<![A-Za-z0-9{dot}-]){re.escape(name)}(?![a-z0-9{hyphen}])")


@dataclass(frozen=True)
class Names:
    """What a new app is called: its name, and its model's in CapWords."""

    app: str
    model: str

    @property
    def model_name(self) -> str:
        """The model's name as Django lowercases it: ``blogpost`` for ``BlogPost``."""
        return self.model.lower()

    def rules(self) -> list[tuple[re.Pattern[str], str]]:
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


def rename(text: str, names: Names) -> str:
    """``text`` with every placeholder name replaced by the new app's."""
    for pattern, replacement in names.rules():
        text = pattern.sub(replacement, text)
    return text
