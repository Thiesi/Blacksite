"""Find every place the server writes player or identity state (S48c1b).

Used by test_s48c1b_write_guards. It reads the server source with ``ast``
and returns one key per writer: ``path::qualified.function::kind``.

Kinds:
- ``queue:<action>``: a Characters.queue call (write guard 1 for save and
  delete);
- ``settle``: a Commerce.settle proposal (write guard 2);
- ``outbox``: a direct write to a commerce or character outbox, or to its
  last effect;
- ``identities``: a write into the live identity store;
- ``identity()``: a call to the live identity accessor, whose result is
  the stored dict itself;
- ``clone_debt``: a direct clone-debt write.
"""

from __future__ import annotations

import ast
from pathlib import Path

SERVER = Path(__file__).resolve().parents[2] / "src" / "karst41" / "server"
MUTATORS = {"append", "clear", "extend", "pop", "popitem", "setdefault", "update", "remove", "discard", "add"}
IDENTITY_OWNERS = {"self", "self.game", "game", "manager", "characters", "self.characters", "self.owner.game",
                   "owner.game", "self.core.characters"}


def _root(node: ast.AST) -> ast.AST:
    """The expression under any chain of subscripts and mutator calls."""
    while True:
        if isinstance(node, ast.Subscript):
            node = node.value
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
              and node.func.attr in ("setdefault", "get")):
            node = node.func.value
        else:
            return node


def _is_store_identities(node: ast.AST) -> bool:
    root = _root(node)
    return isinstance(root, ast.Attribute) and root.attr == "identities" and ast.unparse(root.value) in IDENTITY_OWNERS


def _is_outbox(node: ast.AST) -> bool:
    root = _root(node)
    return isinstance(root, ast.Attribute) and root.attr == "outbox"


def _qualname(parents: dict[ast.AST, ast.AST], node: ast.AST) -> str:
    names = []
    while node in parents:
        node = parents[node]
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.append(node.name)
    return ".".join(reversed(names)) or "<module>"


def _kinds(node: ast.AST) -> list[str]:
    kinds: list[str] = []
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        attr, owner = node.func.attr, ast.unparse(node.func.value)
        if attr == "queue" and node.args:
            first = node.args[0]
            action = first.value if isinstance(first, ast.Constant) and isinstance(first.value, str) else "?"
            kinds.append("queue:" + action)
        elif attr == "settle" and owner.split(".")[-1] == "commerce" or attr == "settle" and owner == "commerce":
            kinds.append("settle")
        elif attr == "identity" and owner in IDENTITY_OWNERS:
            kinds.append("identity()")  # Dropped by writer_sites when only read or copied.
        if attr in MUTATORS:
            if _is_store_identities(node.func.value):
                kinds.append("identities")
            if _is_outbox(node.func.value):
                kinds.append("outbox")
    targets: list[ast.AST] = []
    if isinstance(node, ast.Assign):
        targets = list(node.targets)
    elif isinstance(node, (ast.AugAssign, ast.AnnAssign)):
        targets = [node.target]
    flat: list[ast.AST] = []
    for target in targets:
        flat.extend(target.elts if isinstance(target, ast.Tuple) else [target])
    for target in flat:
        if isinstance(target, ast.Attribute) and target.attr == "clone_debt":
            kinds.append("clone_debt")
        if (isinstance(target, ast.Subscript) and isinstance(target.slice, ast.Constant)
                and target.slice.value == "clone_debt"):
            kinds.append("clone_debt")
        if isinstance(target, (ast.Subscript, ast.Attribute)):
            if isinstance(target, ast.Subscript) and _is_store_identities(target):
                kinds.append("identities")
            if isinstance(target, ast.Attribute) and target.attr == "identities" and ast.unparse(target.value) in IDENTITY_OWNERS:
                kinds.append("identities")
            if isinstance(target, ast.Subscript) and _is_outbox(target):
                kinds.append("outbox")
    return kinds


def _live_read(parents: dict[ast.AST, ast.AST], node: ast.AST) -> bool:
    """A load of the live identity store that is not copied first."""
    if not (isinstance(node, ast.Attribute) and node.attr == "identities" and isinstance(node.ctx, ast.Load)
            and ast.unparse(node.value) in IDENTITY_OWNERS):
        return False
    child, parent = node, parents.get(node)
    while isinstance(parent, ast.Subscript) and parent.value is child or (
            isinstance(parent, ast.Attribute) and parent.attr == "get" and isinstance(parents.get(parent), ast.Call)):
        if isinstance(parent, ast.Attribute):
            parent = parents[parent]
        child, parent = parent, parents.get(parent)
    if isinstance(parent, ast.Call) and ast.unparse(parent.func) == "deepcopy":
        return False  # A copy; writes to it reach storage only through an effect.
    if isinstance(parent, ast.Compare) or isinstance(parent, ast.Attribute) and parent.attr in ("get", "items", "keys", "values"):
        return False  # Compared or iterated, not held.
    return not _kinds(parent) if parent is not None else True


def _only_read(parents: dict[ast.AST, ast.AST], node: ast.AST) -> bool:
    """The live identity is deep-copied, or only looked into, in this expression."""
    child, parent = node, parents.get(node)
    if isinstance(parent, ast.Attribute) and parent.attr == "get":
        return True
    while isinstance(parent, ast.expr):
        if isinstance(parent, ast.Call) and ast.unparse(parent.func) == "deepcopy":
            return True
        child, parent = parent, parents.get(parent)
    return False


def writer_sites(root: Path = SERVER) -> dict[str, int]:
    """Every writer key with the number of sites behind it."""
    found: dict[str, int] = {}
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
        rel = path.relative_to(root).as_posix()
        for node in ast.walk(tree):
            extra = ["identities-held"] if _live_read(parents, node) else []
            kinds = [k for k in _kinds(node) if not (k == "identity()" and _only_read(parents, node))]
            for kind in kinds + extra:
                key = f"{rel}::{_qualname(parents, node)}::{kind}"
                found[key] = found.get(key, 0) + 1
    return found


if __name__ == "__main__":
    for key, count in sorted(writer_sites().items()):
        print(count, key)
