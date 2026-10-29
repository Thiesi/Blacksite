"""S13 layouts through the real display and independent ANSI terminal."""

from copy import deepcopy
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from blacksite.content.loader import load_content
from blacksite.door.model import Display
from blacksite.server.protocol import Frame, encode
from tests.character_helpers import act, create, place
from tests.fake_terminal import FakeTerminal
from tests.harness import HeadlessServer


@pytest.fixture(scope="module")
def sector_views():
    content = load_content(Path(__file__).parents[2]/"src/blacksite/content")
    game = HeadlessServer(content, character_state={})
    callers = []
    for uid, name, tile in ((1, "First", (30, 5)), (2, "Runner界", (31, 6))):
        caller = game.connect({"user_id": uid, "handle": f"BBS界{uid}", "node_name": "test"})
        create(game, caller, archetype=0, name=name, card="none")
        place(game, caller, "core-plaza", tile)
        act(game, caller, Frame("key", {"k": "j", "t": 0}))
        game.commit_commerce()  # Commit the authored entrance-cell discovery.
        callers.append(caller)
    lattice = game.core.lattice
    views = {}
    for sid, sector in lattice.sectors.records.items():
        for caller in callers:
            player = game.core.characters.players[caller.session.player_id]
            lattice.saved(player)["found_cells"] = {sid: [cell.id for cell in sector.cells]}
            presence = lattice.presences[player.id]
            presence.sector, presence.cell = sid, lattice.sectors.entrance(sid)
        views[sid] = lattice.view(callers[0].session, lattice.presences[callers[0].session.player_id])
    return content, views


def draw(info, content, body, width, height, tier):
    display = Display(replace(info, width=width, height=height, color_depth=tier), glyphs=content.glyphs.glyphs)
    display.receive(Frame("welcome", {"keymap": asdict(content.keymaps), "palette": asdict(content.palette)}), 0)
    frame = Frame("view", {"rev": 1, "kind": "lattice", "body": body})
    encode(frame)
    display.receive(frame, 1)
    terminal = FakeTerminal(width, height)
    terminal.write(display.render(1)[0])
    return display, terminal


@pytest.mark.parametrize("size", [(80, 24), (132, 50)])
@pytest.mark.parametrize("tier", ["16", "256", "truecolor"])
def test_design_ui_3_all_eleven_layouts_no_overlap_and_wide_peer(info, sector_views, size, tier):
    content, views = sector_views
    width, height = size
    for body in views.values():
        display, terminal = draw(info, content, body, width, height, tier)
        screen = terminal.screen_text()
        assert "INTEGRITY 100" in screen and "TRACE 0" in screen and "BODY SAFE" in screen
        assert "Runner界" in screen and "Pick" in screen and "Umbrella" in screen
        positions = set()
        area = display.layout.viewport
        columns, rows = body["layout_size"]
        for cell in body["cells"]:
            x = area.x+1+cell["x"]*(area.width-6)//(columns-1)
            y = area.y+1+cell["y"]*(area.height-3)//(rows-1)
            occupied = {(px, y) for px in range(x, x+4)}
            assert not positions.intersection(occupied)
            positions.update(occupied)
            assert terminal.cell(x, y) in ("(", "[")
            assert terminal.cell(x+3, y) in (")", "]")
        if tier == "256":
            expected = Path(__file__).with_name("golden")/f"lattice_{body['sector']}_{width}x{height}.txt"
            assert terminal.screen_text()+"\n" == expected.read_text(encoding="utf-8")


def test_body_hits_and_escape_are_visible_while_jacked(info, sector_views):
    content, views = sector_views
    body = deepcopy(views["lat-core"])
    display, terminal = draw(info, content, body, 80, 24, "256")
    normal = terminal.styles[(0, 0)]
    body["me"].update(hit_serial=1, body_hp=100, escape_ticks=15, interruptions=2)
    display.receive(Frame("view", {"rev": 2, "kind": "lattice", "body": body}), 2)
    terminal.write(display.render(2)[0])
    assert "ESCAPE 1.5s" in terminal.screen_text() and "Interruptions 2/3" in terminal.screen_text()
    assert "HP 100/" in terminal.screen_text() and terminal.styles[(0, 0)] != normal
    terminal.write(display.render(2.2)[0])
    assert terminal.styles[(0, 0)] == normal
    assert display.key("up", 3)[0].data["k"] == "up"
    assert display.key("7", 4)[0].data["k"] == "7"


@pytest.mark.parametrize('size', [(80, 24), (132, 50)])
@pytest.mark.parametrize('tier', ['16', '256', 'truecolor'])
def test_issue_67_fractional_ice_numbers_are_compact_without_changing_state(info, sector_views, size, tier):
    content, views = sector_views
    body = deepcopy(views['lat-core'])
    body['room'] = {'ice': [{'id': 'fractional-ice', 'name': 'Sandman',
        'integrity': 19.9925, 'maximum': 40, 'phase': 'idle', 'role': 'sentinel',
        'trigger': 'active', 'damage': 10.0075, 'meat': 0, 'counter': 'Move or shield.'}],
        'data': [], 'controls': []}
    body['me'].update(target='fractional-ice', integrity=19.9925)
    original = deepcopy(body)
    _, terminal = draw(info, content, body, *size, tier)
    screen = terminal.screen_text()
    assert '19.99/40' in screen and '10.01 integrity' in screen
    assert 'INTEGRITY 19.99/100' in screen
    assert '19.9925' not in screen and '10.0075' not in screen
    assert body == original
