"""P1 gates detect changed rules, colour, ANSI semantics and bad glyphs."""

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path

import pytest

from blacksite.content.loader import ContentTree, load_content
from blacksite.door.cells import CellBuffer
from blacksite.door.palette import Palette, Style
from tests.ansi_style import Rendition
from tests.fake_terminal import FakeTerminal
from tests.presentation.mechanics import fingerprint, walk, zone_seed
from tests.presentation.snapshots import assert_golden, canonical, cp437_problems, snapshot, write_packet


@pytest.fixture(scope='module')
def content() -> ContentTree:
    return load_content(Path(__file__).parents[2]/'src/blacksite/content')


def test_sgr_semantics_normalize_resets_incremental_colours_and_attributes() -> None:
    one, split = FakeTerminal(), FakeTerminal()
    one.write(b'\x1b[0;1;38;5;42;48;2;1;2;3mA')
    split.write(b'\x1b[1m\x1b[38;5;42m\x1b[48;2;1;2;3mA')
    assert snapshot(one) == snapshot(split)
    split.write(b'\x1b[22;39;49mB')
    assert split.renditions[1, 0] == Rendition()


def test_colour_regression_fails_style_golden_and_preserves_mechanics(content: ContentTree, tmp_path: Path) -> None:
    original = fingerprint(content)
    terminal = FakeTerminal()
    buffer = CellBuffer(80, 24)
    buffer.put(1, 1, 'Colour', Style(42))
    terminal.write(buffer.full())
    assert_golden(tmp_path, 'colour', terminal, '256', update=True)
    # Change actual content colour, then draw it through the shipped encoder.
    changed = deepcopy(content)
    roles = deepcopy(changed.palette.roles)
    roles['ui_text']['256']['default'] = 43
    changed.palette = replace(changed.palette, roles=roles)
    buffer.put(1, 1, 'Colour', Palette({'roles': roles}).style('text'))
    terminal.write(buffer.full())
    with pytest.raises(AssertionError, match='style golden differs'):
        assert_golden(tmp_path, 'colour', terminal, '256')
    assert fingerprint(changed) == original


def test_rule_regression_changes_fingerprint_without_palette_change(content: ContentTree) -> None:
    changed = deepcopy(content)
    changed.tiles['floor'] = replace(changed.tiles['floor'], cover=1)
    assert changed.palette == content.palette
    assert fingerprint(changed)['sha256'] != fingerprint(content)['sha256']


def test_zone_seeds_ignore_catalog_order_and_walk_is_viewport_independent(content: ContentTree) -> None:
    ordered = {key: zone_seed(key) for key in content.zones}
    reverse = {key: zone_seed(key) for key in reversed(content.zones)}
    reverse['a-new-future-zone'] = zone_seed('a-new-future-zone')
    assert ordered == {key: reverse[key] for key in ordered}
    assert walk(content, 80, 24) == walk(content, 132, 50)


def test_every_existing_golden_has_every_style_tier() -> None:
    root = Path(__file__).parents[2]/'tests/door/golden'
    names = {p.stem for p in root.glob('*.txt')}
    for tier in ('16', '256', 'truecolor'):
        assert {p.stem for p in (root/'styles/cp437'/tier).glob('*.json')} == names


def test_mechanics_baseline(content: ContentTree, request: pytest.FixtureRequest) -> None:
    path = Path(__file__).with_name('mechanics.json')
    current = canonical(fingerprint(content))
    if request.config.getoption('--update-goldens'):
        path.write_text(current, encoding='utf-8', newline='\n')
    assert path.read_text(encoding='utf-8') == current, 'mechanics fingerprint differs; explain any approved rebaseline'


def test_cp437_gate_checks_every_cell_and_never_exempts_user_text(tmp_path: Path) -> None:
    terminal = FakeTerminal()
    terminal.write('┆界'.encode('utf-8'))
    problems = cp437_problems(terminal)
    assert [p['codepoints'] for p in problems] == [['U+2506'], ['U+754C']]
    write_packet(tmp_path, terminal, {'scenario': 'strict-cp437'})
    assert json.loads((tmp_path/'context.json').read_text(encoding='utf-8'))['cp437_pass'] is False


def test_packet_replays_actual_delta_bytes_and_styles(tmp_path: Path) -> None:
    first = CellBuffer(80, 24)
    first.put(2, 3, 'First', Style(2))
    second = CellBuffer(80, 24)
    second.put(2, 3, 'Next', Style(3, attrs=(7,)))
    terminal = FakeTerminal()
    terminal.write(first.full())
    delta = second.diff(first)
    terminal.write(delta)
    write_packet(tmp_path, terminal, {'scenario': 'delta'})
    assert (tmp_path/'0001.ans').read_bytes() == delta
    replay = FakeTerminal()
    for path in sorted(tmp_path.glob('*.ans')):
        replay.write(path.read_bytes())
    assert snapshot(replay) == snapshot(terminal)
    assert json.loads((tmp_path/'0001.json').read_text())['base_frame'] == 0
