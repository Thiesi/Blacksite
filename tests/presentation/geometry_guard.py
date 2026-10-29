"""Architecture 5.5.1: detect arithmetic on raw terminal dimensions.

Trace dimension aliases within each function. Shared geometry results are
not raw terminal dimensions. World-memory dimensions and the generic text
wrapper's input are deliberately distinct from terminal layout inputs.
"""

import ast
from collections.abc import Iterator
from pathlib import Path

DIMENSIONS = {'width', 'height', 'terminal_width', 'terminal_height'}
NON_TERMINAL = {('players.py', 'pack_memory'), ('players.py', 'unpack_memory'),
                ('wake.py', 'wrapped')}


def _nodes(node: ast.AST) -> Iterator[ast.AST]:
    yield node
    for child in ast.iter_child_nodes(node):
        if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            yield from _nodes(child)


def geometry_copies(path: Path) -> list[str]:
    source = path.read_text(encoding='utf-8')
    tree = ast.parse(source)
    shared = {alias.asname or alias.name for node in tree.body
              if isinstance(node, ast.ImportFrom) and node.module == 'blacksite.layout'
              for alias in node.names if alias.name == 'compute'}
    scopes = [tree, *(node for node in ast.walk(tree)
                     if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)))]
    problems = []
    for scope in scopes:
        if (path.name, getattr(scope, 'name', '')) in NON_TERMINAL:
            continue
        raw = {arg.arg for arg in (*scope.args.posonlyargs, *scope.args.args, *scope.args.kwonlyargs)
               if arg.arg in DIMENSIONS} if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)) else set()
        caps = {'caps'}

        def is_caps(node: ast.AST) -> bool:
            return isinstance(node, ast.Attribute) and node.attr == 'caps' or isinstance(node, ast.Name) and node.id in caps

        def dimension(node: ast.AST) -> bool:
            if isinstance(node, (ast.Tuple, ast.List, ast.Dict, ast.Set)):
                return False  # Cache/version keys carry dimensions without deriving geometry.
            if isinstance(node, ast.Name):
                return node.id in raw
            if isinstance(node, ast.Subscript) and is_caps(node.value):
                return isinstance(node.slice, ast.Constant) and node.slice.value in DIMENSIONS
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in shared:
                    return False
                if isinstance(node.func, ast.Attribute) and node.func.attr == 'get' and is_caps(node.func.value):
                    return bool(node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value in DIMENSIONS)
                if not isinstance(node.func, ast.Name) or node.func.id not in {'int', 'float', 'min', 'max'}:
                    return False  # Forwarding dimensions does not derive a layout.
            return any(dimension(child) for child in ast.iter_child_nodes(node))

        for node in _nodes(scope):
            if isinstance(node, (ast.Assign, ast.AnnAssign, ast.NamedExpr)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                names = {part.id for target in targets for part in ast.walk(target) if isinstance(part, ast.Name)}
                if node.value is not None and is_caps(node.value):
                    caps.update(names)
                if node.value is not None and dimension(node.value):
                    raw.update(names)
            operation = isinstance(node, (ast.BinOp, ast.Compare, ast.IfExp)) or (
                isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {'min', 'max'})
            if operation and dimension(node):
                problems.append(f'{path.name}:{node.lineno}: {ast.get_source_segment(source, node)}')
    return sorted(set(problems))
