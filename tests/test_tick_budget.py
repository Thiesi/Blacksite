"""S11's CI tick budget (owner, 2026-11-12): block at 20 ms, warn at 10 ms."""

import pytest

from scripts.tick_budget import BLOCK_MS, WARN_MS, enforce, verdict


def test_owner_2026_11_12_limits() -> None:
    assert (WARN_MS, BLOCK_MS) == (10.0, 20.0)


@pytest.mark.parametrize(('p99', 'expected'), [
    (0.0, 'pass'), (9.999, 'pass'), (10.0, 'warn'), (19.999, 'warn'), (20.0, 'block'), (55.0, 'block')])
def test_verdict_edges(p99: float, expected: str) -> None:
    assert verdict(p99) == expected


def test_warning_annotates_and_passes() -> None:
    lines: list[str] = []
    assert enforce(12.5, 'S11 80x24', lines.append) == 'warn'
    assert len(lines) == 1 and lines[0].startswith('::warning title=S11 tick budget::S11 80x24')


def test_pass_is_silent() -> None:
    lines: list[str] = []
    assert enforce(4.0, 'S11 80x24', lines.append) == 'pass'
    assert lines == []


def test_block_fails_without_annotating() -> None:
    lines: list[str] = []
    with pytest.raises(AssertionError, match='20 ms limit'):
        enforce(20.105, 'S11 132x50', lines.append)
    assert lines == []


def test_warning_title_names_the_caller() -> None:
    lines: list[str] = []
    enforce(15.0, 'admin status 80x24', lines.append, title='S25a tick budget')
    assert lines[0].startswith('::warning title=S25a tick budget::admin status 80x24')
