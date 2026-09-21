"""A reader of a generated project for the tests: where its files are and what they hold.

``GeneratedProject`` locates the files under a generated root and parses the ones that have
a syntax; ``PythonModule`` reads what a Python file binds at module scope from its source
alone, without importing it. Expected behaviour belongs to the tests: nothing here asserts,
checks that a file exists or validates the tree.

The Python reader resolves an intentionally small subset of the language and fails
explicitly outside it. It makes no general claim to evaluate Python: anything dynamic (a
call, an attribute, a subscript) is outside. Each file is read on its own, so a name it
imports, ``from .base import *`` included, is "imported" and never followed. A module-scope
name is readable when its last unconditional binding takes one of these forms:

- a literal, anything ``ast.literal_eval`` accepts;
- a name bound to a value, which shares that value's list, dict and set objects;
- ``+`` of two values, through Python's own operator;
- a list, tuple, set or dict display, with starred lists or tuples and ``**`` dicts.

An element of a list or tuple display, or the value of a dict entry, that is none of these
becomes an ``Expression`` leaf holding its source, so the display keeps its length and keys
as partial structure: ``value`` returns it and ``literal`` refuses it. An unreadable dict
key, set element, starred or ``**`` operand makes the whole display an ``Expression``, and so
is every other unconditional binding. ``value`` and ``literal`` return deep copies.

Values keep identity the way Python does: ``B = A`` shares A's objects, ``A += [...]``
extends the shared list, ``A = A + [...]`` rebinds A alone. Anything else that could change
an object marks every name reaching it "mutated": a subscript or attribute assignment,
``del`` of either, an augmented assignment the reader cannot apply and any call at module
scope that mentions a value-bound name. ``del A`` unbinds A. A name bound inside a compound
statement (``if``, ``for``, ``while``, ``try``, ``with``, ``match``, a walrus in their tests
included) is "conditional"; a ``def``, ``class``, tuple target or augmented assignment the
reader cannot apply binds its name "unsupported". A later unconditional binding restores a
conditional, mutated or unsupported name. A name listed by ``global`` anywhere, or bound by
a walrus inside a comprehension, stays unsupported whatever binds it: a call could rebind
it later. Nothing inside a def, lambda, class or comprehension binds a module name.

A module is rejected as a whole when a name mentioned inside a compound statement or a
nested scope (header and defaults included; loads and augmented targets) is ever bound to
a value that reaches a list, dict or set: the statement could alias or mutate the object on
a path the reader does not follow. Every ``value`` and ``literal`` query then raises with
the concealing statement's line and the binding that tripped it; ``source`` and
``env_reads`` stay available.

``env_reads`` is syntactic and independent of the resolver: every read of a literal
variable name through ``env`` in the module, in source order, with the default the call
gives.
"""

import ast
import copy
import json
import operator
import re
import tomllib
from collections.abc import Iterable
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import yaml
from packaging.requirements import Requirement

# The reasons a name cannot be read, ``Unresolvable.reason``
UNBOUND = "unbound"
IMPORTED = "imported"
CONDITIONAL = "conditional"
MUTATED = "mutated"
UNSUPPORTED = "unsupported"
REJECTED = "rejected"
EXPRESSION = "expression"
PHRASES = {
    UNBOUND: "is not bound",
    IMPORTED: "is imported",
    CONDITIONAL: "is bound conditionally",
    MUTATED: "may be mutated",
    UNSUPPORTED: "is bound by an unsupported statement",
    EXPRESSION: "is not a literal",
}

SKIPPED_DIRECTORIES = {".venv", "__pycache__"}
ENV_LINE = re.compile(r"([A-Za-z_]\w*)=(.*)")

COMPOUND_STATEMENTS = (
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.Try,
    ast.TryStar,
    ast.With,
    ast.AsyncWith,
    ast.Match,
)
DEFINITIONS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
COMPREHENSIONS = (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
SCOPES = (*DEFINITIONS, ast.Lambda, *COMPREHENSIONS)
MUTABLE = (list, dict, set)

# The ``env`` reads the reader knows, by method (None for ``env()`` itself), with the position
# of the default among the positional arguments: ``env(var, cast, default)``, ``env.list`` and
# ``env.dict`` take a cast before it, the typed reads and ``db`` take it second.
ENV_DEFAULT_POSITION = {
    None: 2,
    "list": 2,
    "dict": 2,
    "str": 1,
    "bool": 1,
    "int": 1,
    "float": 1,
    "db": 1,
}
DATABASE_VAR = "DATABASE_URL"
"""The variable ``env.db()`` reads when its argument is omitted."""


@dataclass(frozen=True)
class Expression:
    """Source the reader does not evaluate, standing where its value would be."""

    source: str


class _NoDefault:
    """The default of an ``env`` read that gives none: one instance, which copying keeps."""

    def __repr__(self) -> str:
        return "NO_DEFAULT"

    def __copy__(self) -> "_NoDefault":
        return self

    def __deepcopy__(self, memo: dict) -> "_NoDefault":
        return self


NO_DEFAULT = _NoDefault()


@dataclass(frozen=True)
class EnvRead:
    """One read through ``env``: the variable, the method (None for ``env()`` itself), the default and the line."""

    name: str
    method: str | None
    default: object
    lineno: int


class Unresolvable(LookupError):  # noqa: N818 - an adjective, as the design names it: "SECRET_KEY is unresolvable"
    """``name`` cannot be read from ``path``.

    ``reason`` is one of the module's reason constants, ``lineno`` the statement responsible
    (None for an unbound name) and ``detail`` what the reason needs to name: the statement,
    the tripping binding of a rejected module, the first expression of a partial value.
    """

    def __init__(self, name: str, reason: str, path: Path, lineno: int | None, detail: str = "") -> None:
        super().__init__(name, reason, path, lineno, detail)
        self.name = name
        self.reason = reason
        self.path = path
        self.lineno = lineno
        self.detail = detail

    def __str__(self) -> str:
        detail = f" ({self.detail})" if self.detail else ""
        if self.reason == REJECTED:
            return f"{self.name} is unreadable: {self.path} is rejected{detail}"
        where = f"{self.path}:{self.lineno}" if self.lineno is not None else str(self.path)
        return f"{self.name} {PHRASES[self.reason]} in {where}{detail}"


@dataclass
class _Binding:
    """What a module-scope name is bound to at a point of the walk: a value when ``reason`` is None."""

    reason: str | None
    obj: object
    lineno: int | None
    detail: str = ""


def _first_line(node: ast.AST) -> str:
    return ast.unparse(node).splitlines()[0]


def _own_nodes(node: ast.AST) -> Iterator[ast.AST]:
    """``node`` and its descendants in the same scope: a nested scope is yielded but not entered."""
    yield node
    if not isinstance(node, SCOPES):
        for child in ast.iter_child_nodes(node):
            yield from _own_nodes(child)


def _loaded_names(node: ast.AST) -> set[str]:
    return {sub.id for sub in _own_nodes(node) if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load)}


def _stored_names(target: ast.AST) -> list[str]:
    return [sub.id for sub in ast.walk(target) if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Store)]


def _mutables_in(obj: object, seen: set[int] | None = None) -> Iterator[object]:
    """The list, dict and set objects ``obj`` is or holds, through lists, tuples and dict values."""
    if seen is None:
        seen = set()
    if isinstance(obj, MUTABLE):
        if id(obj) in seen:
            return
        seen.add(id(obj))
        yield obj
    if isinstance(obj, list | tuple):
        for item in obj:
            yield from _mutables_in(item, seen)
    elif isinstance(obj, dict):
        for item in obj.values():
            yield from _mutables_in(item, seen)


def _reaches_mutable(obj: object) -> bool:
    return any(True for _ in _mutables_in(obj))


def _first_expression(obj: object, seen: set[int] | None = None) -> Expression | None:
    """The first ``Expression`` in ``obj``, in traversal order, or None for a literal."""
    if isinstance(obj, Expression):
        return obj
    if seen is None:
        seen = set()
    if id(obj) in seen:
        return None
    seen.add(id(obj))
    if isinstance(obj, dict):
        items: Iterable[object] = [*obj, *obj.values()]
    elif isinstance(obj, list | tuple | set | frozenset):
        items = obj
    else:
        return None
    for item in items:
        found = _first_expression(item, seen)
        if found is not None:
            return found
    return None


def _literal_or_expression(node: ast.expr) -> object:
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError):
        return Expression(ast.unparse(node))


def _mentions(body: list[ast.stmt]) -> dict[str, int]:
    """The names loaded or augmented inside a compound statement or nested scope, with the line of the first."""
    found: dict[str, int] = {}

    def note(node: ast.AST, lineno: int) -> None:
        for sub in ast.walk(node):
            if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load):
                found.setdefault(sub.id, lineno)
            elif isinstance(sub, ast.AugAssign) and isinstance(sub.target, ast.Name):
                found.setdefault(sub.target.id, lineno)

    for statement in body:
        if isinstance(statement, (*COMPOUND_STATEMENTS, *DEFINITIONS)):
            note(statement, statement.lineno)
        else:
            for node in _own_nodes(statement):
                if isinstance(node, SCOPES):
                    note(node, statement.lineno)
    return found


def _permanent(tree: ast.Module) -> dict[str, tuple[int, str]]:
    """The names a ``global`` lists or a walrus in a module-scope comprehension binds, with line and reason."""
    found: dict[str, tuple[int, str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Global):
            for name in node.names:
                found.setdefault(name, (node.lineno, f"declared global at line {node.lineno}"))

    def visit(node: ast.AST, *, in_comprehension: bool) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (*DEFINITIONS, ast.Lambda)):
                continue
            if in_comprehension and isinstance(child, ast.NamedExpr):
                found.setdefault(
                    child.target.id,
                    (child.lineno, f"bound by a walrus in a comprehension at line {child.lineno}"),
                )
            visit(child, in_comprehension=in_comprehension or isinstance(child, COMPREHENSIONS))

    visit(tree, in_comprehension=False)
    return found


class PythonModule:
    """What a Python file binds at module scope, read from its source; the subset is in the module docstring."""

    def __init__(self, source: str, path: Path) -> None:
        self.source = source
        self.path = path
        self._tree = ast.parse(source, filename=str(path))
        self._bindings: dict[str, _Binding] = {}
        self._permanent = _permanent(self._tree)
        self._mentions = _mentions(self._tree.body)
        self._rejection: tuple[int, str] | None = None
        self._walk()

    def value(self, name: str) -> object:
        """A deep copy of what ``name`` is bound to, ``Expression`` leaves included."""
        return copy.deepcopy(self._binding(name).obj)

    def literal(self, name: str) -> object:
        """``value(name)`` when nothing in it is an ``Expression``; the first one is the error's detail."""
        binding = self._binding(name)
        expression = _first_expression(binding.obj)
        if expression is not None:
            raise Unresolvable(name, EXPRESSION, self.path, binding.lineno, expression.source)
        return copy.deepcopy(binding.obj)

    def env_reads(self) -> list[EnvRead]:
        """Every read of a literal variable name through ``env``, in source order, on a rejected module too."""
        calls = (node for node in ast.walk(self._tree) if isinstance(node, ast.Call))
        reads = (self._env_read(call) for call in sorted(calls, key=lambda call: (call.lineno, call.col_offset)))
        return [read for read in reads if read is not None]

    def _binding(self, name: str) -> _Binding:
        if self._rejection is not None:
            lineno, detail = self._rejection
            raise Unresolvable(name, REJECTED, self.path, lineno, detail)
        if name in self._permanent:
            lineno, detail = self._permanent[name]
            raise Unresolvable(name, UNSUPPORTED, self.path, lineno, detail)
        binding = self._bindings.get(name)
        if binding is None:
            raise Unresolvable(name, UNBOUND, self.path, None)
        if binding.reason is not None:
            raise Unresolvable(name, binding.reason, self.path, binding.lineno, binding.detail)
        return binding

    def _env_read(self, call: ast.Call) -> EnvRead | None:
        match call.func:
            case ast.Name(id="env"):
                method = None
            case ast.Attribute(value=ast.Name(id="env"), attr=method):
                pass
            case _:
                return None
        if method == "read_env":
            return None
        if method not in ENV_DEFAULT_POSITION:
            message = f"{self.path}:{call.lineno}: env.{method} is not a read the reader knows"
            raise ValueError(message)
        positional = dict(enumerate(call.args))
        keywords = {keyword.arg: keyword.value for keyword in call.keywords}
        var = positional.get(0, keywords.get("var"))
        if var is None and method == "db":
            name = DATABASE_VAR
        elif isinstance(var, ast.Constant) and isinstance(var.value, str):
            name = var.value
        else:
            return None
        default = positional.get(ENV_DEFAULT_POSITION[method], keywords.get("default"))
        return EnvRead(name, method, NO_DEFAULT if default is None else _literal_or_expression(default), call.lineno)

    # The walk: one pass over the module's statements, binding names as it goes.

    def _walk(self) -> None:
        for statement in self._tree.body:
            if isinstance(statement, COMPOUND_STATEMENTS):
                self._bind_conditionally(statement)
            elif isinstance(statement, DEFINITIONS):
                self._bind(statement.name, _Binding(UNSUPPORTED, None, statement.lineno, _first_line(statement)))
            elif isinstance(statement, ast.Import | ast.ImportFrom):
                self._import(statement)
            else:
                self._simple(statement)
            if self._rejection is not None:
                return

    def _bind(self, name: str, binding: _Binding) -> None:
        self._bindings[name] = binding
        if binding.reason is None and name in self._mentions and _reaches_mutable(binding.obj):
            concealing = self._mentions[name]
            self._rejection = (
                concealing,
                f"line {concealing} mentions {name}, bound to a mutable value at line {binding.lineno}",
            )

    def _bind_conditionally(self, statement: ast.stmt) -> None:
        """Every name the compound ``statement`` binds in the module's scope is conditional."""
        for node in _own_nodes(statement):
            match node:
                case ast.Name(id=name, ctx=ast.Store() | ast.Del()):
                    names = [name]
                case ast.ExceptHandler(name=str() as name):
                    names = [name]
                case ast.Import() | ast.ImportFrom():
                    names = [alias.asname or alias.name.partition(".")[0] for alias in node.names if alias.name != "*"]
                case ast.FunctionDef() | ast.AsyncFunctionDef() | ast.ClassDef():
                    names = [node.name]
                case (
                    ast.MatchAs(name=str() as name)
                    | ast.MatchStar(name=str() as name)
                    | ast.MatchMapping(rest=str() as name)
                ):
                    names = [name]
                case _:
                    continue
            for name in names:
                self._bind(
                    name,
                    _Binding(CONDITIONAL, None, node.lineno, f"inside the statement at line {statement.lineno}"),
                )

    def _import(self, statement: ast.Import | ast.ImportFrom) -> None:
        for alias in statement.names:
            if alias.name != "*":
                self._bind(alias.asname or alias.name.partition(".")[0], _Binding(IMPORTED, None, statement.lineno))

    def _simple(self, statement: ast.stmt) -> None:
        mentioned = {
            name for node in _own_nodes(statement) if isinstance(node, ast.Call) for name in _loaded_names(node)
        }
        self._mutate(mentioned, statement)
        for node in _own_nodes(statement):
            if isinstance(node, ast.NamedExpr):
                self._bind(node.target.id, _Binding(UNSUPPORTED, None, statement.lineno, _first_line(statement)))
        match statement:
            case ast.Assign(targets=targets, value=value):
                self._assign(targets, value, statement)
            case ast.AnnAssign(target=target, value=ast.expr() as value):
                self._assign([target], value, statement)
            case ast.AugAssign():
                self._augment(statement)
            case ast.Delete(targets=targets):
                self._delete(targets, statement)

    def _mutate(self, names: set[str], statement: ast.stmt) -> None:
        """Every name reaching a mutable object one of ``names`` reaches may be changed by ``statement``."""
        values = [binding.obj for name in names if (binding := self._bindings.get(name)) and binding.reason is None]
        affected = {id(obj) for value in values for obj in _mutables_in(value)}
        if not affected:
            return
        for name, binding in list(self._bindings.items()):
            if binding.reason is None and any(id(obj) in affected for obj in _mutables_in(binding.obj)):
                self._bindings[name] = _Binding(MUTATED, None, statement.lineno, _first_line(statement))

    def _assign(self, targets: list[ast.expr], value_node: ast.expr, statement: ast.stmt) -> None:
        value = self._resolve(value_node)
        for target in targets:
            match target:
                case ast.Name(id=name):
                    self._bind(name, _Binding(None, value, statement.lineno))
                case ast.Subscript() | ast.Attribute():
                    self._mutate(_loaded_names(target), statement)
                case _:
                    for name in _stored_names(target):
                        self._bind(name, _Binding(UNSUPPORTED, None, statement.lineno, _first_line(statement)))

    def _augment(self, statement: ast.AugAssign) -> None:
        target = statement.target
        if not isinstance(target, ast.Name):
            self._mutate(_loaded_names(target), statement)
            return
        binding = self._bindings.get(target.id)
        operand = self._resolve(statement.value)
        if binding is not None and binding.reason is None:
            if (
                isinstance(statement.op, ast.Add)
                and not isinstance(binding.obj, Expression)
                and not isinstance(operand, Expression)
            ):
                try:
                    result = operator.iadd(binding.obj, operand)
                except TypeError:
                    pass
                else:
                    self._bind(target.id, _Binding(None, result, statement.lineno))
                    return
            if isinstance(binding.obj, MUTABLE):
                self._mutate({target.id}, statement)
        self._bind(target.id, _Binding(UNSUPPORTED, None, statement.lineno, _first_line(statement)))

    def _delete(self, targets: list[ast.expr], statement: ast.stmt) -> None:
        for target in targets:
            match target:
                case ast.Name(id=name):
                    self._bindings.pop(name, None)
                case ast.Tuple(elts=elts) | ast.List(elts=elts):
                    self._delete(elts, statement)
                case _:
                    self._mutate(_loaded_names(target), statement)

    # Resolution of an expression to a value, or to an ``Expression`` of its source.

    def _resolve(self, node: ast.expr) -> object:
        try:
            return ast.literal_eval(node)
        except (ValueError, TypeError):
            pass
        match node:
            case ast.Name(id=name, ctx=ast.Load()):
                resolved = self._bound_value(name)
            case ast.BinOp(left=left, op=ast.Add(), right=right):
                resolved = self._sum(left, right)
            case ast.List() | ast.Tuple() | ast.Set():
                resolved = self._display(node)
            case ast.Dict():
                resolved = self._entries(node)
            case _:
                resolved = None
        return Expression(ast.unparse(node)) if resolved is None else resolved

    def _bound_value(self, name: str) -> object | None:
        binding = self._bindings.get(name)
        if binding is not None and binding.reason is None and name not in self._permanent:
            return binding.obj
        return None

    def _sum(self, left: ast.expr, right: ast.expr) -> object | None:
        operands = (self._resolve(left), self._resolve(right))
        if any(isinstance(operand, Expression) for operand in operands):
            return None
        try:
            return operator.add(*operands)
        except TypeError:
            return None

    def _display(self, node: ast.List | ast.Tuple | ast.Set) -> list | tuple | set | None:
        """The display's elements, starred lists and tuples spliced; None when it cannot be built."""
        elements = []
        for element in node.elts:
            if isinstance(element, ast.Starred):
                spliced = self._resolve(element.value)
                if not isinstance(spliced, list | tuple):
                    return None
                elements.extend(spliced)
            else:
                elements.append(self._resolve(element))
        if isinstance(node, ast.List):
            return elements
        if isinstance(node, ast.Tuple):
            return tuple(elements)
        if any(_first_expression(element) is not None for element in elements):
            return None
        try:
            return set(elements)
        except TypeError:
            return None

    def _entries(self, node: ast.Dict) -> dict | None:
        """The dict display's entries, ``**`` dicts spliced; None when a key or operand cannot be read."""
        entries = {}
        for key, value in zip(node.keys, node.values, strict=True):
            if key is None:
                spliced = self._resolve(value)
                if not isinstance(spliced, dict):
                    return None
                entries.update(spliced)
                continue
            resolved = self._resolve(key)
            if _first_expression(resolved) is not None:
                return None
            try:
                hash(resolved)
            except TypeError:
                return None
            entries[resolved] = self._resolve(value)
        return entries


class GeneratedProject:
    """A generated project at ``root``, whose directory keeps the generated slug: its name is the package."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.package = self.root.name

    def files(self) -> list[Path]:
        """Every file under the root, relative to it and sorted; ``.venv`` and ``__pycache__`` are skipped."""
        found = []
        for directory, subdirectories, names in self.root.walk():
            subdirectories[:] = [name for name in subdirectories if name not in SKIPPED_DIRECTORIES]
            found.extend((directory / name).relative_to(self.root) for name in names)
        return sorted(found)

    def text(self, relative: str | Path) -> str:
        return (self.root / relative).read_text()

    def bytes(self, relative: str | Path) -> bytes:
        return (self.root / relative).read_bytes()

    def json(self, relative: str | Path) -> object:
        return json.loads(self.text(relative))

    def toml(self, relative: str | Path) -> dict:
        return tomllib.loads(self.text(relative))

    def yaml(self, relative: str | Path) -> object:
        return yaml.safe_load(self.text(relative))

    def dotenv(self, relative: str | Path) -> dict[str, str]:
        """The ``NAME=value`` lines of the env file at ``relative``.

        A line that is neither that, blank nor a comment raises.
        """
        values = {}
        for number, line in enumerate(self.text(relative).splitlines(), start=1):
            if not line or line.startswith("#"):
                continue
            match = ENV_LINE.fullmatch(line)
            if match is None:
                message = f"{relative}:{number} is not a NAME=value line: {line!r}"
                raise ValueError(message)
            values[match[1]] = match[2]
        return values

    def env(self, environment: str, service: str) -> dict[str, str]:
        """The ``NAME=value`` lines of ``.envs/.<environment>/.<service>``."""
        return self.dotenv(f".envs/.{environment}/.{service}")

    def compose(self, name: str) -> object:
        """The parsed ``docker-compose.<name>.yml``."""
        return self.yaml(f"docker-compose.{name}.yml")

    def template(self, name: str) -> str:
        """The source of the template at ``name`` under the package's templates directory."""
        return self.text(f"{self.package}/templates/{name}")

    @property
    def pyproject(self) -> dict:
        return self.toml("pyproject.toml")

    @property
    def pins(self) -> dict[str, list[Requirement]]:
        """The requirements of each array of ``pyproject.toml``: ``dependencies``, then the dependency groups."""
        data = self.pyproject
        arrays = {"dependencies": data["project"]["dependencies"], **data.get("dependency-groups", {})}
        return {name: [Requirement(entry) for entry in entries] for name, entries in arrays.items()}

    def module(self, relative: str | Path) -> PythonModule:
        return PythonModule(self.text(relative), Path(relative))

    def settings(self, environment: str) -> PythonModule:
        """The settings module of ``environment``: base, local, test or production."""
        return self.module(f"config/settings/{environment}.py")
