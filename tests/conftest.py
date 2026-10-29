"""Shared fixtures for the Blacksite test suite.

Tests never write outside pytest's temporary tree and never leave the
machine (AGENTS.md section 5).
"""

from pathlib import Path
from typing import Protocol

import pytest

from tests.presentation.snapshots import assert_golden
from tests.fake_terminal import FakeTerminal
from blacksite.door.model import Display
from tests.presentation.provenance import render_with_provenance
from blacksite.server.protocol import Frame


class Golden(Protocol):
    def __call__(self, name: str, terminal: FakeTerminal, tier: str, *, trim: bool = False) -> None: ...


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption('--update-goldens', action='store_true', help='Regenerate P1 glyph/style baselines explicitly')
    parser.addoption('--review-packet', type=Path, help='Write byte-preserved headless review frames')


@pytest.fixture
def caller_provenance(monkeypatch: pytest.MonkeyPatch) -> None:
    render = Display.render
    def tracked(model: Display, now: float) -> tuple[bytes, Frame | None]:
        return render_with_provenance(render, model, now)
    monkeypatch.setattr(Display, 'render', tracked)


@pytest.fixture
def golden(request: pytest.FixtureRequest, caller_provenance: None) -> Golden:
    def check(name: str, terminal: FakeTerminal, tier: str, *, trim: bool = False) -> None:
        assert_golden(REPO_ROOT/'tests/door/golden', name, terminal, tier,
            update=request.config.getoption('--update-goldens'), trim=trim,
            packet=request.config.getoption('--review-packet'))
    return check

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
