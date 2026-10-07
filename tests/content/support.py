"""Helpers for content tests: scratch copies of the fixture world."""

import json
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

from blacksite.content.loader import ContentTree, load_content
from blacksite.content.validate import Problem, validate

FIXTURE_WORLD = Path(__file__).resolve().parent.parent / "fixtures" / "world"
SHIPPED = Path(__file__).resolve().parents[2] / "src" / "blacksite" / "content"


class World:
    """A scratch copy of the fixture world with JSON editing helpers."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def path(self, rel: str) -> Path:
        return self.root / rel

    def read(self, rel: str) -> Any:
        return json.loads(self.path(rel).read_text(encoding="utf-8"))

    def write(self, rel: str, data: Any) -> None:
        path = self.path(rel)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")

    def edit(self, rel: str, change: Callable[[Any], None]) -> None:
        data = self.read(rel)
        change(data)
        self.write(rel, data)

    def write_text(self, rel: str, text: str) -> None:
        path = self.path(rel)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")

    def load(self) -> ContentTree:
        return load_content(self.root)

    def problems(self) -> list[Problem]:
        return validate(self.load())

    def messages(self) -> list[str]:
        return [str(p) for p in self.problems()]


def find(items: list[dict], record_id: str) -> dict:
    return next(i for i in items if i["id"] == record_id)


def copy_world(scratch_dir: Path) -> World:
    root = scratch_dir / "world"
    shutil.copytree(FIXTURE_WORLD, root)
    return World(root)
