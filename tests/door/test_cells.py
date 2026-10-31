"""Terminal UI §6: independent replay checks destructive terminal behavior."""

from blacksite.door.cells import CellBuffer, display_width, truncate
from tests.fake_terminal import FakeTerminal


def test_cached_copy_preserves_wide_combining_and_rejects_partial_glyphs() -> None:
    source = CellBuffer(80,24)
    source.put(2,2,'界e\u0301')
    target = CellBuffer(80,24)
    target.copy_from(source,0,0,80,24)
    terminal = FakeTerminal()
    terminal.write(target.full())
    assert terminal.cell(2,2) == '界' and terminal.cell(3,2) == ''
    assert terminal.cell(4,2) == 'e\u0301'
    cropped = CellBuffer(80,24)
    cropped.copy_from(source,3,2,1,1)
    cropped.copy_from(source,2,3,1,1)
    cropped.copy_from(source,2,2,1,1)
    screen = FakeTerminal()
    screen.write(cropped.full())
    assert screen.cell(2,2) == screen.cell(3,2) == ' '
    assert source.cells[2][2].glyph == '界'  # Cropping never edits the source.


def test_cached_copy_isolates_rows_clears_old_wide_glyphs_and_keeps_last_cell_safe() -> None:
    source,target = CellBuffer(80,24),CellBuffer(80,24)
    source.put(3,2,'a')
    target.put(2,2,'界')
    target.copy_from(source,3,2,1,1)
    target.put(3,2,'b')
    assert source.cells[2][3].glyph == 'a'
    source.put(78,23,'x')
    source.put(79,23,'y')
    target.copy_from(source,-1,-1,100,30)
    screen = FakeTerminal()
    screen.write(target.full())
    assert screen.cell(2,2) == ' ' and screen.cell(3,2) == 'a'
    assert screen.cell(78,23) == 'x' and screen.cell(79,23) == ' '


def test_wide_glyph_two_cells_and_combining_zero_width() -> None:
    buffer = CellBuffer(80, 24)
    buffer.put(0, 0, "界e\u0301")
    terminal = FakeTerminal()
    terminal.write(buffer.full())
    assert terminal.cell(0, 0) == "界" and terminal.cell(1, 0) == ""
    assert terminal.cell(2, 0) == "e\u0301"
    assert display_width("界e\u0301") == 3


def test_wide_refused_at_last_column_and_never_writes_last_cell() -> None:
    buffer = CellBuffer(80, 24)
    buffer.put(79, 0, "界")
    buffer.put(79, 23, "x")
    buffer.put(78, 23, "界")
    terminal = FakeTerminal()
    terminal.write(buffer.full())
    assert terminal.cell(79, 0) == " "
    assert terminal.cell(79, 23) == " "


def test_clip_by_display_width() -> None:
    assert truncate("界界abc", 6) == "界..."
    assert display_width(truncate("界界abc", 6)) <= 6
    buffer = CellBuffer(80, 24)
    buffer.put(77, 0, "界abc")
    assert buffer.cells[0][77].glyph == "界"
    assert buffer.cells[0][79].glyph == "a"


def test_diff_minimal_moves_and_wide_replacement() -> None:
    before = CellBuffer(80, 24)
    after = CellBuffer(80, 24)
    after.put(1, 1, "abc")
    data = after.diff(before)
    assert data.count(b"H") == 1
    terminal = FakeTerminal()
    terminal.write(before.full())
    terminal.write(data)
    assert terminal.screen_text() == after.screen_text()
    wide = CellBuffer(80, 24)
    wide.put(1, 1, "界")
    terminal.write(wide.diff(after))
    replacement = CellBuffer(80, 24)
    replacement.put(1, 1, "x")
    terminal.write(replacement.diff(wide))
    assert terminal.screen_text() == replacement.screen_text()


def test_untrusted_controls_never_reach_terminal() -> None:
    buffer = CellBuffer(80, 24)
    buffer.put(1, 1, "A\x1b[31mB\x07\x1b]0;bad\x07C\x1b[2JD")
    terminal = FakeTerminal()
    terminal.write(buffer.full())
    assert "ABCD" in terminal.screen_text()
    assert b"\x07" not in terminal.written
