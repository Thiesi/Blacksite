"""scripts/clean_scratch.py removes only ignored scratch."""
import importlib.util
import os
import time
from pathlib import Path

import pytest

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


def test_older_than_zero_clears_recent_folders(tmp_path: Path) -> None:
    (tmp_path / 'blacksite-recent').mkdir()
    (tmp_path / 'blacksite-recent' / 'f').write_text('x')
    assert clean_scratch.clean_temp(tmp_path, hours=24) == 0
    assert (tmp_path / 'blacksite-recent').exists()
    assert clean_scratch.clean_temp(tmp_path, hours=0, now=time.time() + 1) == 0
    assert not (tmp_path / 'blacksite-recent').exists()


def test_a_stale_link_is_removed_and_its_target_left_alone(tmp_path: Path) -> None:
    target = tmp_path / 'elsewhere'
    target.mkdir()
    (target / 'keep').write_text('x')
    link = tmp_path / 'temp' / 'blacksite-link'
    link.parent.mkdir()
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip('this account cannot create symlinks')
    assert clean_scratch.clean_temp(link.parent, hours=0, now=time.time() + 1) == 0
    assert not link.is_symlink()
    assert (target / 'keep').exists()
