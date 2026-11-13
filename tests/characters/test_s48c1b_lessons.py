"""S48c1b: the Wake lessons on the provisional body (#220 beats 6-9; game design 17)."""

from karst41.server.protocol import Frame
from tests.character_helpers import act, create, place, state
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


def replaying(game: HeadlessServer):
    """Q2: no replay trigger yet (#239); spawn the drone for a finished character directly."""
    client = game.connect()
    create(game, client, name="Noor", card="none")
    manager, combat = game.core.characters, game.core.combat
    player = manager.players[client.session.player_id]
    own = combat.weapon(player)
    assert own is not None and own[0].template != PISTOL
    player.progress.pop("wake_combat", None)
    approach(game, client)
    assert drone_of(game, player.id) is not None
    return client, manager, combat, player, own


def test_a_replay_holds_the_pistol_over_the_characters_own_weapon(game: HeadlessServer) -> None:
    client, manager, combat, player, own = replaying(game)
    equipment = dict(player.equipment)
    assert combat.weapon(player)[0].template == PISTOL
    assert player.equipment == equipment  # Equipment is never touched.
    fight(game, client)
    assert combat.weapon(player)[0].id == own[0].id


def test_leaving_or_disconnecting_mid_replay_restores_the_weapon_and_saves_no_pistol(game: HeadlessServer) -> None:
    client, manager, combat, player, own = replaying(game)
    place(game, client, "vatside-clinics", (30, 18))
    game.step(2)
    assert combat.weapon(player)[0].id == own[0].id and drone_of(game, player.id) is None
    place(game, client, HALL, NEAR_DRONE)
    game.step(3)
    assert combat.weapon(player)[0].template == PISTOL
    game.core.sessions.disconnect(client.session)
    saved = [e for e in manager.outbox if e["action"] == "save" and e["player"]["id"] == player.id]
    assert saved and all("training:" not in str(e["player"]) for e in saved)
    assert saved[-1]["player"]["equipment"] == player.equipment
    back = HeadlessServer(game.core.loop.content, character_state=state(game)).connect()
    assert back.session.player_id == player.id


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
