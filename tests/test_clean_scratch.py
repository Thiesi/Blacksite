"""scripts/clean_scratch.py removes only ignored scratch."""
import importlib.util
import os
import time
from pathlib import Path

from tests.conftest import REPO_ROOT

spec = importlib.util.spec_from_file_location('clean_scratch', REPO_ROOT / 'scripts' / 'clean_scratch.py')
clean_scratch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(clean_scratch)


def test_clean_removes_scratch_and_keeps_everything_else(tmp_path: Path) -> None:
    for rel in ('.test-tmp/a/b.txt', '.pytest_cache/v/x', 'src/pkg/__pycache__/m.pyc',
                'src/pkg.egg-info/PKG-INFO', 'src/pkg/m.py', '.venv/__pycache__/keep.pyc', 'docs/evidence.md'):
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('x')
    (tmp_path / '.test-tmp' / 'a' / 'b.txt').chmod(0o444)
    assert clean_scratch.clean(tmp_path) == 0
    left = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob('*') if p.is_file())
    assert left == ['.venv/__pycache__/keep.pyc', 'docs/evidence.md', 'src/pkg/m.py']


def test_clean_temp_removes_only_our_stale_folders(tmp_path: Path) -> None:
    for rel in ('blacksite-old/a/b', 'native-proof-old/c', 'blacksite-running/d', 'blacksite-file.json',
                'claude/session/scratchpad/e', 'pytest-of-me/f', 'other/g'):
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('x')
    now = time.time()
    two_days = now - 48 * 3600
    for path in sorted(tmp_path.rglob('*'), reverse=True):
        os.utime(path, (two_days, two_days))
    # One recent write deep inside keeps the whole folder: a proof may be running.
    os.utime(tmp_path / 'blacksite-running' / 'd', (now, now))
    assert clean_scratch.clean_temp(tmp_path, hours=24, now=now) == 0
    assert sorted(p.name for p in tmp_path.iterdir()) == ['blacksite-running', 'claude', 'other', 'pytest-of-me']
    assert (tmp_path / 'claude' / 'session' / 'scratchpad' / 'e').exists()
