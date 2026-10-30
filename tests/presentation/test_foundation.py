"""P1 gates detect changed rules, colour, ANSI semantics and bad glyphs."""

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import time
from types import SimpleNamespace

import pytest

from blacksite.content.loader import ContentTree, load_content
from blacksite.door.cells import CellBuffer
from blacksite.door.palette import Palette, Style
from tests.ansi_style import Rendition
from tests.fake_terminal import FakeTerminal
from tests.presentation.mechanics import fingerprint, walk, zone_seed
from tests.presentation.snapshots import assert_golden, canonical, cp437_problems, snapshot, write_packet
from blacksite.door.doorinfo import DoorInfo
from blacksite.door.model import Display
from blacksite.server.protocol import Frame
from tests.harness import WIDE_HANDLE


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


def test_object_rule_parameters_change_fingerprint_but_display_name_does_not(content: ContentTree) -> None:
    original = fingerprint(content)
    changed = deepcopy(content)
    terminal = next(obj for zone in changed.zones.values() for obj in zone.meta.objects
                    if obj.kind == 'terminal' and 'sector' in obj.params)
    terminal.params['name'] = 'A different inspection label'
    terminal.params['inspect_verb'] = 'look at'
    assert fingerprint(changed) == original
    terminal.params['sector'] = next(s for s in content.sectors if s != terminal.params['sector'])
    assert fingerprint(changed)['sha256'] != original['sha256']


@pytest.mark.parametrize('what', ['walking in a scene place', 'walking where there is no scene'])
def test_walking_deadlines_include_render_cost_and_every_key_moves(
        content: ContentTree, monkeypatch: pytest.MonkeyPatch, what: str) -> None:
    from tests.presentation import budget
    clock = SimpleNamespace(now=0.0)
    def sleep(seconds: float) -> None:
        assert seconds >= 0
        clock.now += seconds
    monkeypatch.setattr(budget, 'time', SimpleNamespace(monotonic=lambda: clock.now, sleep=sleep,
        process_time_ns=time.process_time_ns, perf_counter_ns=time.perf_counter_ns))
    draw = budget.Caller.draw
    def costly_draw(caller: budget.Caller, now: float) -> dict[str, object] | None:
        frame = draw(caller, now)
        clock.now += .03  # Simulated render cost must not reduce the five-Hz walk.
        return frame
    monkeypatch.setattr(budget.Caller, 'draw', costly_draw)
    measured = budget.activity(content, 132, 50, 'truecolor', what, 12)
    assert 59 <= measured['key_steps'] <= 60
    assert measured['successful_moves'] == measured['key_steps']
    assert 290 <= measured['successful_moves_per_minute'] <= 300


def test_blocked_walking_route_is_rejected(content: ContentTree, monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.presentation import budget
    clock = SimpleNamespace(now=0.0)
    def sleep(seconds: float) -> None:
        clock.now += seconds
    monkeypatch.setattr(budget, 'time', SimpleNamespace(monotonic=lambda: clock.now, sleep=sleep,
        process_time_ns=time.process_time_ns, perf_counter_ns=time.perf_counter_ns))
    monkeypatch.setitem(budget.KEYS, 'walking in a scene place', ['up'])
    with pytest.raises(AssertionError, match='must execute every step'):
        budget.activity(content, 132, 50, 'truecolor', 'walking in a scene place', 3)


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


def test_entities_1_11_absent_cell_dialogue_keeps_baseline_but_binding_is_guarded(content: ContentTree) -> None:
    from tests.presentation.mechanics import projection
    baseline = projection(content)
    sid, sector = next(iter(content.sectors.items()))
    assert all('dialogue' not in cell for cell in baseline['sectors'][sid]['cells'])
    changed = deepcopy(content)
    changed.sectors[sid] = replace(sector, cells=(replace(sector.cells[0], dialogue='ninety-nine'), *sector.cells[1:]))
    assert projection(changed) != baseline


def test_cp437_gate_rejects_unprovenanced_unicode(tmp_path: Path) -> None:
    terminal = FakeTerminal()
    terminal.write('┆界'.encode('utf-8'))
    problems = cp437_problems(terminal)
    assert [p['codepoints'] for p in problems] == [['U+2506'], ['U+754C']]
    write_packet(tmp_path, terminal, {'scenario': 'strict-cp437'})
    assert json.loads((tmp_path/'context.json').read_text(encoding='utf-8'))['cp437_pass'] is False


def test_caller_provenance_excludes_only_input_cells_and_preserves_authored_identical_text(
        caller_provenance: None, tmp_path: Path) -> None:
    info = DoorInfo(tmp_path/'unused', tmp_path, {'handle': WIDE_HANDLE.text}, 80, 24, '256', 3600)
    display = Display(info)
    display.receive(Frame('view', {'rev': 1, 'kind': 'text',
        'body': {'title': 'AUTHORED', 'lines': [WIDE_HANDLE.text]}}), 0)
    terminal = FakeTerminal()
    terminal.write(display.render(0)[0])
    problems = cp437_problems(terminal)
    assert len(problems) == 1 and problems[0]['codepoints'] == ['U+754C']
    assert problems[0]['y'] != 0  # Identical body text stays authored.
    assert len(terminal.caller_cells) == 6  # Four ASCII cells plus both wide cells.
    assert {(x, y) for x, y in terminal.caller_cells if y != 0} == set()
    write_packet(tmp_path/'packet', terminal, {'scenario': 'source-not-character'})
    report = json.loads((tmp_path/'packet/context.json').read_text(encoding='utf-8'))
    assert report['caller_input_cell_count'] == 6
    assert report['cp437_pass'] is False
    # An ordinary redraw must clear provenance where input is no longer
    # present, while the identical authored line remains checked.
    display.info = replace(info, raw={'handle': 'plain'})
    display.dirty = True
    terminal.write(display.render(1)[0])
    assert not terminal.caller_cells
    assert len(cp437_problems(terminal)) == 1


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
