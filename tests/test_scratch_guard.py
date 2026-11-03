"""Local scratch stays bounded (tests/scratch_guard.py, AGENTS.md section 5)."""
from pathlib import Path

from tests.scratch_guard import LOCAL_BASETEMP, basetemp_problem, count_files, scratch_problem


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
