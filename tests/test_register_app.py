"""The integration scripts' registration of a scaffolded app, on hand-written files."""

import pytest

from tests.register_app import register

PACKAGE = "my_awesome_project"


@pytest.fixture
def project(tmp_path):
    (tmp_path / "config" / "settings").mkdir(parents=True)
    (tmp_path / "config" / "settings" / "base.py").write_text(
        'LOCAL_APPS = [\n    "my_awesome_project.users",\n    # Your stuff: custom apps go here\n]\n',
    )
    (tmp_path / "config" / "urls.py").write_text(
        "urlpatterns = [\n    # Your stuff: custom urls includes go here\n]\n",
    )
    return tmp_path


def test_the_settings_and_the_urls_are_edited_at_their_markers(project):
    changed = register(project, PACKAGE, "blog", "Post")

    assert [path.as_posix() for path in changed] == ["config/settings/base.py", "config/urls.py"]
    assert (project / "config" / "settings" / "base.py").read_text() == (
        'LOCAL_APPS = [\n    "my_awesome_project.users",\n    "my_awesome_project.blog",\n'
        "    # Your stuff: custom apps go here\n]\n"
    )
    assert (project / "config" / "urls.py").read_text() == (
        'urlpatterns = [\n    path("blog/", include("my_awesome_project.blog.urls", namespace="blog")),\n'
        "    # Your stuff: custom urls includes go here\n]\n"
    )


def test_a_ninja_router_is_added_after_the_users(project):
    api = project / "config" / "api.py"
    api.write_text('api.add_router("/users/", "my_awesome_project.users.api.views.router")\n')

    register(project, PACKAGE, "blog", "Post")

    assert api.read_text() == (
        'api.add_router("/users/", "my_awesome_project.users.api.views.router")\n'
        'api.add_router("/posts/", "my_awesome_project.blog.api.views.router")\n'
    )


def test_a_drf_viewset_is_imported_and_registered_beside_the_users(project):
    router = project / "config" / "api_router.py"
    router.write_text(
        'from my_awesome_project.users.api.views import UserViewSet\n\nrouter.register("users", UserViewSet)\n',
    )

    register(project, PACKAGE, "blog", "Post")

    assert router.read_text() == (
        "from my_awesome_project.blog.api.views import PostViewSet\n"
        "from my_awesome_project.users.api.views import UserViewSet\n\n"
        'router.register("users", UserViewSet)\nrouter.register("posts", PostViewSet)\n'
    )


def test_a_moved_marker_is_an_error(project):
    (project / "config" / "urls.py").write_text("urlpatterns = []\n")

    with pytest.raises(SystemExit, match="0 times, not once"):
        register(project, PACKAGE, "blog", "Post")
