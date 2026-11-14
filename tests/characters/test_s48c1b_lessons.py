"""S48c1b: the Wake lessons on the provisional body (#220 beats 6-9; game design 17)."""

from copy import deepcopy
from pathlib import Path

from karst41.door.doorinfo import DoorInfo
from karst41.door.model import Display
from karst41.server.protocol import Frame
from tests.character_helpers import act, create, place, state
from tests.fake_terminal import FakeTerminal
from tests.harness import HeadlessServer

HALL = "vatside-wake-hall"
NEAR_DRONE = (22, 14)  # Within two tiles of the corridor door's training tile (23,14).
PISTOL = "wpn_hall_training_pistol"


def drone_of(game: HeadlessServer, pid: str):
    return next((a for a in game.core.world.actors.values() if a.owner == pid and a.behaviour.get("training")), None)


def approach(game: HeadlessServer, client) -> None:
    place(game, client, HALL, NEAR_DRONE)
    game.step(3)


def fight(game: HeadlessServer, client, ticks: int = 1200) -> None:
    combat, pid = game.core.combat, client.session.player_id
    actor = game.core.world.actors[pid]
    for _ in range(ticks):
        drone = drone_of(game, pid)
        if drone is None:
            return
        actor.target = drone.id
        combat.fire(pid)
        game.step()
    raise AssertionError("the training drone never fell")


def test_the_unread_body_fights_the_drone_with_the_training_pistol(game: HeadlessServer) -> None:
    client = game.connect()
    game.step(2)
    manager, combat, pid = game.core.characters, game.core.combat, client.session.player_id
    assert manager.unread(pid) and combat.weapon(manager.players[pid]) is None
    approach(game, client)
    drone = drone_of(game, pid)
    assert drone is not None
    item, weapon = combat.weapon(manager.players[pid])
    assert item.template == PISTOL and weapon.damage == 12 and weapon.ammo is None
    assert item.id not in manager.players[pid].inventory and item.id not in combat.commerce.items
    fight(game, client)
    assert combat.weapon(manager.players[pid]) is None  # Back on its hook.
    wake = manager.wakes[client.session.id]
    assert wake.lessons["drone"] == "done"
    assert manager.identities["1"]["wake"]["lessons"]["drone"] == "done"
    assert not [e for e in manager.outbox if e["action"] in ("save", "create")]
    # Applied at creation.
    create(game, client, name="Noor", card="none")
    assert manager.players[client.session.player_id].progress["wake_combat"] == "done"


def test_a_disconnect_mid_fight_leaves_the_lesson_open_and_a_redial_starts_it_fresh(game: HeadlessServer) -> None:
    manager, combat = game.core.characters, game.core.combat
    client = game.connect()
    game.step(2)
    pid = client.session.player_id
    approach(game, client)
    drone = drone_of(game, pid)
    drone.health = max(1, drone.health // 2)  # Mid-fight.
    game.core.sessions.disconnect(client.session)
    assert drone_of(game, pid) is None and pid not in combat.training_arms
    back = game.connect()
    # Before any tick: back on the saved tile, nothing in hand, no drone.
    assert back.session.player_id == pid
    assert drone_of(game, pid) is None and combat.weapon(manager.players[pid]) is None
    assert "drone" not in manager.wakes[back.session.id].lessons  # Unfinished, not skipped.
    game.step(2)  # The saved tile is near the drone's post, so it wakes again at once.
    fresh = drone_of(game, pid)
    assert fresh is not None and fresh.health == fresh.health_max
    assert combat.weapon(manager.players[pid])[0].template == PISTOL
    fight(game, back)
    assert manager.wakes[back.session.id].lessons["drone"] == "done"  # The win, not a skip.


def test_skipping_the_drone_puts_the_pistol_back(game: HeadlessServer) -> None:
    client = game.connect()
    game.step(2)
    manager, combat, pid = game.core.characters, game.core.combat, client.session.player_id
    approach(game, client)
    assert pid in combat.training_arms
    act(game, client, Frame("key", {"k": "b", "t": 0}))
    assert pid not in combat.training_arms and drone_of(game, pid) is None
    assert manager.wakes[client.session.id].lessons["drone"] == "skipped"


def logged(game: HeadlessServer, client) -> list[str]:
    return [line["text"] for f in game.frames_for(client) if f.type == "log" for line in f.data["lines"]]


def wakes_line(lines: list[str]) -> bool:
    return any(text.startswith("Your training drone wakes.") for text in lines)


def test_a_skipper_crossing_the_ring_wakes_nothing(game: HeadlessServer) -> None:
    """Creative lead beat (a): the drone wakes only for an unread body."""
    client = game.connect()
    create(game, client, name="Noor", card="none")  # The record read at the door: never fought.
    manager, combat = game.core.characters, game.core.combat
    player = manager.players[client.session.player_id]
    assert "wake_combat" not in player.progress
    game.frames_for(client)
    approach(game, client)
    game.step(40)
    assert drone_of(game, player.id) is None and player.id not in combat.training_arms
    assert "wake_combat" not in player.progress
    assert not wakes_line(logged(game, client))


def test_a_winner_coming_back_wakes_nothing(game: HeadlessServer) -> None:
    client = game.connect()
    game.step(2)
    manager = game.core.characters
    approach(game, client)
    fight(game, client)
    create(game, client, name="Noor", card="none")
    player = manager.players[client.session.player_id]
    assert player.progress["wake_combat"] == "done"
    place(game, client, "vatside-clinics", (30, 18))
    game.step(2)
    game.frames_for(client)
    approach(game, client)
    game.step(40)
    assert drone_of(game, player.id) is None
    assert player.progress["wake_combat"] == "done"
    assert not wakes_line(logged(game, client))


def test_a_character_never_wakes_the_drone_whatever_its_lesson_state(game: HeadlessServer) -> None:
    """By any route: even with no lesson recorded (a pre-S48 character), no drone."""
    client = game.connect()
    create(game, client, name="Noor", card="none")
    player = game.core.characters.players[client.session.player_id]
    player.progress.pop("wake_combat", None)
    approach(game, client)
    game.step(40)
    assert drone_of(game, player.id) is None and "wake_combat" not in player.progress


def armed_and_warned(game: HeadlessServer, client):
    """An unread body at the drone, past the drone's warning, the fight on."""
    game.step(2)
    approach(game, client)
    pid = client.session.player_id
    drone = drone_of(game, pid)
    assert drone is not None
    actor = game.core.world.actors[pid]
    for _ in range(200):
        game.step()
        if actor.health < actor.health_max:
            break
    assert actor.health < actor.health_max, "the drone should be firing"
    return pid, drone, actor


def test_the_drone_holds_fire_while_the_record_is_open_and_resumes_after(game: HeadlessServer) -> None:
    client = game.connect()
    manager = game.core.characters
    pid, drone, actor = armed_and_warned(game, client)
    actor.health = actor.health_max
    assert manager.open_record(client.session, "door")
    game.step(80)
    assert actor.health == actor.health_max  # Not one hit while the record is open.
    assert drone_of(game, pid) is drone and not drone.behaviour.get("inert")
    act(game, client, Frame("intent", {"name": "menu_close", "args": {}}))
    assert manager.wakes[client.session.id].stage == "hall"
    game.step(80)
    assert actor.health < actor.health_max  # Esc: the fight resumes unchanged.
    assert "drone" not in manager.wakes[client.session.id].lessons


def test_the_drone_holds_fire_at_the_name_prompt_too(game: HeadlessServer) -> None:
    client = game.connect()
    manager = game.core.characters
    pid, drone, actor = armed_and_warned(game, client)
    assert manager.open_record(client.session, "door")
    act(game, client, Frame("intent", {"name": "menu_select", "args": {}}))
    assert manager.wakes[client.session.id].stage == "name"
    actor.health = actor.health_max
    game.step(80)
    assert actor.health == actor.health_max


def test_reading_the_record_mid_fight_quiets_the_drone_and_holds_skipped(game: HeadlessServer) -> None:
    client = game.connect()
    manager, combat = game.core.characters, game.core.combat
    pid, drone, actor = armed_and_warned(game, client)
    assert combat.weapon(manager.players[pid])[0].template == PISTOL
    actor.target = drone.id
    effects = create(game, client, name="Noor", card="none")
    assert client.session.player_id == pid  # Promoted in place.
    player = manager.players[pid]
    assert drone_of(game, pid) is drone and drone.behaviour["inert"]  # Still drawn, never in a fight.
    assert pid not in combat.training_arms and combat.weapon(player)[0].template != PISTOL  # Reeled back.
    assert actor.target is None
    assert player.progress["wake_combat"] == "skipped"
    created = next(e for e in effects if e["action"] == "create")
    assert created["player"]["progress"]["wake_combat"] == "skipped"
    assert "training:" not in str(created)
    health = actor.health
    game.step(80)
    assert actor.health >= health  # It never fires again.
    assert drone_of(game, pid) is drone


def test_a_characters_inert_drone_is_no_target_and_writes_nothing(game: HeadlessServer) -> None:
    client = game.connect()
    manager, combat = game.core.characters, game.core.combat
    pid, drone, actor = armed_and_warned(game, client)
    create(game, client, name="Noor", card="none")
    player = manager.players[pid]
    progress = deepcopy(player.progress)
    health = drone.health
    outbox = len(manager.outbox)
    game.frames_for(client)
    act(game, client, Frame("key", {"k": "tab", "t": 0}))
    assert actor.target != drone.id
    combat.select(actor)
    assert actor.target != drone.id
    combat.fire(pid, drone.id)
    assert "Select a visible target with Tab." in logged(game, client)
    act(game, client, Frame("key", {"k": "b", "t": 0}))  # B skips nothing: there is no lesson.
    game.step(10)
    assert drone.health == health and drone_of(game, pid) is drone
    assert not combat.legal(actor, drone) and not combat.legal(drone, actor)
    assert combat.relation(actor, drone) == "neutral"
    assert player.progress == progress
    assert not [e for e in manager.outbox[outbox:] if e["action"] in ("save", "identity")]


def test_an_inert_drone_reads_neutral_in_nearby_and_leaves_the_target_panel(game: HeadlessServer) -> None:
    """Presentation lead: NEARBY keeps the name with `~`; TARGET clears on that frame."""
    client = game.connect()
    pid, drone, actor = armed_and_warned(game, client)
    model = Display(DoorInfo(Path('.'), Path('.'), client.session.door_info, 80, 24, "256", 3600), presentation=True)
    terminal = FakeTerminal(80, 24)  # One terminal: later renders send only what changed.
    clock = iter(range(20, 10_000, 20))

    def screen() -> str:
        for frame in game.frames_for(client):
            model.receive(frame, 0)
            if frame.type in ("view", "delta"):
                client.send(Frame("ack", {"rev": frame.data["rev"]}))
        model.toast = None
        now = next(clock)
        model.update(now, now)
        terminal.write(model.render(now)[0])
        return terminal.screen_text()

    actor.target = drone.id
    game.core.world.zones[actor.zone].revision += 1
    game.step(2)
    screen()
    assert model.body["target"] and model.body["target"]["id"] == drone.id
    create(game, client, name="Noor", card="none")
    game.step(3)
    text = screen()
    row = next(entry for entry in model.body["nearby"] if entry["id"] == drone.id)
    assert row["relation"] == "~" and row["name"] == "Training drone"
    shown = next(entry for entry in model.body["actors"] if entry["id"] == drone.id)
    assert shown["glyph_id"] == "actor-drone"  # Still drawn as the drone.
    assert model.body["target"] is None
    assert "none   Tab picks" in text and "Training drone" in text


def test_leaving_an_inert_drone_removes_it_and_no_save_holds_the_pistol(game: HeadlessServer) -> None:
    client = game.connect()
    manager = game.core.characters
    pid, drone, actor = armed_and_warned(game, client)
    create(game, client, name="Noor", card="none")
    place(game, client, "vatside-clinics", (30, 18))
    game.step(2)
    assert drone_of(game, pid) is None
    approach(game, client)
    game.step(20)
    assert drone_of(game, pid) is None  # Gone for good: a character never wakes it.
    game.core.sessions.disconnect(client.session)
    saved = [e for e in manager.outbox if e["action"] in ("save", "create") and e["player"]["id"] == pid]
    assert saved and all("training:" not in str(e["player"]) for e in saved)
    back = HeadlessServer(game.core.loop.content, character_state=state(game)).connect()
    assert back.session.player_id == pid


def intent(game: HeadlessServer, client, name: str, **args) -> None:
    act(game, client, Frame("intent", {"name": name, "args": args}))


def lift_record(game: HeadlessServer, client, presence) -> None:
    encounters = game.core.lattice.encounters
    data = encounters.core(presence).graph.room(presence.room).data[0]
    source = game.core.lattice.sources.refresh(encounters.source(presence, data), data, game.clock.now_tick())
    intent(game, client, "lat.lift", target=data.id, generation=source.generation)
    game.step(max(1, presence.procedure.until - game.clock.now_tick()) if presence.procedure else 1)
    game.step(2)


def test_the_terminal_lesson_enters_its_core_lifts_the_record_and_brings_it_back(game: HeadlessServer) -> None:
    client = game.connect()
    game.step(2)
    manager, lattice, pid = game.core.characters, game.core.lattice, client.session.player_id
    place(game, client, HALL, (34, 15))
    act(game, client, Frame("key", {"k": "j", "t": 0}))
    game.step(3)
    presence = lattice.presences[pid]
    assert presence.core == "lat-wake-hall" and presence.instance  # No district grid first (item 6).
    ice = lattice.encounters.defenders(presence)[0]
    intent(game, client, "lat.cast", program="prg_pick", target=ice.id)
    game.step(presence.cast.until - game.clock.now_tick() + 2)
    assert not ice.alive
    game.frames_for(client)
    lift_record(game, client, presence)
    wake = manager.wakes[client.session.id]
    assert wake.lessons["lifted"]["asset"] == "lattice-training-record"
    logs = [line["text"] for f in game.frames_for(client) if f.type == "log" for line in f.data["lines"]]
    assert logs.count("Transfer committed: Your decant record.") == 1
    lift_record(game, client, presence)  # Idempotent: nothing more is written or logged.
    logs = [line["text"] for f in game.frames_for(client) if f.type == "log" for line in f.data["lines"]]
    assert "Transfer committed: Your decant record." not in logs
    assert not [e for e in manager.outbox if e["action"] in ("save", "create")]
    assert not game.core.commerce.outbox
    intent(game, client, "lat.leave")
    game.step(3)
    assert pid not in lattice.presences and wake.stage == "record" and wake.source == "terminal"
    act(game, client, Frame("intent", {"name": "menu_select", "args": {}}))
    act(game, client, Frame("line", {"id": wake.prompt_id, "text": "Noor"}))
    effects = game.commit_characters()
    game.step()
    created = next(e for e in effects if e["action"] == "create")
    key, unit = wake.lessons["lifted"]["key"], wake.lessons["lifted"]["unit"]
    assert created["identity"]["lattice_receipts"][key] == unit
    player = manager.players[client.session.player_id]
    assert player.progress["lattice_records"]["lattice-training-record"] == unit and player.xp == 0


def test_a_disconnect_in_the_training_core_drops_the_unread_body_at_once(game: HeadlessServer) -> None:
    client = game.connect()
    game.step(2)
    manager, lattice, pid = game.core.characters, game.core.lattice, client.session.player_id
    place(game, client, HALL, (34, 15))
    act(game, client, Frame("key", {"k": "j", "t": 0}))
    game.step(3)
    assert pid in lattice.presences
    game.core.sessions.disconnect(client.session)
    game.step()
    assert pid not in lattice.presences and pid not in lattice.orphans and pid not in manager.players
