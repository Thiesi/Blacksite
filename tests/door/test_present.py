"""Proposal 68 renderer: real views, both sizes, three tiers, replayed."""

from dataclasses import asdict, replace
from pathlib import Path

import pytest

from blacksite.content.loader import load_content
from blacksite.door.model import Display
from blacksite.door.present import chrome, screen
from blacksite.server.protocol import Frame
from tests.door.test_lattice_render import sector_views  # noqa: F401  (module fixture)
from tests.fake_terminal import FakeTerminal
from tests.harness import HeadlessServer
from tests.server.test_looks import move

ROOT = Path(__file__).parents[2]
SIZES = [(80, 24), (132, 50)]
TIERS = ["16", "256", "truecolor"]


@pytest.fixture(scope="module")
def content():
    return load_content(ROOT / "src/blacksite/content")


def zone_frames(content, zone: str, tile: tuple[int, int], width: int, height: int):
    game = HeadlessServer(content, zone)
    client = game.connect(width=width, height=height)
    game.step()
    move(game, client, zone, tile)
    return game, client, list(game.frames_for(client))


def shown(info, content, frames, width, height, tier, *, present=True, now=9.0):
    display = Display(replace(info, width=width, height=height, color_depth=tier))
    display.receive(Frame("welcome", {"keymap": asdict(content.keymaps), "palette": asdict(content.palette)}), 0)
    for frame in frames:
        display.receive(frame, 1)
    display.present = present
    display.update(9, now)
    terminal = FakeTerminal(width, height)  # rejects controls and the bottom-right cell
    terminal.write(display.render(now)[0])
    return display, terminal


@pytest.mark.parametrize("width,height", SIZES)
@pytest.mark.parametrize("tier", TIERS)
@pytest.mark.parametrize("zone,tile", [("core-plaza", (57, 6)), ("sodium-row", (34, 12)), ("vatside-clinics", (46, 3)),
                                       ("vatside-wake-hall", (5, 5))])
def test_zone_frames_replay_at_every_size_and_tier(info, content, zone, tile, width, height, tier) -> None:
    _, _, frames = zone_frames(content, zone, tile, width, height)
    display, terminal = shown(info, content, frames, width, height, tier, now=20)
    text = terminal.screen_text()
    me = display.body["me"]
    assert me["zone_name"] in text and me["safety"].upper() in text
    assert "HP" in text and "STA" in text and "SHK" in text and "@" in text
    double = me["safety"] in ("safe", "pocket")
    assert text.splitlines()[0][0] == ("╔" if double else "┌")


@pytest.mark.parametrize("width,height", SIZES)
@pytest.mark.parametrize("tier", TIERS)
def test_every_sector_draws_as_linework(info, content, sector_views, width, height, tier) -> None:  # noqa: F811
    _, views = sector_views
    for sid, body in views.items():
        display, terminal = shown(info, content, [Frame("view", {"rev": 1, "kind": "lattice", "body": body})],
                                  width, height, tier)
        text = terminal.screen_text()
        here = next(c for c in body["cells"] if c["id"] == body["me"]["cell"])
        assert "RUNNER" in text and "BODY" in text and "RIG" in text, sid
        assert "@ " + here["label"][:10] in text, sid
        assert "(01)" not in text  # names, not numbers


def test_f7_switches_renderer_on_the_same_view(info, content) -> None:
    _, _, frames = zone_frames(content, "core-plaza", (57, 6), 80, 24)
    display, terminal = shown(info, content, frames, 80, 24, "256", present=False)
    assert "THE CORE" not in terminal.screen_text()
    assert display.key("f7", 10) == []
    terminal.write(display.render(10)[0])
    assert "THE CORE" in terminal.screen_text() and display.present


def test_place_card_on_entry_closes_on_any_key_which_still_acts(info, content) -> None:
    _, _, frames = zone_frames(content, "core-plaza", (57, 6), 80, 24)
    display, terminal = shown(info, content, frames, 80, 24, "256", now=1.5)
    assert "M E R I D I A N" in terminal.screen_text()
    sent = display.key("left", 2)
    assert sent and sent[0].type == "key"  # the move is not swallowed
    terminal.write(display.render(2)[0])
    assert "M E R I D I A N" not in terminal.screen_text()


def test_place_card_never_covers_a_threat(info, content) -> None:
    _, _, frames = zone_frames(content, "core-plaza", (57, 6), 80, 24)
    display, _ = shown(info, content, frames, 80, 24, "256", now=1.5)
    display.body["nearby"] = [{"id": "x", "name": "Hostile", "relation": "!", "role": "npc_hostile"}]
    display.card_until = 1e9
    display.dirty = True
    terminal = FakeTerminal(80, 24)
    terminal.write(display.render(3)[0])
    assert "M E R I D I A N" not in terminal.screen_text() and display.card_until == 0


def test_log_coalesces_repeats_and_merges_xp() -> None:
    at = "2026-10-25T12:00:0{}+00:00"
    lines = [{"channel": "system", "role": "ui_text", "text": "Select a visible target with Tab.", "at": at.format(i)}
             for i in range(5)]
    lines += [{"channel": "zone", "role": "ui_text", "text": "You gain 5 XP.", "at": at.format(6)},
              {"channel": "zone", "role": "ui_text", "text": "You gain 10 XP.", "at": at.format(7)},
              {"channel": "zone", "role": "warning", "text": "Wardens: lower your weapon.", "at": at.format(8)}]
    assert chrome.digest(lines) == [("system", "Select a visible target with Tab. (x5)"), ("system", "15 XP"),
                                    ("danger", "Wardens: lower your weapon.")]


def test_threat_test_reads_only_authorized_fields() -> None:
    assert not screen.threatened({"me": {}, "nearby": [{"relation": "~"}]})
    assert screen.threatened({"me": {}, "hazards": [{"warning": 3}]})
    assert screen.threatened({"me": {"in_combat": True}})
