"""B2 evidence integrity: count emitted columns and preserve cold/warm walks."""

from pathlib import Path

from blacksite.content.loader import load_content
from blacksite.door.cells import CellBuffer
from blacksite.door.present import zone
from blacksite.door.present.places import Places
from scripts.presentation_p6b_profile import emitted_cells, profile
from tests.fake_terminal import FakeTerminal


def test_emitted_columns_match_wide_combining_delta_and_reserved_corner() -> None:
    previous = CellBuffer(80, 24)
    current = CellBuffer(80, 24)
    current.put(2, 2, '\u754ce\u0301')
    terminal = FakeTerminal()
    terminal.write(previous.full())
    terminal.write(current.diff(previous))
    assert terminal.cell(2, 2) == '\u754c' and terminal.cell(3, 2) == ''
    assert terminal.cell(4, 2) == 'e\u0301'
    assert emitted_cells(current, previous) == 3
    assert emitted_cells(current, current) == 0
    assert emitted_cells(current, None) == 80*24-1
    assert emitted_cells(current, CellBuffer(132, 50)) == 80*24-1


def test_profile_retains_entry_same_viewport_revisit_and_real_diff_counts() -> None:
    content = load_content(Path(__file__).resolve().parents[2]/'src/blacksite/content')
    original = zone.terrain, CellBuffer.diff, Places.cell
    ordinary = profile(content, 'vatside-clinics', '256', False)
    assert [p['phase'] for p in ordinary['phases']] == ['cold', 'warm']
    assert all(p['successful_moves'] == 16 for p in ordinary['phases'])
    assert ordinary['phases'][0]['initial'] == ordinary['phases'][1]['initial']
    entry = [s for s in ordinary['samples'] if s['phase'] == 'entry']
    assert entry and entry[0]['frame']['kind'] == 'full'
    assert entry[0]['emitted_cells'] == 132*50-1
    assert all(p['steps']['diff_wall_ms']['count'] == 16 for p in ordinary['phases'])
    assert any(s['terrain_cells'] > 0 for s in ordinary['samples'])
    assert any(s['emitted_cells'] > 0 for s in ordinary['samples'] if s['phase'] == 'warm')
    # Temporary probes restore runtime methods after every render.
    assert original == (zone.terrain, CellBuffer.diff, Places.cell)
