"""S48c1a: the body before the record (#220, game design 4 and 17)."""

import pytest

from karst41.server.protocol import Frame
from karst41.server.rules import character as rules
from tests.character_helpers import act, create, place, state
from tests.harness import HeadlessServer

HALL = "vatside-wake-hall"
E = Frame("key", {"k": "e", "t": 0})
ESC = Frame("key", {"k": "escape", "t": 0})


def woken(game: HeadlessServer):
    client = game.connect()
    game.step(2)
    return client, game.core.characters


def test_the_caller_wakes_in_the_hall_with_an_unread_body(game: HeadlessServer) -> None:
    client, manager = woken(game)
    pid = client.session.player_id
    body = manager.players[pid]
    assert manager.unread(pid) and client.session.subscribed == HALL
    assert manager.wakes[client.session.id].stage == "hall"
    assert body.name == f"No. {manager.wakes[client.session.id].serial:04d}" and body.archetype == rules.UNREAD
    assert set(body.attributes.values()) == {rules.UNREAD_ATTRIBUTE}
    # Game design 17 (#238): derived from the rules, not restated.
    assert body.health == rules.health_max(rules.UNREAD_ATTRIBUTE) == 58
    assert body.stamina == rules.stamina_max(rules.UNREAD_ATTRIBUTE, rules.UNREAD_ATTRIBUTE) == 36
    me = manager.me(client.session)
    assert me["grade"] is None and me["chits"] == 0
    assert not manager.owned(client.session.user_id)


def test_e_at_the_street_door_or_the_outfitter_opens_the_record_but_not_the_terminal(game: HeadlessServer) -> None:
    client, manager = woken(game)
    wake = manager.wakes[client.session.id]
    for tile, source in (((37, 16), "door"), ((33, 16), "outfitter")):
        place(game, client, HALL, tile)
        act(game, client, E)
        assert (wake.stage, wake.source) == ("record", source)
        act(game, client, ESC)
        assert wake.stage == "hall"
    place(game, client, HALL, (36, 14))  # Beside the training terminal only: it never opens the record.
    act(game, client, E)
    assert wake.stage == "hall"


def test_the_street_door_never_lets_an_unread_body_out(game: HeadlessServer) -> None:
    client, manager = woken(game)
    place(game, client, HALL, (37, 16))
    act(game, client, Frame("key", {"k": "right", "t": 0}))  # A door exit needs E; a step never leaves.
    game.step(4)
    avatar = manager.sim.avatars[client.session.user_id]
    assert avatar.actor.position == (38, 16) and avatar.travel is None and manager.wakes[client.session.id].stage == "hall"
    act(game, client, E)
    game.step(4)
    assert avatar.travel is None and avatar.actor.zone == HALL
    assert manager.wakes[client.session.id].stage == "record"
    # Any other way to the street refuses too, and opens the record (beat 7).
    exit = game.core.world.zones[HALL].template.meta.exits[0]
    assert manager.sim.travel_refusal(client.session, exit)


def test_an_unread_body_never_reaches_storage_or_commerce(game: HeadlessServer) -> None:
    client, manager = woken(game)
    pid = client.session.player_id
    commerce = game.core.commerce
    assert not commerce.ready(client.session)
    with pytest.raises(ValueError):
        commerce.propose(client.session, "buy", {})
    manager.queue("save", client.session.user_id, manager.players[pid], immediate=True)
    game.core.sessions.disconnect(client.session)
    game.step()
    written = [e for e in manager.outbox if e["action"] in ("save", "delete", "create")]
    assert not written and pid not in manager.players and not manager.unread_ids
    # The serial is kept in the identity's wake record, so a redial is the same number.
    assert manager.identities["1"]["wake"]["serial"] == int(pid.rsplit(":", 1)[1])


def test_a_redial_while_the_record_settles_waits_for_the_commit(game: HeadlessServer) -> None:
    client = game.connect()
    create(game, client, commit=False)
    manager = game.core.characters
    game.core.sessions.disconnect(client.session)
    back = game.connect()
    game.step()
    assert manager.wakes[back.session.id].stage == "saving" and back.session.player_id is None
    game.commit_characters()
    game.step()
    player = manager.players[back.session.player_id]
    assert not manager.unread(player.id) and player.name == "Wide界"
    assert sum(a.kind == "player" for a in game.core.world.actors.values()) == 1


def test_reading_the_record_promotes_the_body_in_place(game: HeadlessServer) -> None:
    client, manager = woken(game)
    tile = game.core.world.free_tile(HALL, (20, 10))
    place(game, client, HALL, tile)
    pid = client.session.player_id
    actor = game.core.world.actors[pid]
    create(game, client, archetype=0, name="Noor", card="none")
    player = manager.players[client.session.player_id]
    assert player.id == pid and game.core.world.actors[pid] is actor and actor.position == tile
    assert player.archetype == "hardline" and not manager.unread(pid)
    assert actor.health == rules.health_max(player.attributes["vitals"])
    assert actor.stamina == rules.stamina_max(player.attributes["nerve"], player.attributes["frame"])
    assert manager.me(client.session)["grade"] == player.grade


def test_a_card_counts_when_it_is_taken_at_the_table(game: HeadlessServer) -> None:
    client, manager = woken(game)
    place(game, client, HALL, (8, 9))
    act(game, client, E)
    assert manager.screens[client.session.id][0] == "cards"
    first = next(iter(game.core.loop.content.wake_cards))
    act(game, client, Frame("intent", {"name": "menu_select", "args": {}}))
    assert client.session.id not in manager.screens and manager.wakes[client.session.id].card == first
    assert manager.open_record(client.session, "door")
    game.step(2)
    act(game, client, Frame("intent", {"name": "menu_select", "args": {}}))
    wake = manager.wakes[client.session.id]
    act(game, client, Frame("line", {"id": wake.prompt_id, "text": "Noor"}))
    game.commit_characters()
    game.step()
    player = manager.players[client.session.player_id]
    selected = game.core.loop.content.wake_cards[first]
    assert player.standing == {selected.faction or first: rules.CARD_STANDING}


def take_first_card_at_table(game: HeadlessServer, client) -> str:
    manager = game.core.characters
    place(game, client, HALL, (8, 9))
    act(game, client, E)
    assert manager.screens[client.session.id][0] == "cards"
    act(game, client, Frame("intent", {"name": "menu_select", "args": {}}))
    return next(iter(game.core.loop.content.wake_cards))


def test_a_card_can_be_taken_once_after_the_record_by_an_ordinary_save(game: HeadlessServer) -> None:
    client = game.connect()
    create(game, client, name="Noor", card="none")
    manager = game.core.characters
    player = manager.players[client.session.player_id]
    assert not player.standing and not manager.card_taken("1")
    first = take_first_card_at_table(game, client)
    effect = next(e for e in game.core.commerce.outbox if e.get("player_id") == player.id)
    assert effect["identity"]["wake_card"] == first  # Committed with the standing, not before.
    game.commit_commerce()
    game.step()
    selected = game.core.loop.content.wake_cards[first]
    assert player.standing == {selected.faction or first: rules.CARD_STANDING}
    assert manager.card_taken("1")
    # A second card is refused: the table gives its ordinary recruiter answer.
    act(game, client, ESC)
    act(game, client, E)
    assert client.session.id not in manager.screens
    assert player.standing == {selected.faction or first: rules.CARD_STANDING}


def test_a_returning_identity_keeps_its_card_after_deletion(game: HeadlessServer) -> None:
    client = game.connect()
    create(game, client, name="Noor", card="unmoored")
    manager = game.core.characters
    pid = client.session.player_id
    act(game, client, Frame("intent", {"name": "delete_character", "args": {}}))
    act(game, client, Frame("line", {"id": "delete:" + pid, "text": "Noor"}))
    game.commit_characters()
    game.step(4)
    assert manager.unread(client.session.player_id) and manager.card_taken("1")
    place(game, client, HALL, (8, 9))
    act(game, client, E)
    assert client.session.id not in manager.screens  # No card table for this identity again.
    create(game, client, name="Again", card="kestrel")
    assert not manager.players[client.session.player_id].standing


def test_a_restart_keeps_none_taken_apart_from_a_pre_s48_identity(game: HeadlessServer) -> None:
    client = game.connect()
    create(game, client, name="Noor", card="none")
    snapshot = state(game)
    assert not HeadlessServer(game.core.loop.content, character_state=snapshot).core.characters.card_taken("1")
    snapshot["identities"]["1"].pop("wake_card")  # As stored before S48: the card menu was in the Wake.
    assert HeadlessServer(game.core.loop.content, character_state=snapshot).core.characters.card_taken("1")


def test_an_unread_body_reaches_only_the_halls_own_systems(game: HeadlessServer) -> None:
    client, manager = woken(game)
    names = {route.name for route in game.core.routes_for(client.session)}
    assert names <= game.core.UNREAD_ROUTES and "wake" in names
    assert not names & {"market", "commerce", "factions", "crews", "apartments", "relays", "events", "progression"}
    other = game.connect({"user_id": 2, "handle": "Other", "node_name": "test"})
    create(game, other, name="Other", card="none")
    assert "market" in {route.name for route in game.core.routes_for(other.session)}
    # Nobody can put a price on an unread body.
    panel = type("Panel", (), {"kind": "targets"})()
    rows = game.core.market.views.rows(other.session, panel)
    assert other.session.player_id in {row["id"] for row in rows}
    assert client.session.player_id not in {row["id"] for row in rows}


def test_an_unread_body_cannot_start_a_delete(game: HeadlessServer) -> None:
    client, manager = woken(game)
    pid = client.session.player_id
    name = manager.players[pid].name
    act(game, client, Frame("key", {"k": "p", "t": 0}))
    act(game, client, Frame("intent", {"name": "delete_character", "args": {}}))
    act(game, client, Frame("line", {"id": "delete:" + pid, "text": name}))
    assert pid not in manager.deleting
    assert manager.screens.get(client.session.id, ("",))[0] != "saving"
    assert not [e for e in manager.outbox if e["action"] == "delete"]


def test_a_refused_death_proposes_nothing_and_patches_no_other_effect(game: HeadlessServer) -> None:
    client, manager = woken(game)
    pid = client.session.player_id
    combat = game.core.combat
    actor = game.core.world.actors[pid]
    manager.players[pid].progress["combat"] = {"stage": "down", "until": 0}  # As a downed body has it.
    other = {"action": "save", "user": "other"}
    combat.commerce.outbox.append(other)
    combat.die(manager.players[pid], actor)
    assert combat.commerce.outbox[-1] is other and set(other) == {"action", "user"}
    assert pid not in combat.pending_deaths
