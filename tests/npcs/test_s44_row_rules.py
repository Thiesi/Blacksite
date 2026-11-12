"""S44: hunted, the Halo's refusal and settling the debt (game design 5.5, 7.3)."""

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

from karst41.content.loader import load_content
from karst41.server import truce as truce_rules
from karst41.server.npcs.templates import PROVOCATION_SECONDS, make_actor
from karst41.server.rules import character, combat as rules
from karst41.server.storage.db import Storage
from tests.character_helpers import create, place, state
from tests.combat.test_engine import body
from tests.harness import HeadlessServer

ROW, HALO = "sodium-row", "sodium-tin-halo"
KEEP = "sable-enforcer"  # The Row's shipped keeper guard spawner.


def build(repo_root: Path, content=None, clock=None, saved=None):
    content = content or load_content(repo_root/"src/karst41/content")
    # Keep only the Row's keeper spawner; no unrelated city traffic.
    content.zones = {key: replace(zone, meta=replace(zone.meta, spawners=tuple(
        sp for sp in zone.meta.spawners if sp.condition == "per_player" or (key == ROW and sp.id == KEEP))))
        for key, zone in content.zones.items()}
    if saved is not None:
        return HeadlessServer(content, character_state=saved, clock=clock), content
    game = HeadlessServer(content, character_state={})
    clients = []
    for uid in (1, 2):
        client = game.connect({"user_id": uid, "handle": f"Wake{uid}", "node_name": "test"})
        create(game, client, archetype=0, name=f"Runner{uid}", card="none")
        player = game.core.characters.players[client.session.player_id]
        player.update_progression(1500)
        player.grade = 5
        actor = body(game, client)
        actor.health = actor.health_max = character.health_max(player.attributes["vitals"])
        clients.append(client)
    place(game, clients[0], ROW, (25, 3))
    place(game, clients[1], ROW, (27, 3))
    return game, content, *clients


@pytest.fixture
def row(repo_root):
    return build(repo_root)


def player(game, client):
    return game.core.characters.players[client.session.player_id]


def keepers(game):
    return [a for a in game.core.world.zones[ROW].actors.values() if a.behaviour.get("spawner") == KEEP]


def regular(game, aid="regular", tile=(26, 5)):
    actor = make_actor(game.core.loop.content.npcs["npc-sodium-regular"], aid, {"spawner": aid, "home": tile})
    game.core.world.enter(actor, ROW, tile)
    return actor


def lines(client):
    return [line["text"] for line in client.session.log_ring]


def halo_door(game):
    return next(ex for ex in game.core.world.zones[ROW].template.meta.exits if ex.target_zone == HALO)


def refusal(game, client):
    return game.core.characters.sim.travel_refusal(client.session, halo_door(game))


def kill(game, attacker, victim_client):
    game.core.combat.hurt(attacker, body(game, victim_client), 10_000)
    game.step(rules.DOWN_SECONDS * 10)
    game.commit_commerce()


def respawn(game):
    game.step(rules.DECANT_SECONDS * 10)
    game.commit_commerce()
    game.step()


def breach(game, client, target=None):
    """An attack on a Row resident that was not after the attacker."""
    target = target or regular(game)
    game.core.npcs.provoked(body(game, client), target)
    return target


# ---- 1. Hunted: the stored record only ------------------------------------

def test_s44_breach_writes_record_and_hunted_reads_it(row):
    game, _, a, _ = row
    assert keepers(game)
    breach(game, a)
    record = player(game, a).keeper_answer
    assert record["keeper"] == "sable" and record["zone"] == ROW
    assert truce_rules.stamp(record["until"]) == game.core.combat.now() + PROVOCATION_SECONDS
    assert game.core.characters.sim.me_provider(a.session)["hunted"] is True
    assert "Sable is coming for you." in lines(a)
    # The predicate is the record: provocations alone don't make anyone hunted.
    player(game, a).keeper_answer = None
    assert "hunted" not in game.core.characters.sim.me_provider(a.session)
    assert refusal(game, a) is None


def test_s44_non_truce_npc_elsewhere_makes_nobody_hunted(row):
    game, _, a, _ = row
    place(game, a, "vatside-clinics", (25, 3))
    target = make_actor(game.core.loop.content.npcs["npc-sodium-regular"], "elsewhere",
                        {"spawner": "elsewhere", "home": (26, 3)})
    game.core.world.enter(target, "vatside-clinics", (26, 3))
    game.core.npcs.provoked(body(game, a), target)
    assert ("vatside-clinics", "elsewhere", body(game, a).id) in game.core.npcs.provocations
    assert player(game, a).keeper_answer is None
    assert "hunted" not in game.core.characters.sim.me_provider(a.session)
    assert refusal(game, a) is None


def test_s44_breach_with_no_live_guard_writes_record_and_a_new_guard_pursues(row):
    game, _, a, _ = row
    for guard in keepers(game):
        game.core.world.leave(guard)
    assert not keepers(game)
    breach(game, a)
    assert truce_rules.hunted(player(game, a), game.core.combat.now())
    assert (ROW, KEEP, body(game, a).id) in game.core.npcs.provocations
    # The spawner's next guard takes up the live answer and goes to the body.
    game.step(61 * 10)
    fresh = keepers(game)
    assert fresh and all(guard.target == body(game, a).id for guard in fresh)
    assert all(guard.behaviour["state"] == "hunt" for guard in fresh)


def test_s44_drone_or_burn_records_against_controller_body(row):
    game, _, a, _ = row
    drone = make_actor(game.core.loop.content.npcs["npc-sodium-regular"], "fake-drone",
                       {"player_drone": True, "spawner": "fake-drone", "home": (24, 3)})
    drone.owner = body(game, a).id
    game.core.world.enter(drone, ROW, (24, 3))
    game.core.progression.controller = lambda source: player(game, a) if source in (drone, body(game, a)) else None
    game.core.npcs.keep_truce(drone, regular(game), "sable")
    assert player(game, a).keeper_answer["zone"] == ROW
    assert (ROW, KEEP, drone.id) in game.core.npcs.provocations
    assert (ROW, KEEP, body(game, a).id) in game.core.npcs.provocations


# ---- restart ---------------------------------------------------------------

def test_s44_restart_mid_answer_restores_hunted_and_guards(row, repo_root, tmp_path):
    game, content, a, _ = row
    breach(game, a)
    pid, until = body(game, a).id, player(game, a).keeper_answer["until"]
    store = Storage(tmp_path/"world.db", game.clock)
    try:
        store.mark_dirty("players", pid, player(game, a).record())
        store.flush_now()
        stored = store.character_state()
        assert next(p for p in stored["players"] if p["id"] == pid)["keeper_answer"]["until"] == until
    finally:
        store.close()
    saved = state(game)
    game.clock.advance(600)  # One minute of downtime; the answer runs on.
    reboot, _ = build(repo_root, content, game.clock, saved)
    restored = reboot.core.characters.players[pid]
    assert truce_rules.hunted(restored, reboot.core.combat.now())
    assert reboot.core.npcs.provocations[(ROW, KEEP, pid)] == truce_rules.stamp(until)
    returning = reboot.connect({"user_id": 1, "handle": "Wake1", "node_name": "test"})
    reboot.step()
    place(reboot, returning, ROW, (25, 3))
    assert reboot.core.characters.sim.me_provider(returning.session)["hunted"] is True
    reboot.step(20)
    guards = keepers(reboot)
    assert guards and all(guard.target == pid for guard in guards)


def test_s44_restart_drops_an_expired_answer(row, repo_root):
    game, content, a, _ = row
    breach(game, a)
    pid = body(game, a).id
    saved = state(game)
    game.clock.advance((PROVOCATION_SECONDS + 1) * 10)
    reboot, _ = build(repo_root, content, game.clock, saved)
    assert reboot.core.characters.players[pid].keeper_answer is None
    assert not any(key[2] == pid for key in reboot.core.npcs.provocations)


# ---- truce Mark vs other Marks ---------------------------------------------

def test_s44_truce_mark_then_other_mark_keeps_door_to_truce_expiry(row, repo_root):
    game, content, a, b = row
    combat = game.core.combat
    combat.mark(body(game, a), body(game, b))
    me = player(game, a)
    assert me.truce_marked_until == me.marked_until
    truce_until = truce_rules.stamp(me.truce_marked_until)
    game.step(5 * 60 * 10)
    # A Lattice-channel Mark (interlock) extends marked_until only.
    later = combat.now() + rules.MARKED_SECONDS
    me.marked_until = truce_rules.iso(later)
    assert truce_rules.stamp(me.truce_marked_until) == truce_until
    saved = state(game)
    reboot, _ = build(repo_root, content, game.clock, saved)
    restored = reboot.core.characters.players[me.id]
    assert restored.truce_marked_until == me.truce_marked_until and restored.marked_until == me.marked_until
    now = combat.now()
    assert truce_rules.halo_refusal(content, me, now).endswith(f"{truce_rules.minutes(truce_until-now)} min.\"")
    after = truce_until + 1
    assert truce_rules.halo_refusal(content, me, after) is None
    assert truce_rules.vesper_refusal(me, after) == (
        f'Vesper: "Not with that name. Come back in {truce_rules.minutes(later-after)} min."')


def test_s44_lattice_mark_shuts_vesper_not_the_halo_door(row):
    game, _, a, _ = row
    me = player(game, a)
    me.marked_until = truce_rules.iso(game.core.combat.now() + rules.MARKED_SECONDS)
    assert refusal(game, a) is None
    assert game.core.commerce.service_refusal(a.session, "vesper") == 'Vesper: "Not with that name. Come back in 15 min."'
    assert game.core.commerce.service_refusal(a.session, "halvard") is None


# ---- the Halo's door wording -----------------------------------------------

@pytest.mark.parametrize("mark,answer,words", [
    (900, 300, "mark"), (120, 300, "answer"), (300, 300, "mark"), (0, 61, "answer"), (59, 0, "mark")])
def test_s44_halo_wording_longer_wait_wins_mark_on_tie(row, mark, answer, words):
    game, content, a, _ = row
    now, me = game.core.combat.now(), player(game, a)
    me.truce_marked_until = truce_rules.iso(now + mark) if mark else None
    me.keeper_answer = {"keeper": "sable", "zone": ROW, "until": truce_rules.iso(now + answer)} if answer else None
    line = truce_rules.halo_refusal(content, me, now)
    wait = truce_rules.minutes(max(mark, answer))
    if words == "mark":
        assert line == f'The bouncer looks at your red name. "Not tonight. Not after the Row. {wait} min."'
    else:
        assert line == f'The bouncer doesn\'t move. "Sable\'s still asking about you. Try me in {wait} min."'


def test_s44_minutes_round_up_and_never_say_zero():
    assert [truce_rules.minutes(s) for s in (0.1, 59, 60, 61, 299, 300)] == [1, 1, 1, 2, 5, 5]


def test_s44_door_refuses_at_travel_and_shows_out_from_inside(row):
    game, _, a, _ = row
    breach(game, a)
    halo = halo_door(game)
    game.core.characters.sim.interact(a.session, game.core.characters.sim.avatars[a.session.user_id],
                                      game.clock.now_tick(), choice=type("C", (), {"value": halo})())
    assert body(game, a).zone == ROW
    assert any("still asking about you. Try me in 5 min." in text for text in lines(a))
    # Inside when the answer starts (a drone or burn sent from the Halo).
    player(game, a).keeper_answer = None
    place(game, a, HALO, (5, 5))
    game.core.npcs.keep_truce(body(game, a), regular(game, "victim2", (40, 5)), "sable")
    assert "Sable is waiting for you on Sodium Row." in lines(a)
    game.step(10)
    assert body(game, a).zone == ROW
    assert lines(a).count('The bouncer doesn\'t move. "Sable\'s still asking about you. Try me in 5 min."') == 2


# ---- 4. Death settles ------------------------------------------------------

def test_s44_death_settles_answer_and_guards_stand_down_same_tick(row):
    game, _, a, b = row
    breach(game, a)
    for guard in keepers(game):
        guard.target = body(game, a).id
        guard.behaviour["state"] = "hunt"
    kill(game, body(game, b), a)
    assert body(game, a).stance == "dead"
    assert player(game, a).keeper_answer is None
    # The keeper's answer goes; the regular's own group reaction is not the keeper's.
    assert not any(key[1] == KEEP and key[2] == body(game, a).id for key in game.core.npcs.provocations)
    assert all(guard.target is None and guard.behaviour["state"] == "base" for guard in keepers(game))
    assert player(game, a).progress["truce_settled"] == "Sable"
    respawn(game)
    assert body(game, a).stance == "normal"
    log = lines(a)
    vat = log.index("You wake in the vat. Missing recovery supplies are bound to you.")
    assert log[vat + 1] == "Sable considers it settled."
    assert "truce_settled" not in player(game, a).progress
    assert refusal(game, a) is None


def test_s44_marked_die_respawn_then_new_breach_answers_again(row):
    game, _, a, b = row
    combat = game.core.combat
    combat.mark(body(game, a), body(game, b))
    combat.exchange(body(game, a), body(game, b))
    assert player(game, a).keeper_answer and body(game, a).marked
    kill(game, body(game, b), a)
    respawn(game)
    log = lines(a)
    assert log[log.index("You wake in the vat. Missing recovery supplies are bound to you.") + 1] == (
        "Sable considers it settled. The Mark stays.")
    # The settled breach: the wording changes, the wait goes on.
    assert refusal(game, a).startswith("The bouncer looks at your red name.")
    place(game, a, ROW, (25, 3))
    game.step(20)
    assert all(guard.target != body(game, a).id for guard in keepers(game))
    # A new breach, at an unmarked player, starts a fresh answer.
    third = game.connect({"user_id": 3, "handle": "Wake3", "node_name": "test"})
    create(game, third, archetype=0, name="Runner3", card="none")
    player(game, third).grade = 5
    place(game, third, ROW, (26, 3))
    before = lines(a).count("Sable is coming for you.")
    combat.mark(body(game, a), body(game, third))
    combat.exchange(body(game, a), body(game, third))
    assert truce_rules.hunted(player(game, a), combat.now())
    assert lines(a).count("Sable is coming for you.") == before + 1


def test_s44_combat_logout_settles_nothing(row):
    game, _, a, b = row
    breach(game, a)
    game.core.combat.exchange(body(game, a), body(game, b))
    until = player(game, a).keeper_answer["until"]
    game.core.sessions.disconnect(a.session)
    game.step(rules.COMBAT_SECONDS * 10 + 100)
    assert player(game, a).keeper_answer["until"] == until
    assert truce_rules.hunted(player(game, a), game.core.combat.now())


def test_s44_offline_body_killed_settles_and_restart_restores_nothing(row, repo_root):
    game, content, a, b = row
    breach(game, a)
    pid = body(game, a).id
    game.core.combat.exchange(body(game, a), body(game, b))
    game.core.sessions.disconnect(a.session)
    game.step()
    sleeper = game.core.world.actors[pid]
    assert sleeper.stance == "sleeper"
    game.core.combat.hurt(body(game, b), sleeper, 10_000)
    game.step(rules.DOWN_SECONDS * 10)
    effects = game.commit_commerce()
    # The death's own durable write carries the cleared record.
    assert any(effect["player"] and effect["player"].get("keeper_answer", 0) is None
               and effect["player"]["id"] == pid for effect in effects)
    assert game.core.characters.players[pid].keeper_answer is None
    reboot, _ = build(repo_root, content, game.clock, state(game))
    restored = reboot.core.characters.players[pid]
    assert not truce_rules.hunted(restored, reboot.core.combat.now())
    assert truce_rules.halo_refusal(content, restored, reboot.core.combat.now()) is None
