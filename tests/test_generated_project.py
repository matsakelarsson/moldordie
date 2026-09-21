"""Unit tests for the generated-project reader, on hand-written modules and trees."""

import json
import tomllib
from pathlib import Path
from textwrap import dedent

import pytest
import yaml

from tests.generated_project import CONDITIONAL
from tests.generated_project import EXPRESSION
from tests.generated_project import IMPORTED
from tests.generated_project import MUTATED
from tests.generated_project import NO_DEFAULT
from tests.generated_project import REJECTED
from tests.generated_project import UNBOUND
from tests.generated_project import UNSUPPORTED
from tests.generated_project import EnvRead
from tests.generated_project import Expression
from tests.generated_project import GeneratedProject
from tests.generated_project import PythonModule
from tests.generated_project import Unresolvable

PATH = Path("settings.py")


def module(source: str) -> PythonModule:
    """The reader over a hand-written module; the source is dedented and its first line is line 1."""
    return PythonModule(dedent(source).lstrip("\n"), PATH)


def failure(reader: PythonModule, name: str, query: str = "value") -> tuple[str, int | None, str]:
    """The reason, line and detail ``query`` on ``name`` fails with."""
    with pytest.raises(Unresolvable) as excinfo:
        getattr(reader, query)(name)
    error = excinfo.value
    assert (error.name, error.path) == (name, PATH)
    return error.reason, error.lineno, error.detail


# The forms the resolver reads


def test_literals_and_the_names_bound_to_them():
    reader = module("""
        A = 1
        B = "text"
        C = [1, "two", {"three": (3, None)}, {4}, -5, b"six"]
        D = C
        E: dict[str, int] = {"seven": 7}
    """)
    assert reader.literal("A") == 1
    assert reader.literal("B") == "text"
    assert reader.literal("C") == [1, "two", {"three": (3, None)}, {4}, -5, b"six"]
    assert reader.literal("D") == reader.literal("C")
    assert reader.literal("E") == {"seven": 7}


def test_plus_goes_through_the_operator():
    reader = module("""
        A = [1] + [2]
        B = "a" + "b"
        C = (1,) + (2,)
        D = 1 + 2
        E = A + B
    """)
    assert reader.literal("A") == [1, 2]
    assert reader.literal("B") == "ab"
    assert reader.literal("C") == (1, 2)
    assert reader.literal("D") == 1 + 2
    assert reader.value("E") == Expression("A + B")  # a list and a string: the operator refuses


def test_displays_splice_starred_lists_and_tuples_and_double_starred_dicts():
    reader = module("""
        A = [1, 2]
        B = (3,)
        C = {"c": 4}
        D = [0, *A, *B]
        E = (*A, 5)
        F = {*A, 6}
        G = {"g": 0, **C}
    """)
    assert reader.literal("D") == [0, 1, 2, 3]
    assert reader.literal("E") == (1, 2, 5)
    assert reader.literal("F") == {1, 2, 6}
    assert reader.literal("G") == {"g": 0, "c": 4}


def test_every_other_unconditional_binding_is_an_expression():
    reader = module("""
        import os
        A = os.getenv("A")
        B = f"{A}"
        C = os.path
        D = 2 * 3
        E = A if A else None
        F = os
        G = X
        H = (Y := 1)
    """)
    expressions = {
        "A": "os.getenv('A')",
        "B": "f'{A}'",
        "C": "os.path",
        "D": "2 * 3",
        "E": "A if A else None",
        "F": "os",
        "G": "X",
        "H": "(Y := 1)",
    }
    for name, source in expressions.items():
        assert reader.value(name) == Expression(source), name
    assert failure(reader, "A", "literal") == (EXPRESSION, 2, "os.getenv('A')")
    assert failure(reader, "Y") == (UNSUPPORTED, 9, "H = (Y := 1)")


# Identity


def test_augmented_assignment_extends_the_list_every_alias_shares():
    reader = module("""
        A = [1]
        B = A
        C = {"a": A}
        A += [2]
    """)
    assert reader.literal("A") == [1, 2]
    assert reader.literal("B") == [1, 2]
    assert reader.literal("C") == {"a": [1, 2]}


def test_assignment_of_a_sum_rebinds_the_name_alone():
    reader = module("""
        A = [1]
        B = A
        A = A + [2]
    """)
    assert reader.literal("A") == [1, 2]
    assert reader.literal("B") == [1]


def test_a_call_mentioning_a_name_invalidates_every_name_reaching_its_objects():
    reader = module("""
        A = [1]
        B = {"a": A}
        C = (A,)
        D = [1]
        E = A.append(2)
    """)
    for name in ("A", "B", "C"):
        assert failure(reader, name) == (MUTATED, 5, "E = A.append(2)")
    assert reader.literal("D") == [1]
    assert reader.value("E") == Expression("A.append(2)")


def test_an_augmented_assignment_the_reader_cannot_apply_invalidates_the_aliases():
    reader = module("""
        A = [1]
        B = A
        A += f()
        C = "c"
        D = C
        C += f()
    """)
    assert failure(reader, "A") == (UNSUPPORTED, 3, "A += f()")
    assert failure(reader, "B") == (MUTATED, 3, "A += f()")
    assert failure(reader, "C") == (UNSUPPORTED, 6, "C += f()")
    assert reader.literal("D") == "c"


def test_immutables_never_alias():
    reader = module("""
        S = "x"
        A = [S]
        B = [S]
        T = S
        A += ["y"]
        S += "y"
    """)
    assert reader.literal("A") == ["x", "y"]
    assert reader.literal("B") == ["x"]
    assert reader.literal("S") == "xy"
    assert reader.literal("T") == "x"


# Statements


def test_names_bound_inside_compound_statements_are_conditional():
    reader = module("""
        import os
        if os.name:
            A = 1
        else:
            A = 2
        for B in "bc":
            pass
        while (C := os.name):
            break
        try:
            import json as D
        except ImportError as E:
            pass
        with open("f") as F:
            pass
        match os.name:
            case str() as G:
                pass
        A = "restored"
    """)
    assert failure(reader, "B") == (CONDITIONAL, 6, "inside the statement at line 6")
    assert failure(reader, "C") == (CONDITIONAL, 8, "inside the statement at line 8")
    assert failure(reader, "D") == (CONDITIONAL, 11, "inside the statement at line 10")
    assert failure(reader, "E") == (CONDITIONAL, 12, "inside the statement at line 10")
    assert failure(reader, "F") == (CONDITIONAL, 14, "inside the statement at line 14")
    assert failure(reader, "G") == (CONDITIONAL, 17, "inside the statement at line 16")
    assert reader.literal("A") == "restored"


def test_definitions_and_tuple_targets_are_unsupported():
    reader = module("""
        def f():
            pass
        class C:
            pass
        A, B = 1, 2
    """)
    assert failure(reader, "f") == (UNSUPPORTED, 1, "def f():")
    assert failure(reader, "C") == (UNSUPPORTED, 3, "class C:")
    assert failure(reader, "A") == (UNSUPPORTED, 5, "A, B = (1, 2)")
    assert failure(reader, "B") == (UNSUPPORTED, 5, "A, B = (1, 2)")


def test_subscript_and_attribute_assignment_invalidate_the_holders():
    reader = module("""
        A = {"k": [1]}
        B = [A]
        C = [1]
        A["k"] = 2
        C.x = 3
    """)
    assert failure(reader, "A") == (MUTATED, 4, "A['k'] = 2")
    assert failure(reader, "B") == (MUTATED, 4, "A['k'] = 2")
    assert failure(reader, "C") == (MUTATED, 5, "C.x = 3")


def test_del_of_a_name_unbinds_it_and_del_of_an_item_invalidates():
    reader = module("""
        A = [1]
        B = A
        del A
        C = [1]
        D = C
        del C[0]
    """)
    assert failure(reader, "A") == (UNBOUND, None, "")
    assert reader.literal("B") == [1]
    assert failure(reader, "C") == (MUTATED, 6, "del C[0]")
    assert failure(reader, "D") == (MUTATED, 6, "del C[0]")


def test_a_fresh_unconditional_binding_restores_the_name_but_not_its_aliases():
    reader = module("""
        A = [1]
        B = A
        A.append(2)
        A = [3]
        C = f()
        C += 1
        C = "restored"
    """)
    assert reader.literal("A") == [3]
    assert failure(reader, "B") == (MUTATED, 3, "A.append(2)")
    assert reader.literal("C") == "restored"


# Partial structure


def test_partial_displays_keep_their_shape_with_expression_leaves():
    reader = module("""
        import os
        A = [1, os.sep, "b"]
        B = {"a": A, "b": os.name}
        C = (os.sep,)
    """)
    assert reader.value("A") == [1, Expression("os.sep"), "b"]
    assert reader.value("B") == {"a": [1, Expression("os.sep"), "b"], "b": Expression("os.name")}
    assert reader.value("C") == (Expression("os.sep"),)
    assert failure(reader, "B", "literal") == (EXPRESSION, 3, "os.sep")


def test_an_unreadable_key_set_element_or_spliced_operand_makes_the_display_an_expression():
    reader = module("""
        import os
        A = {os.name: 1}
        B = {1, os.name}
        C = [*os.environ]
        D = {**os.environ}
        E = [*A]
        F = {**B}
        G = [1, [2, os.name]]
        H = [*G]
    """)
    assert reader.value("A") == Expression("{os.name: 1}")
    assert reader.value("B") == Expression("{1, os.name}")
    assert reader.value("C") == Expression("[*os.environ]")
    assert reader.value("D") == Expression("{**os.environ}")
    assert reader.value("E") == Expression("[*A]")
    assert reader.value("F") == Expression("{**B}")
    assert reader.value("H") == [1, [2, Expression("os.name")]]


def test_negative_membership_needs_literal():
    """An ``Expression`` leaf could be anything, so ``not in`` over ``value`` proves nothing."""
    reader = module("""
        import os
        A = ["a", os.name]
    """)
    assert "b" not in reader.value("A")
    assert failure(reader, "A", "literal") == (EXPRESSION, 2, "os.name")


def test_values_are_copies():
    reader = module("""
        A = [[1]]
        B = A
    """)
    reader.value("A")[0].append(2)
    assert reader.literal("A") == [[1]]
    assert reader.literal("B") == [[1]]
    assert reader.value("A") is not reader.value("A")


# Rejection


def test_an_alias_made_inside_an_if_rejects_the_module():
    """After the if, B may or may not be A's list, so the append could reach A."""
    reader = module("""
        import os
        A = [1]
        if os.name:
            B = A
        else:
            B = []
        B.append(2)
    """)
    for name in ("A", "B", "os", "C"):
        assert failure(reader, name) == (REJECTED, 3, "line 3 mentions A, bound to a mutable value at line 2")
    assert "B.append(2)" in reader.source


def test_an_augmented_target_inside_an_if_rejects_the_module():
    reader = module("""
        INTERNAL_IPS = ["127.0.0.1"]
        if env("USE_DOCKER") == "yes":
            INTERNAL_IPS += ["10.0.2.2"]
    """)
    expected = (REJECTED, 2, "line 2 mentions INTERNAL_IPS, bound to a mutable value at line 1")
    assert failure(reader, "INTERNAL_IPS") == expected


@pytest.mark.parametrize(
    "statement",
    [
        "def f(x=A):\n    return x",
        "def f():\n    return A",
        "g = lambda: A",
        "D = [a for a in A]",
        "class C:\n    x = A",
    ],
    ids=["default", "body", "lambda", "comprehension", "class"],
)
def test_a_mention_in_a_nested_scope_rejects_the_module(statement):
    reader = module(f"A = []\n{statement}\nB = 1\n")
    assert failure(reader, "A") == (REJECTED, 2, "line 2 mentions A, bound to a mutable value at line 1")
    assert failure(reader, "B") == (REJECTED, 2, "line 2 mentions A, bound to a mutable value at line 1")


def test_a_compound_statement_over_expressions_and_immutables_is_not_rejected():
    reader = module("""
        import os
        X = os.getenv("X")
        Y = "s"
        Z = 1
        if X:
            W = Y + "t"
        for i in range(Z):
            Y.upper()
        V = tuple(c for c in Y)
    """)
    assert reader.literal("Y") == "s"
    assert reader.literal("Z") == 1
    assert failure(reader, "W") == (CONDITIONAL, 6, "inside the statement at line 5")
    assert reader.value("V") == Expression("tuple((c for c in Y))")


def test_rejection_covers_names_bound_before_and_after_the_trigger():
    reader = module("""
        A = [1]
        B = 2
        if B:
            A.append(3)
        C = 4
    """)
    for name in ("A", "B", "C"):
        assert failure(reader, name) == (REJECTED, 3, "line 3 mentions A, bound to a mutable value at line 1")


def test_names_declared_global_or_bound_by_a_comprehension_walrus_stay_unsupported():
    reader = module("""
        A = 1
        def f():
            global A
            A = 2
        B = [(C := n) for n in range(3)]
        C = 5
        A = 3
    """)
    assert failure(reader, "A") == (UNSUPPORTED, 3, "declared global at line 3")
    assert failure(reader, "C") == (UNSUPPORTED, 5, "bound by a walrus in a comprehension at line 5")
    assert reader.value("B") == Expression("[(C := n) for n in range(3)]")


# env_reads


def test_env_reads_list_every_literal_name_read_through_env_in_source_order():
    reader = module("""
        import environ
        env = environ.Env()
        env.read_env("/app/.env")
        A = env("A", default="a")
        B = env.bool("B", False)
        if env.int("C", default=3):
            D = env.str("D")
        E = [env("A"), env.list("E", str, default=["e"])]
        F = env(var="F", default=None)
        G = env.db()
        H = env.db("H", default={})
        J = env.float("J", 0.5)
        K = env("K", str, "k")
        L = env("L", default=DEFAULT)
        M = env(name)
        N = env.dict("N", default={"n": "1"})
    """)
    assert reader.env_reads() == [
        EnvRead("A", None, "a", 4),
        EnvRead("B", "bool", default=False, lineno=5),
        EnvRead("C", "int", 3, 6),
        EnvRead("D", "str", NO_DEFAULT, 7),
        EnvRead("A", None, NO_DEFAULT, 8),
        EnvRead("E", "list", ["e"], 8),
        EnvRead("F", None, None, 9),
        EnvRead("DATABASE_URL", "db", NO_DEFAULT, 10),
        EnvRead("H", "db", {}, 11),
        EnvRead("J", "float", 0.5, 12),
        EnvRead("K", None, "k", 13),
        EnvRead("L", None, Expression("DEFAULT"), 14),
        EnvRead("N", "dict", {"n": "1"}, 16),
    ]


def test_env_reads_reject_a_method_the_reader_does_not_know():
    reader = module('A = env.url("A")\n')
    with pytest.raises(ValueError, match=r"^settings.py:1: env.url is not a read the reader knows$"):
        reader.env_reads()


def test_env_reads_work_on_a_rejected_module():
    reader = module("""
        A = []
        if env.bool("B", default=True):
            A.append(1)
    """)
    assert failure(reader, "A")[0] == REJECTED
    assert reader.env_reads() == [EnvRead("B", "bool", default=True, lineno=2)]


# Errors


def test_unresolvable_carries_the_name_reason_path_and_line():
    reader = module("""
        import os
        A = [1]
        B = A
        x = A.pop()
    """)
    with pytest.raises(Unresolvable) as excinfo:
        reader.value("C")
    error = excinfo.value
    assert (error.name, error.reason, error.path, error.lineno, error.detail) == ("C", UNBOUND, PATH, None, "")
    assert str(error) == "C is not bound in settings.py"
    with pytest.raises(Unresolvable, match=r"^os is imported in settings.py:1$"):
        reader.value("os")
    assert failure(reader, "os") == (IMPORTED, 1, "")
    # The alias error points at the mutation
    assert failure(reader, "B") == (MUTATED, 4, "x = A.pop()")
    with pytest.raises(Unresolvable, match=r"^B may be mutated in settings.py:4 \(x = A.pop\(\)\)$"):
        reader.literal("B")


def test_a_rejected_module_says_so_for_every_name():
    reader = module("""
        A = []
        for a in A:
            pass
    """)
    with pytest.raises(
        Unresolvable,
        match=r"^B is unreadable: settings.py is rejected \(line 2 mentions A, bound to a mutable value at line 1\)$",
    ):
        reader.value("B")


# GeneratedProject


@pytest.fixture
def project(tmp_path):
    """A hand-written tree in the shape of a generated project, with a file of each kind the reader parses."""
    root = tmp_path / "my_project"
    files = {
        "pyproject.toml": (
            "[project]\n"
            'dependencies = [\n  "django==6.0.2",\n  "uvicorn[standard]==0.40.0",\n]\n'
            "[dependency-groups]\n"
            'dev = ["ruff==0.16.6"]\n'
        ),
        ".envs/.local/.django": "# Django\nDJANGO_DEBUG=True\n\nEMPTY=\n",
        ".env.example": "# Deployment\nDJANGO_SECRET_KEY=\nWEB_CONCURRENCY=4\n",
        ".envs/.production/.postgres": "export POSTGRES_USER=debug\n",
        "docker-compose.local.yml": "services:\n  django:\n    image: django\n",
        "my_project/templates/base.html": "<!doctype html>\n",
        "my_project/__init__.py": '__version__ = "0.1.0"\n',
        "config/settings/base.py": "DEBUG = False\n",
        "data.json": '{"key": [1]}\n',
        "broken.yml": "key: [\n",
        ".venv/lib/site.py": "",
        "config/__pycache__/base.pyc": "",
    }
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    return GeneratedProject(root)


def test_package_is_the_name_of_the_root_directory(project):
    assert project.package == "my_project"
    assert project.root.name == "my_project"


def test_files_are_sorted_relative_paths_without_the_venv_and_caches(project):
    expected = [
        ".env.example",
        ".envs/.local/.django",
        ".envs/.production/.postgres",
        "broken.yml",
        "config/settings/base.py",
        "data.json",
        "docker-compose.local.yml",
        "my_project/__init__.py",
        "my_project/templates/base.html",
        "pyproject.toml",
    ]
    assert project.files() == [Path(relative) for relative in expected]


def test_text_bytes_and_the_parsers_read_root_relative_paths(project):
    assert project.text("config/settings/base.py") == "DEBUG = False\n"
    assert project.bytes(Path("config/settings/base.py")) == b"DEBUG = False\n"
    assert project.json("data.json") == {"key": [1]}
    assert project.yaml("docker-compose.local.yml") == {"services": {"django": {"image": "django"}}}
    assert project.toml("pyproject.toml")["project"]["dependencies"] == ["django==6.0.2", "uvicorn[standard]==0.40.0"]
    assert project.pyproject == project.toml("pyproject.toml")


def test_parser_errors_propagate(project):
    with pytest.raises(yaml.YAMLError):
        project.yaml("broken.yml")
    with pytest.raises(json.JSONDecodeError):
        project.json("broken.yml")
    with pytest.raises(tomllib.TOMLDecodeError):
        project.toml("broken.yml")
    with pytest.raises(SyntaxError):
        project.module("broken.yml")
    with pytest.raises(FileNotFoundError):
        project.text("missing.txt")


def test_dotenv_reads_an_env_file_by_path(project):
    """``.env.example`` is not under ``.envs``, so it is read by path rather than by environment."""
    assert project.dotenv(".env.example") == {"DJANGO_SECRET_KEY": "", "WEB_CONCURRENCY": "4"}
    assert project.dotenv(Path(".envs/.local/.django")) == project.env("local", "django")


def test_env_reads_the_name_value_lines_and_rejects_any_other(project):
    assert project.env("local", "django") == {"DJANGO_DEBUG": "True", "EMPTY": ""}
    with pytest.raises(
        ValueError,
        match=r"^\.envs/\.production/\.postgres:1 is not a NAME=value line: 'export POSTGRES_USER=debug'$",
    ):
        project.env("production", "postgres")


def test_pins_are_requirements_by_array_in_file_order(project):
    pins = project.pins
    assert list(pins) == ["dependencies", "dev"]
    dependencies = [(pin.name, str(pin.specifier), pin.extras) for pin in pins["dependencies"]]
    assert dependencies == [("django", "==6.0.2", set()), ("uvicorn", "==0.40.0", {"standard"})]
    assert [str(pin) for pin in pins["dev"]] == ["ruff==0.16.6"]


def test_compose_template_module_and_settings_locate_their_files(project):
    assert project.compose("local") == project.yaml("docker-compose.local.yml")
    assert project.template("base.html") == "<!doctype html>\n"
    assert project.module("my_project/__init__.py").literal("__version__") == "0.1.0"
    settings = project.settings("base")
    assert settings.literal("DEBUG") is False
    assert settings.path == Path("config/settings/base.py")
    assert settings.source == "DEBUG = False\n"
