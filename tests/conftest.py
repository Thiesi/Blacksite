"""Shared fixtures for the Blacksite test suite.

Tests never write outside pytest's temporary tree and never leave the
machine (AGENTS.md section 5).
"""

from pathlib import Path

import pytest

REPO_ROOT: Path = Path(__file__).resolve().parent.parent


@pytest.fixture
def repo_root() -> Path:
    """The repository root, for tests that read shipped files."""
    return REPO_ROOT


@pytest.fixture
def scratch_dir(tmp_path: Path) -> Path:
    """An empty per-test directory inside pytest's tmp_path.

    Use this instead of any hard-coded temporary path such as /tmp.
    """
    path = tmp_path / "scratch"
    path.mkdir()
    return path
