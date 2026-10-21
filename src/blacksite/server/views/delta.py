"""Revisioned JSON-pointer patches compatible with the S04 client."""

import json
from typing import Any

from blacksite.server.protocol import Frame, encode
from blacksite.server.sessions import Session


def _size(value: object) -> int:
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def changes(old: Any, new: Any, path: str = "") -> list[dict[str, Any]]:
    if old == new:
        return []
    replacement = [{"op": "replace", "path": path, "value": new}]
    ops: list[dict[str, Any]] = []
    if isinstance(old, dict) and isinstance(new, dict):
        for key in sorted(old.keys() | new.keys()):
            child = path + "/" + str(key).replace("~", "~0").replace("/", "~1")
            if key not in new:
                ops.append({"op": "remove", "path": child})
            elif key not in old:
                ops.append({"op": "add", "path": child, "value": new[key]})
            else:
                ops.extend(changes(old[key], new[key], child))
    elif isinstance(old, list) and isinstance(new, list) and len(old) == len(new):
        for index, (before, after) in enumerate(zip(old, new)):
            ops.extend(changes(before, after, path + f"/{index}"))
    else:
        return replacement
    # Sparse cell/actor updates usually win; large row edits replace the row.
    return ops if not path or _size(ops) < _size(replacement) else replacement


class ViewStore:
    def __init__(self) -> None:
        self.previous: dict[str, Any] | None = None

    def publish(self, session: Session, body: dict[str, Any], tick: int) -> bool:
        """Take ownership of a snapshot whose nested arrays stay immutable."""
        document = {"kind": "zone", "body": body}
        if document == self.previous and not session.needs_full_view:
            return False
        revision = session.view_revision + 1
        full = Frame("view", {"rev": revision, **document})
        delta = None
        if self.previous is not None and self.previous["body"]["viewport"] == body["viewport"]:
            ops = changes(self.previous, document)
            candidate = Frame("delta", {"rev": revision, "base": session.view_revision, "ops": ops})
            if len(ops) <= 256 and len(encode(candidate)) < len(encode(full)):
                delta = candidate
        if session.publish_view(full, delta, tick):
            self.previous = document
            return True
        return False
