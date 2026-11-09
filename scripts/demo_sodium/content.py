"""Explicit demo data layer, separate from the frozen shipped city."""

from __future__ import annotations

import json
from pathlib import Path
from shutil import copyfile
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from karst41.content.loader import ContentTree

ROOT = Path(__file__).resolve().parents[2]
OVERLAY = ROOT / 'docs/demo/sodium-row-round4/content'


def load_demo_content(root: Path | None = None) -> ContentTree:
    """Use the production local-content loader, never rewrite shipped data."""
    from karst41.content.loader import load_content
    return load_content(root or ROOT / 'src/karst41/content', OVERLAY)


def install_overlay(install: Path) -> None:
    """Called under the server lease. Replace only our own prior overlay files."""
    install = install.resolve()
    target = (install / 'content.local').resolve()
    if target.parent != install:
        raise ValueError('Demo content.local must stay inside its install directory.')
    manifest = install / '.round4-content.json'
    previous = json.loads(manifest.read_text(encoding='utf-8')) if manifest.exists() else []
    files = [p for p in OVERLAY.rglob('*') if p.is_file()]
    current = [p.relative_to(OVERLAY).as_posix() for p in files]
    for name in set(previous) | set(current):
        path = (target / name).resolve()
        if not path.is_relative_to(target):
            raise ValueError('Demo overlay path escapes its content directory.')
        if name not in previous and path.exists():
            raise ValueError(f'Demo refuses to overwrite an unowned local-content file: {name}')
    for name in set(previous) - set(current):
        path = (target / name).resolve()
        if path.is_file():
            path.unlink()
    for source in files:
        path = target / source.relative_to(OVERLAY)
        path.parent.mkdir(parents=True, exist_ok=True)
        copyfile(source, path)
    manifest.write_text(json.dumps(current, indent=2) + '\n', encoding='utf-8')
