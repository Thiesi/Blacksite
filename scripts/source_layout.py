"""Resolve trusted proof revisions across R1 without an import shim.

Historical Git objects and capture hashes keep their original paths.
Only the current proof reader maps a package path at a selected revision.
"""

from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
CURRENT = 'src/karst41'
LEGACY = 'src/blacksite'  # Historical evidence, not an installed alias.


def at_revision(revision: str, path: str, *, root: Path = ROOT) -> str:
    """Return the package spelling actually present in this Git revision."""
    if path != CURRENT and not path.startswith(CURRENT+'/'):
        return path
    present = subprocess.run(['git', 'cat-file', '-e', f'{revision}:{CURRENT}'],
        cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
    return path if present else LEGACY+path[len(CURRENT):]


def revision_argument(value: str, *, root: Path = ROOT) -> str:
    if ':' not in value:
        return value
    revision, path = value.split(':', 1)
    return revision+':'+at_revision(revision, path, root=root)
