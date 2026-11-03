"""Keep local test scratch bounded (AGENTS.md section 5, disk hygiene).

Several million scratch files once piled up across the local worktrees
and took the host down. Most of them came from pytest runs pointed at a
new `.test-tmp/<name>` for every run, plus proof roots and venvs left
behind. pytest clears an explicit --basetemp only when the same path is
reused, so a fresh name per run is never cleaned.

Two checks run before any test:
- an explicit --basetemp inside the worktree must be `.test-tmp/pytest`,
  the one fixed name, so each run replaces the last;
- the worktree's ignored scratch (`.test-tmp`, `.pytest_cache`) must hold
  fewer than SCRATCH_LIMIT files. Above that, run
  `python scripts/clean_scratch.py` first.
"""
from __future__ import annotations

import os
from pathlib import Path

SCRATCH_DIRS = ('.test-tmp', '.pytest_cache')
LOCAL_BASETEMP = Path('.test-tmp') / 'pytest'
DEFAULT_LIMIT = 50_000


def scratch_limit() -> int:
    return int(os.environ.get('BLACKSITE_SCRATCH_LIMIT', DEFAULT_LIMIT))


def count_files(root: Path, stop_after: int) -> int:
    """Files under root, counting at most stop_after + 1 so a huge tree stays cheap."""
    count, pending = 0, [root]
    while pending:
        try:
            entries = os.scandir(pending.pop())
        except OSError:
            continue
        with entries:
            for entry in entries:
                try:
                    if entry.is_dir(follow_symlinks=False):
                        pending.append(Path(entry.path))
                        continue
                except OSError:
                    continue
                count += 1
                if count > stop_after:
                    return count
    return count


def basetemp_problem(basetemp: str | os.PathLike[str] | None, root: Path) -> str | None:
    if not basetemp:
        return None
    path, root = Path(basetemp).resolve(), root.resolve()
    if not path.is_relative_to(root) or path == (root / LOCAL_BASETEMP).resolve():
        return None
    return (f'--basetemp {path} is inside the worktree under a name that is never cleaned. '
            f'Omit --basetemp (pytest then uses the system temp folder and keeps only failed runs) '
            f'or use --basetemp={LOCAL_BASETEMP.as_posix()}, which every run replaces.')


def scratch_problem(root: Path, limit: int | None = None) -> str | None:
    limit = scratch_limit() if limit is None else limit
    total = 0
    for name in SCRATCH_DIRS:
        if (root / name).is_dir():
            total += count_files(root / name, limit - total)
            if total > limit:
                return (f'This worktree holds more than {limit:,} scratch files in '
                        f'{" and ".join(SCRATCH_DIRS)}. Run `python scripts/clean_scratch.py` '
                        f'(keep any evidence you need in docs/ or on the PR first). '
                        f'BLACKSITE_SCRATCH_LIMIT raises the limit for one run.')
    return None
