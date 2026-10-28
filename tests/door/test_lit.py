"""V0 spike (#68): the Tin Halo lit at eye level from its look.

What the review checks: figures come only from disclosed actors, dressing
never stands where the map shows nothing, scenes stay trial-only and
never leave known ground, and every tier replays cleanly.
"""

import json
import random
import shutil
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from blacksite.content.loader import load_content
from blacksite.content.validate import validate
from blacksite.door.cells import CellBuffer, display_width
from blacksite.door.layout import Rect
from blacksite.door.model import Display
from blacksite.door.palette import Palette
from blacksite.door.present import lit
from blacksite.door.present.paint import Paint
from blacksite.server.protocol import Frame
from blacksite.server.views import looks
from tests.fake_terminal import FakeTerminal
from tests.harness import HeadlessServer
from tests.server.test_looks import move

ROOT = Path(__file__).parents[2]
CONTENT = ROOT / "src/blacksite/content"
CANDIDATE = ROOT / "docs/design/proposals/68-presentation/candidates/sodium-row"
SPOT = (4, 10)


@pytest.fixture(scope="module")
def content():
    return load_content(CONTENT, CANDIDATE)


@pytest.fixture
def trial(monkeypatch):
    monkeypatch.setattr(looks, "TRIAL", True)


def halo(info, content, width=132, height=50, tier="truecolor", glyphs="modern", ticks=40):
    game = HeadlessServer(content, "sodium-tin-halo")
    client = game.connect(width=width, height=height)
    game.step()
    move(game, client, "sodium-tin-halo", SPOT)
    display = Display(replace(info, width=width, height=height, color_depth=tier))
    display.receive(Frame("welcome", {"keymap": asdict(content.keymaps), "palette": asdict(content.palette)}), 0)
    display.present, display.view_mode, display.glyphs, display.heading = True, "scene", glyphs, "right"
    for _ in range(ticks):
        game.step()
        for frame in game.frames_for(client):
            for out in display.receive(frame, 1):
                client.send(out)
    return game, client, display


def picture(display, body, glyphs="modern", tier="truecolor", columns=100, rows=18):
    paint = Paint(Palette({"roles": display.palette.roles}, tier), glyphs)
    buffer = CellBuffer(columns, rows)
    assert lit.render(buffer, body, Rect(0, 0, columns, rows), paint, "right", hud=False)
    return buffer, paint


def cells(buffer):
    return [[(c.glyph, c.style) for c in row] for row in buffer.cells]


def test_content_with_the_v0_look_validates(content) -> None:
    assert validate(content) == []
    look = content.looks["sodium-tin-halo"]
    assert look.scene is not None and look.scene.lights and look.scene.pieces


def test_scene_is_trial_only(info, content, monkeypatch) -> None:
    monkeypatch.setattr(looks, "TRIAL", False)
    _, _, display = halo(info, content, ticks=4)
    assert "scene" not in display.body
    monkeypatch.setattr(looks, "TRIAL", True)
    _, _, display = halo(info, content, ticks=4)
    assert display.body["scene"]["lights"] and display.body["scene"]["pieces"]


def test_scene_sends_only_dressing_on_known_ground(content, trial) -> None:
    look = content.looks["sodium-tin-halo"]
    known = lambda tile: tile[0] < 10
    sent = looks.scene(look, known)
    assert sent is not None and sent["pieces"] and len(sent["pieces"]) < len(look.scene.pieces)
    for piece in sent["pieces"]:
        x, y, w, h = piece["rect"]
        assert x + w <= 10, piece  # clipped to the known tiles
    kinds = {p["kind"] for p in sent["pieces"]}
    assert "counter" in kinds and "sign" not in kinds  # a counter is clipped; a sign goes whole or not at all
    assert all(light["at"][0] < 10 for light in sent["lights"])
    assert looks.scene(look, lambda tile: False) == {**looks.scene(look, lambda tile: False), "lights": [], "pieces": []}


def write_look(tmp_path: Path, change) -> Path:
    local = tmp_path / "local"
    shutil.copytree(CANDIDATE, local)
    path = local / "looks/sodium-tin-halo.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    change(data["scene"])
    path.write_text(json.dumps(data), encoding="utf-8")
    return local


def test_validator_refuses_an_obstacle_the_map_does_not_have(tmp_path) -> None:
    local = write_look(tmp_path, lambda sc: sc["pieces"].append({"kind": "box", "rect": [3, 10, 1, 1], "z": [0, 1]}))
    problems = [p.message for p in validate(load_content(CONTENT, local))]
    assert any("stands in the way on open ground at [3, 10]" in p for p in problems), problems


def test_overhead_dressing_and_floor_marks_may_go_anywhere(tmp_path) -> None:
    def add(sc):
        sc["pieces"].append({"kind": "pipe", "rect": [3, 10, 6, 0.3], "z": [2.8, 3.0]})
        sc["pieces"].append({"kind": "box", "rect": [3, 11, 2, 1], "z": [0, 0.1]})
    assert validate(load_content(CONTENT, write_look(tmp_path, add))) == []


def test_validator_checks_scene_colours_and_lights(tmp_path) -> None:
    def spoil(sc):
        sc["walls"] = "brown"
        sc["lights"].append({"at": [99, 2], "z": 1.0, "colour": "#ffffff", "reach": 3})
    problems = [p.message for p in validate(load_content(CONTENT, write_look(tmp_path, spoil)))]
    assert any("'brown'" in p for p in problems) and any("light at [99, 2]" in p for p in problems)


def test_people_are_drawn_only_from_the_views_actors(info, content, trial) -> None:
    _, _, display = halo(info, content)
    body = json.loads(json.dumps(display.body))
    alone = {**body, "actors": [a for a in body["actors"] if a.get("role") == "player_self"]}
    base, _ = picture(display, alone)
    # Anything that is not an actor in the view draws nobody: names in
    # NEARBY, objects, unknown keys.
    rumour = {**alone, "nearby": [{"id": "ghost", "name": "Ghost", "relation": "~", "role": "npc_sable"}],
              "hidden": [{"id": "ghost", "x": SPOT[0] + 3, "y": SPOT[1], "role": "npc_sable"}]}
    assert cells(picture(display, rumour)[0]) == cells(base)
    # Each actor changes only the columns where it stands.
    rng = random.Random(68)
    me = next(a for a in body["actors"] if a.get("role") == "player_self")
    seen = 0
    for _ in range(12):
        x, y = SPOT[0] + rng.randint(2, 14), SPOT[1] + rng.randint(-5, 4)
        stranger = {"id": "s", "x": x, "y": y, "role": rng.choice(["npc_sable", "npc_neutral", "player_neutral"]),
                    "kind": "npc"}
        drawn, _ = picture(display, {**alone, "actors": [*alone["actors"], stranger]})
        changed = {col for row_a, row_b in zip(cells(drawn), cells(base))
                   for col, (a, b) in enumerate(zip(row_a, row_b)) if a != b}
        cam = lit.camera(me, 100, 18, True, "right")
        spot = cam.project(x + 0.5, y + 0.5, 0.0)
        if spot is None:
            assert not changed
            continue
        half = 0.3 * cam.focal_x / spot[2] * 1.1
        low, high = (spot[0] - half) / 2 - 1, (spot[0] + half) / 2 + 1
        assert all(low <= col <= high for col in changed), (stranger, sorted(changed), low, high)
        seen += bool(changed)
    assert seen >= 6  # the strangers in view were drawn


def test_a_faction_mark_comes_from_the_disclosed_role(info, content, trial) -> None:
    _, _, display = halo(info, content)
    body = json.loads(json.dumps(display.body))
    alone = [a for a in body["actors"] if a.get("role") == "player_self"]
    near = {"id": "s", "x": SPOT[0] + 3, "y": SPOT[1], "kind": "npc"}
    sable, _ = picture(display, {**body, "actors": [*alone, {**near, "role": "npc_sable"}]})
    plain, _ = picture(display, {**body, "actors": [*alone, {**near, "role": "npc_neutral"}]})
    assert cells(sable) != cells(plain)


@pytest.mark.parametrize("glyphs,tier", [("modern", "truecolor"), ("modern", "256"), ("cp437", "truecolor"),
                                         ("cp437", "256"), ("cp437", "16"), ("modern", "16")])
def test_sextants_only_in_the_modern_tier(info, content, trial, glyphs, tier) -> None:
    _, _, display = halo(info, content, ticks=4)
    buffer, _ = picture(display, display.body, glyphs, tier)
    used = {c.glyph for row in buffer.cells for c in row}
    sextants = {g for g in used if g and 0x1FB00 <= ord(g) <= 0x1FB3B}
    if glyphs == "modern" and tier != "16":
        assert sextants
    else:
        assert not sextants and used <= {" ", "▀", *"TINHALO"}, used - {" ", "▀"}
    assert all(display_width(g) == 1 for g in used if g)


def test_every_sextant_pattern_has_a_single_width_glyph() -> None:
    glyphs = {lit.sextant(p) for p in range(64)}
    assert len(glyphs) == 64
    for pattern in range(64):
        glyph = lit.sextant(pattern)
        assert display_width(glyph) == 1
        if 0x1FB00 <= ord(glyph) <= 0x1FB3B:  # decode as a terminal would
            back = ord(glyph) - 0x1FB00 + 1
            back += back >= 21
            back += back >= 42
            assert back == pattern


@pytest.mark.parametrize("width,height", [(80, 24), (132, 50)])
@pytest.mark.parametrize("glyphs,tier", [("modern", "truecolor"), ("cp437", "256"), ("cp437", "16")])
@pytest.mark.parametrize("mode", ["scene", "street"])
def test_lit_views_replay_cleanly(info, content, trial, width, height, glyphs, tier, mode) -> None:
    _, _, display = halo(info, content, width, height, tier, glyphs, ticks=6)
    display.view_mode = mode
    display.force_full = display.dirty = True
    display.last_render = -1
    terminal = FakeTerminal(width, height)
    terminal.write(display.render(50.0)[0])  # asserts no bottom-right write and no stray controls
    text = terminal.screen_text()
    assert "The Tin Halo" in text and ("WAYS" in text if mode == "scene" else "facing" in text)


def test_a_threat_still_takes_the_screen(info, content, trial) -> None:
    _, _, display = halo(info, content, ticks=4)
    display.body["nearby"] = [{"id": "x", "name": "Hostile", "relation": "!", "role": "npc_hostile"}]
    display.force_full = display.dirty = True
    display.last_render = -1
    terminal = FakeTerminal(132, 50)
    terminal.write(display.render(50.0)[0])
    assert "TACTICAL" in terminal.screen_text()


def test_a_place_without_a_scene_keeps_the_street_view(info, content, trial) -> None:
    _, _, display = halo(info, content, ticks=4)
    body = {k: v for k, v in display.body.items() if k != "scene"}
    assert not lit.render(CellBuffer(40, 10), body, Rect(0, 0, 40, 10), Paint(display.palette, "modern"), "right")
