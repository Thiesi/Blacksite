"""P2 / architecture 5.5.1: geometry has one source and no visible change."""

from pathlib import Path

import pytest

from blacksite.layout import Page, Rect, compute
from blacksite.door.layout import compute as door_layout
from blacksite.door.log import rows
from blacksite.door.cells import display_width
from tests.presentation.geometry_guard import geometry_copies


@pytest.mark.parametrize('width,height,viewport,overlay,briefing,city,contracts,wake,encounter,private,cursor', [
    (80, 24, (55, 17), (5, 1, 70, 17), (51, 14), (52, 14), (66, 11), 66, 64, 66, 8),
    (99, 24, (74, 17), (14, 1, 70, 17), (70, 14), (71, 14), (66, 11), 66, 83, 66, 8),
    (100, 24, (75, 17), (3, 1, 94, 17), (71, 14), (72, 14), (50, 14), 44, 38, 52, 12),
    (132, 50, (107, 38), (11, 1, 110, 38), (103, 35), (104, 40), (50, 35), 52, 54, 52, 33),
    (80, 28, (55, 20), (5, 1, 70, 20), (51, 17), (52, 18), (66, 14), 66, 64, 66, 11),
])
def test_current_tier_preserves_legacy_shapes_and_page_policies(width: int, height: int,
        viewport: tuple[int, int], overlay: tuple[int, int, int, int],
        briefing: tuple[int, int], city: tuple[int, int], contracts: tuple[int, int],
        wake: int, encounter: int, private: int, cursor: int) -> None:
    layout = compute(width, height)
    assert door_layout is compute
    assert layout.tier == 'current'
    assert (layout.viewport.width, layout.viewport.height) == viewport
    assert layout.overlay == Rect(*overlay)
    assert layout.briefing == Page(*briefing)
    assert layout.city == Page(*city)
    assert layout.contracts == Page(*contracts)
    assert (layout.wake_detail_width, layout.encounter_width, layout.private_core_width) == (wake, encounter, private)
    assert layout.menu.cursor_page == cursor
    assert layout.hint.y == height - 2 and layout.hint.height == 1
    assert layout.text_area.width == layout.viewport.width - 2
    for area in (layout.header, layout.viewport, layout.side, layout.log, layout.hint,
                 layout.text_area, layout.overlay):
        assert 0 <= area.x < area.right <= layout.frame.right
        assert 0 <= area.y < area.bottom <= layout.frame.bottom


def test_only_current_layout_tier_and_supported_terminal_sizes() -> None:
    with pytest.raises(ValueError, match='layout tier'):
        compute(80, 24, 'future')  # type: ignore[arg-type]
    for width, height in ((79, 24), (80, 23)):
        with pytest.raises(ValueError, match='80x24'):
            compute(width, height)


@pytest.mark.parametrize('width', [0, 1, 2, 3])
def test_log_rejects_width_without_room_for_indented_wide_glyph(width: int) -> None:
    with pytest.raises(ValueError, match='indented wide glyph'):
        rows([{'channel': 'say', 'text': '界'}], width)


def test_minimum_log_width_preserves_whole_wide_glyph() -> None:
    wrapped = rows([{'channel': 'say', 'text': '界'}], 4)
    assert all(display_width(row['text']) <= 4 for row in wrapped)
    assert sum(row['text'].count('界') for row in wrapped) == 1


def test_no_server_terminal_geometry_copies(repo_root: Path) -> None:
    failures = [failure for path in (repo_root/'src/blacksite/server').rglob('*.py')
                for failure in geometry_copies(path)]
    assert failures == []


def test_guard_catches_new_copy_and_dimension_aliases(tmp_path: Path) -> None:
    scratch = tmp_path/'new_panel.py'
    scratch.write_text('def panel(session):\n    caps = session.caps\n    size = caps["width"]\n    return size - 25\n')
    assert geometry_copies(scratch)
    scratch.write_text('def panel(width, height):\n    return min(width - 25, height - 7)\n')
    assert geometry_copies(scratch)
    scratch.write_text('from blacksite.layout import compute as screen\ndef panel(session):\n    return screen(session.caps["width"], session.caps["height"]).viewport\n')
    assert geometry_copies(scratch) == []
    scratch.write_text('def changed(session, old):\n    stamp = (session.caps["width"], session.caps["height"])\n    return stamp != old\n')
    assert geometry_copies(scratch) == []
