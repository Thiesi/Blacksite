"""Local scratch stays bounded (tests/scratch_guard.py, AGENTS.md section 5)."""
from pathlib import Path

import pytest

from tests.scratch_guard import LOCAL_BASETEMP, basetemp_problem, count_files, scratch_problem, temp_files, temp_problem


def test_basetemp_outside_the_worktree_or_absent_is_fine(tmp_path: Path) -> None:
    root = tmp_path / 'wt'
    root.mkdir()
    assert basetemp_problem(None, root) is None
    assert basetemp_problem(tmp_path / 'elsewhere', root) is None


def test_only_the_fixed_local_basetemp_is_allowed_inside_the_worktree(tmp_path: Path) -> None:
    root = tmp_path / 'wt'
    root.mkdir()
    assert basetemp_problem(root / LOCAL_BASETEMP, root) is None
    problem = basetemp_problem(root / '.test-tmp' / 's19-full-root-5', root)
    assert problem and '.test-tmp/pytest' in problem


def test_scratch_over_the_limit_is_refused(tmp_path: Path) -> None:
    nested = tmp_path / '.test-tmp' / 'proof' / 'deep'
    nested.mkdir(parents=True)
    for i in range(6):
        (nested / f'f{i}').write_text('x')
    (tmp_path / '.pytest_cache').mkdir()
    (tmp_path / '.pytest_cache' / 'v').write_text('x')
    (tmp_path / 'src.txt').write_text('tracked files never count')
    assert scratch_problem(tmp_path, limit=7) is None
    problem = scratch_problem(tmp_path, limit=6)
    assert problem and 'clean_scratch.py' in problem


def test_counting_stops_early(tmp_path: Path) -> None:
    for i in range(50):
        (tmp_path / f'f{i}').write_text('x')
    assert count_files(tmp_path, 9) == 10
    assert count_files(tmp_path, 100) == 50


def test_temp_over_the_limit_is_refused_and_only_our_folders_count(tmp_path: Path) -> None:
    for rel in ('blacksite-s38/a/b', 'blacksite-s38/c', 'native-proof-1/d', 'blacksite-demo.json',
                'claude/session/scratchpad/e', 'pytest-of-me/f', 'other/g'):
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('x')
    assert temp_files(tmp_path) == 4
    assert temp_problem(tmp_path, limit=4) is None
    problem = temp_problem(tmp_path, limit=3)
    assert problem and 'clean_scratch.py --temp' in problem


def test_an_empty_temp_folder_is_fine(tmp_path: Path) -> None:
    assert temp_problem(tmp_path, limit=0) is None


def test_a_link_counts_once_and_its_target_is_not_walked(tmp_path: Path) -> None:
    target = tmp_path / 'elsewhere'
    target.mkdir()
    for i in range(5):
        (target / f'f{i}').write_text('x')
    temp = tmp_path / 'temp'
    temp.mkdir()
    try:
        (temp / 'blacksite-link').symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip('this account cannot create symlinks')
    assert temp_files(temp) == 1
