"""S44 part 5: the price as notices, and HUNTED in the header (terminal UI 2.1, 2.5)."""

from dataclasses import replace

import pytest

from karst41.content.loader import load_content
from karst41.door.cells import display_width
from karst41.door.layout import compute
from karst41.door.model import Display
from karst41.door.present.chrome import NOTICE_SECONDS
from karst41.server.npcs.templates import PROVOCATION_SECONDS
from karst41.server.protocol import Frame
from karst41.server.rules.combat import MARKED_SECONDS
from tests.character_helpers import create, place
from tests.fake_terminal import FakeTerminal
from tests.harness import HeadlessServer
from tests.presentation.snapshots import assert_golden

# Canon text, word for word (terminal UI 2.1); numbers from the constants.
ARRIVAL = "Fire: {} comes, no Halo. At a player: Marked {}m, no work."
AT_PLAYER = "Fire: Marked {}m. No Halo, no work."
AT_NPC = "Fire here and {} comes. No Halo."


def toasts(frames):
    return [frame.data for frame in frames if frame.type == "toast"]


def arrive(repo_root, width=80, height=24):
    game = HeadlessServer(load_content(repo_root/"src/karst41/content"), character_state={})
    caller = game.connect({"user_id": 1, "handle": "Price", "node_name": "S44"}, width=width, height=height)
    create(game, caller, card="none")
    game.frames_for(caller)
    place(game, caller, "sodium-row", (25, 3))
    game.core.characters.sim.discover(caller.session, game.core.characters.sim.avatars[caller.session.user_id])
    return game, caller


def test_s44_arrival_price_notice_once_per_character_from_constants(repo_root):
    game, caller = arrive(repo_root)
    shown = toasts(game.frames_for(caller))
    text = ARRIVAL.format("Sable", MARKED_SECONDS // 60)
    assert [t["text"] for t in shown] == [text] and shown[0]["price"] is True
    # A new Wake (minutes old) sees it at once: a price is never held back.
    assert "15m" in text and str(PROVOCATION_SECONDS // 60) not in text.replace("15m", "")
    avatar = game.core.characters.sim.avatars[caller.session.user_id]
    place(game, caller, "core-plaza", (30, 30))
    place(game, caller, "sodium-row", (25, 3))
    game.core.characters.sim.discover(caller.session, avatar)
    assert not toasts(game.frames_for(caller))


def view(me, target=None, kind="zone"):
    body = {"me": {"zone_name": "Sodium Row", "safety": "contested", "clock": "21:00", **me}}
    if target is not None:
        body["target"] = target
    return Frame("view", {"rev": 1, "kind": kind, "body": body})


@pytest.mark.parametrize("presentation", [False, True])
@pytest.mark.parametrize("warning,text", [
    ("Firing marks you", AT_PLAYER.format(MARKED_SECONDS // 60)),
    ("Truce: Sable answers", AT_NPC.format("Sable")),
    ("Sable answers", AT_NPC.format("Sable")),
])
def test_s44_first_target_notice_once_per_session(info, presentation, warning, text):
    display = Display(info, presentation=presentation)
    display.receive(view({"truce": "Sable"}, {"warning": warning}), 1)
    assert display.toast[0] == text
    display.toast = None
    display.receive(view({"truce": "Sable"}, {"warning": warning}), 2)
    display.receive(view({"truce": "Sable"}, {"warning": "Firing marks you"}), 3)
    assert display.toast is None


def test_s44_no_target_notice_outside_a_truce_zone(info):
    display = Display(info, presentation=True)
    display.receive(view({}, {"warning": "Firing marks you"}), 1)
    assert display.toast is None and not display.price_noticed


def test_s44_price_notice_held_in_header_counts_from_its_return(info):
    display = Display(info, presentation=True)
    threatened = {"warning": "Firing marks you", "relation": "hostile"}
    display.receive(view({"truce": "Sable"}, threatened), 0)
    assert display._notice_to_header(0)
    display.update(30, 30)
    display.key("x", 30)  # A key while it sits in the header doesn't count.
    assert display.toast is not None
    display.receive(view({"truce": "Sable"}, {"warning": "", "relation": "neutral"}), 31)
    display.update(31, 31)
    assert display.toast is not None and display.toast[2] >= 31 + NOTICE_SECONDS - 1
    display.key("x", 32)
    display.update(32 + NOTICE_SECONDS, 32 + NOTICE_SECONDS)
    assert display.toast is None


@pytest.mark.parametrize("me", [{"hunted": True}, {"marked_until": "2999-01-01T00:00:00+00:00"},
                                {"hunted": True, "marked_until": "2999-01-01T00:00:00+00:00"}])
def test_s44_hunted_or_marked_alone_is_not_threatened(info, me):
    display = Display(info, presentation=True)
    display.receive(view({"truce": "Sable", **me}), 0)
    assert not display._notice_to_header(0)


def test_s44_every_shipped_keeper_name_fits_the_price_lines(repo_root):
    content = load_content(repo_root/"src/karst41/content")
    layout = compute(80, 24)
    header = layout.header.width // 2  # The notice's room in the header (P4).
    hint = layout.hint.width
    keepers = {zone.meta.truce for zone in content.zones.values() if zone.meta.truce}
    assert keepers == {"sable"}
    for keeper in keepers:
        name = content.factions[keeper].short
        assert display_width(AT_NPC.format(name)) <= header, name
        assert display_width(AT_PLAYER.format(MARKED_SECONDS // 60)) <= header
        assert display_width(ARRIVAL.format(name, MARKED_SECONDS // 60)) <= hint, name
    # The target line holds names of 6 cells or fewer; any longer name fails.
    assert display_width(AT_NPC.format("x" * 6)) <= header < display_width(AT_NPC.format("x" * 7))


def test_s44_header_cuts_with_ascii_dots(info):
    from karst41.door.cells import truncate
    assert truncate(AT_NPC.format("Sable"), 20) == "Fire here and Sab..."


def hunted_screen(repo_root, info, width, height, tier, presentation):
    content = load_content(repo_root/"src/karst41/content")
    content.zones = {key: replace(zone, meta=replace(zone.meta, spawners=())) for key, zone in content.zones.items()}
    game = HeadlessServer(content, character_state={})
    caller = game.connect({"user_id": 1, "handle": "Hunted界", "node_name": "S44"}, width=width, height=height)
    create(game, caller, card="none")
    place(game, caller, "sodium-row", (25, 3))
    player = game.core.characters.players[caller.session.player_id]
    from karst41.server import truce as truce_rules
    now = game.core.combat.now()
    player.keeper_answer = {"keeper": "sable", "zone": "sodium-row", "until": truce_rules.iso(now + PROVOCATION_SECONDS)}
    player.marked_until = player.truce_marked_until = truce_rules.iso(now + MARKED_SECONDS)
    game.step(2)
    display = Display(replace(info, width=width, height=height, color_depth=tier), presentation=presentation)
    for frame in game.frames_for(caller):
        display.receive(frame, 0)
        if frame.type == "prompt":
            display.key("enter", 0)
    display.toast = None
    display.update(20, 20)
    terminal = FakeTerminal(width, height)
    terminal.write(display.render(20)[0])
    return display, terminal


@pytest.mark.parametrize("width,height", [(80, 24), (132, 50)])
@pytest.mark.parametrize("tier", ["16", "256", "truecolor"])
@pytest.mark.parametrize("presentation", [False, True])
def test_s44_hunted_header_golden(repo_root, info, request, width, height, tier, presentation):
    display, terminal = hunted_screen(repo_root, info, width, height, tier, presentation)
    assert display.body["me"]["hunted"] is True
    top = terminal.screen_text().splitlines()[0]
    assert "HUNTED" in top
    if presentation:
        assert top.index("MARKED") < top.index("HUNTED")
    assert_golden(repo_root/"tests/presentation/golden/s44-hunted",
                  f"s44_hunted_{'present' if presentation else 'legacy'}_{width}x{height}_{tier}", terminal, tier,
                  trim=True, update=request.config.getoption("--update-goldens"))


def test_s44_hunted_drops_no_earlier_than_marked_or_heat(info):
    display = Display(replace(info, width=80, height=24), presentation=True)
    me = {"zone_name": "A Very Long Zone Name Indeed For Testing Drops", "safety": "contested", "truce": "Sable",
          "heat_until": "x", "marked_until": "x", "hunted": True, "district": "Lower Ring", "clock": "21:00",
          "zone": "sodium-row", "hp": 10, "hp_max": 10, "sta": 10, "sta_max": 10, "grade": 1, "name": "Runner"}
    display.receive(Frame("view", {"rev": 1, "kind": "zone", "body": {
        "me": me, "service": {"summary": "service summary"}, "hint": "", "tiles": [], "actors": []}}), 0)
    from karst41.door.cells import CellBuffer
    from karst41.door.present import zone
    buffer = CellBuffer(80, 24, display.palette.style())
    zone.head(buffer, display.body, display.layout, display.paint)
    terminal = FakeTerminal(80, 24)
    terminal.write(buffer.diff(None) if hasattr(buffer, "diff") else b"")
    top = terminal.screen_text().splitlines()[0] if terminal.screen_text() else ""
    for fact in ("HEAT", "MARKED", "HUNTED"):
        assert fact in top, top
    assert "LOWER RING" not in top and "service summary" not in top


@pytest.mark.parametrize("presentation", [False, True])
def test_s44_real_server_warning_drives_the_first_target_notice(repo_root, info, presentation):
    """Pins the door's match to the server's own TARGET wording (review 6817177879)."""
    game, caller = arrive(repo_root)
    zone = game.core.world.zones["sodium-row"]
    source = game.core.world.actors[caller.session.player_id]
    target = next(a for a in zone.actors.values() if a.behaviour.get("template") == "npc-sodium-regular")
    game.core.world.enter(target, zone.id, game.core.world.free_tile(zone.id, (27, 3), target))
    source.target = target.id
    game.step()
    assert game.core.combat.target_view(source)["warning"] == "Truce: Sable answers"
    display = Display(info, presentation=presentation)
    for frame in game.frames_for(caller):
        if frame.type != "toast":  # Only the TARGET path, not the arrival notice.
            display.receive(frame, 0)
    assert display.price_noticed and display.toast[0] == AT_NPC.format("Sable")


@pytest.mark.parametrize("presentation", [False, True])
def test_s44_price_notice_waits_behind_an_unread_notice(info, presentation):
    """Review 6817410615: a price notice queues instead of replacing one."""
    display = Display(info, presentation=presentation)
    arrival = ARRIVAL.format("Sable", MARKED_SECONDS // 60)
    display.receive(Frame("toast", {"text": arrival, "role": "warning", "seconds": 4, "kind": "notice",
                                    "price": True}), 0)
    display.receive(view({"truce": "Sable"}, {"warning": "Truce: Sable answers"}), 1)
    assert display.toast[0] == arrival  # The arrival notice is still being read.
    display.key("x", 2)
    display.update(NOTICE_SECONDS + 1, NOTICE_SECONDS + 1)
    assert display.toast[0] == AT_NPC.format("Sable")
