"""Register an app that ``startapp`` created in a generated project, where the command's
output says: in ``LOCAL_APPS``, in the URL configuration and, where the project has a REST
API, on it.

For the integration scripts, run from the generated project's root as
``python3 <repository>/tests/register_app.py <package> <app> <Model>``. Each line goes at
the place the generated file marks or beside the users app's own registration, and a
file that does not hold its anchor exactly once is an error: the anchors are the
template's, and this says when the template moves them.
"""

from __future__ import annotations

import sys
from pathlib import Path


def edits(package: str, app: str, model: str) -> list[tuple[Path, str, str]]:
    """What to put into which file: the anchor the file holds once, and what replaces it."""
    plural = f"{model.lower()}s"
    apps_marker = "    # Your stuff: custom apps go here\n"
    urls_marker = "    # Your stuff: custom urls includes go here\n"
    users_router = f'api.add_router("/users/", "{package}.users.api.views.router")\n'
    users_import = f"from {package}.users.api.views import UserViewSet\n"
    users_viewset = 'router.register("users", UserViewSet)\n'
    return [
        (Path("config/settings/base.py"), apps_marker, f'    "{package}.{app}",\n{apps_marker}'),
        (
            Path("config/urls.py"),
            urls_marker,
            f'    path("{app}/", include("{package}.{app}.urls", namespace="{app}")),\n{urls_marker}',
        ),
        (
            Path("config/api.py"),
            users_router,
            f'{users_router}api.add_router("/{plural}/", "{package}.{app}.api.views.router")\n',
        ),
        (
            Path("config/api_router.py"),
            users_import,
            f"from {package}.{app}.api.views import {model}ViewSet\n{users_import}",
        ),
        (
            Path("config/api_router.py"),
            users_viewset,
            f'{users_viewset}router.register("{plural}", {model}ViewSet)\n',
        ),
    ]


def register(root: Path, package: str, app: str, model: str) -> list[Path]:
    """Apply the edits to the files under ``root`` the project has; the API's files are
    there only with a REST API. Returns the files changed."""
    changed = []
    for relative, anchor, replacement in edits(package, app, model):
        path = root / relative
        if not path.exists():
            continue
        text = path.read_text()
        if text.count(anchor) != 1:
            msg = f"{path} holds {anchor!r} {text.count(anchor)} times, not once"
            raise SystemExit(msg)
        path.write_text(text.replace(anchor, replacement))
        changed.append(relative)
    return changed


if __name__ == "__main__":
    for path in register(Path.cwd(), *sys.argv[1:4]):
        print(f"registered in {path}")
