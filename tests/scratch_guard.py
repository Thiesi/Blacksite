"""Keep local test scratch bounded (AGENTS.md section 5, disk hygiene).

Several million scratch files once piled up across the local worktrees
and took the host down. Most of them came from pytest runs pointed at a
new `.test-tmp/<name>` for every run, plus proof roots and venvs left
behind. pytest clears an explicit --basetemp only when the same path is
reused, so a fresh name per run is never cleaned.

Moving that scratch to the system temp folder only moved the problem:
on 2026-11-06 it passed half a million entries there too, about 318,000
of them in `blacksite-*` folders, and had to be cleared by hand before
the host failed again. So the temp folder is bounded as well.

Three checks run before any test:
- an explicit --basetemp inside the worktree must be `.test-tmp/pytest`,
  the one fixed name, so each run replaces the last;
- the worktree's ignored scratch (`.test-tmp`, `.pytest_cache`) must hold
  fewer than SCRATCH_LIMIT files. Above that, run
  `python scripts/clean_scratch.py` first;
- this project's folders in the system temp folder must hold fewer than
  SCRATCH_LIMIT files. Above that, run
  `python scripts/clean_scratch.py --temp` first.

NativeProbe, which most native proofs start from, makes the last check too.
"""
from __future__ import annotations

import os
from pathlib import Path
import tempfile

from karst41.environment import setting

SCRATCH_DIRS = ('.test-tmp', '.pytest_cache')
LOCAL_BASETEMP = Path('.test-tmp') / 'pytest'
DEFAULT_LIMIT = 50_000
# pytest-of-* is left out: pytest bounds it, and concurrent full runs would
# otherwise trip the limit with nothing to clean.
# Remove in S31: keep counting legacy scratch until its aliases retire.
TEMP_PATTERNS = ('karst41-*', 'blacksite-*', 'native-proof-*')


def scratch_limit() -> int:
    return int(setting(os.environ, ('KARST41_SCRATCH_LIMIT',), str(DEFAULT_LIMIT)))


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
                        f'KARST41_SCRATCH_LIMIT raises the limit for one run.')
    return None


def temp_folders(temp: Path | None = None) -> list[Path]:
    temp = Path(tempfile.gettempdir()) if temp is None else temp
    return sorted(path for pattern in TEMP_PATTERNS for path in temp.glob(pattern))


def temp_files(temp: Path | None = None, stop_after: int = 10**9) -> int:
    total = 0
    for path in temp_folders(temp):
        # A link counts as one entry: its target isn't this project's scratch.
        total += count_files(path, stop_after - total) if path.is_dir() and not path.is_symlink() else 1
        if total > stop_after:
            break
    return total


def temp_problem(temp: Path | None = None, limit: int | None = None) -> str | None:
    limit = scratch_limit() if limit is None else limit
    if temp_files(temp, limit) > limit:
        return (f'This project holds more than {limit:,} files in the system temp folder '
                f'({", ".join(TEMP_PATTERNS)}). The temp folder is not storage, and past half a million '
                f'entries it has taken this host down. Run `python scripts/clean_scratch.py --temp`, '
                f'and keep any evidence you need on the PR or in docs/ first. That keeps folders written '
                f'to in the last 24 hours; once no proof is running, `--temp --older-than 0` removes them too. '
                f'KARST41_SCRATCH_LIMIT raises the limit for one run.')
    return None
