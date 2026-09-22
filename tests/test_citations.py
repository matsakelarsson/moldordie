"""The citation check on hand-written files, removed paths and allowances.

``tests/citations.py`` decides what counts as a generated file citing a path its answers
removed; the generation tests apply it to every supported combination.
"""

from tests.citations import Allowance
from tests.citations import Citation
from tests.citations import citations

PACKAGE = "my_project"


def found(files, removed, allowed=()):
    """The citations alone, for the tests that are not about allowances."""
    cited, _ = citations(files, removed, allowed, package=PACKAGE)
    return cited


def test_a_file_that_names_a_removed_file_cites_it():
    files = {"README.md": "Start everything with docker-compose.local.yml.\n", "justfile": "up:\n"}

    assert found(files, ["docker-compose.local.yml"]) == [Citation("README.md", "docker-compose.local.yml")]


def test_a_file_is_cited_once_however_often_it_is_named():
    files = {"README.md": "docker-compose.local.yml, and again docker-compose.local.yml\n"}

    assert found(files, ["docker-compose.local.yml"]) == [Citation("README.md", "docker-compose.local.yml")]


def test_a_file_is_matched_by_its_whole_name():
    """Bounded by what cannot continue a path: another file, or the same one somewhere else, is no citation."""
    removed = ["config/api.py"]

    def cites(text):
        return found({"docs/howto.rst": text}, removed) != []

    assert cites("Routes live in config/api.py.")  # the full stop ends the sentence, not the name
    assert cites("``config/api.py``")
    assert cites("COPY ./config/api.py /app/config/api.py")
    assert not cites("config/api.pyc")
    assert not cites("config/api.py.bak")
    assert not cites("config/api.py/")
    assert not cites("reconfig/api.py")
    assert not cites("my-config/api.py")


def test_a_directory_is_matched_with_its_slash_because_its_bare_name_may_be_prose():
    removed = ["compose/", "utility/"]

    def cited(text):
        return [citation.path for citation in found({"README.md": text}, removed)]

    assert cited("Run docker compose up, a utility you have.") == []
    assert cited("The images are built from compose/production/django/Dockerfile.") == ["compose/"]
    assert cited("See the scripts in ``utility/``.") == ["utility/"]
    assert cited("docker-compose/ is not the directory") == []


def test_a_path_in_the_project_package_is_also_tried_relative_to_it():
    """Files inside the package name their neighbours without it, and so do the docs."""
    removed = [f"{PACKAGE}/sentry/", f"{PACKAGE}/metrics.py", "config/gunicorn.py"]
    files = {
        f"{PACKAGE}/conftest.py": "# the SDK is initialised in sentry/apps.py\n",
        "docs/observability.rst": "The guard lives in ``metrics.py``; Gunicorn reads gunicorn.py.\n",
    }

    assert found(files, removed) == [
        Citation(f"{PACKAGE}/conftest.py", f"{PACKAGE}/sentry/"),
        Citation("docs/observability.rst", f"{PACKAGE}/metrics.py"),
    ]


def test_an_allowed_citation_is_not_reported_and_an_allowance_that_covers_none_is():
    files = {".dockerignore": ".gitlab-ci.yml\n.github/\n", "README.md": "CI runs from .gitlab-ci.yml\n"}
    listing = Allowance(".dockerignore", ".gitlab-ci.yml", "an ignore file may name a file the project lacks")
    unused = Allowance(".dockerignore", "justfile", "the same")

    cited, uncalled = citations(files, [".gitlab-ci.yml"], [listing, unused], package=PACKAGE)

    assert cited == [Citation("README.md", ".gitlab-ci.yml")]
    assert uncalled == [unused]


def test_a_directory_below_the_root_is_also_cited_without_its_slash():
    """Only a bare top-level name can be prose; ``compose/production/nginx`` is a path however it ends."""
    removed = ["compose/production/nginx/", f"{PACKAGE}/users/api/"]
    files = {
        "docs/deploy.rst": "The media server is built from compose/production/nginx and nothing else.\n",
        f"{PACKAGE}/urls.py": "# routes live in users/api, see there\n",
    }

    assert found(files, removed) == [
        Citation("docs/deploy.rst", "compose/production/nginx/"),
        Citation(f"{PACKAGE}/urls.py", f"{PACKAGE}/users/api/"),
    ]


def test_a_segment_of_a_web_address_is_no_citation():
    """A link to docs.docker.com/compose/ names nothing in the project."""
    files = {"README.md": "Read https://docs.docker.com/compose/ and https://developers.google.com/identity/gsi\n"}

    assert found(files, ["compose/", f"{PACKAGE}/identity/"]) == []


def test_a_path_inside_an_image_is_a_citation():
    """``/app/config/api.py`` is the same file as ``config/api.py`` once the image is built."""
    files = {"compose/production/django/start": "python /app/config/api.py\n"}

    assert found(files, ["config/api.py"]) == [Citation("compose/production/django/start", "config/api.py")]
