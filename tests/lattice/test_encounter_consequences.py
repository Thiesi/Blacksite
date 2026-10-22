"""Game 5/6.7: body authority, trace dispatch and durable one-use goods."""

from dataclasses import replace
import sqlite3

import pytest

from blacksite.server.lattice.ice import IceEvent
from blacksite.server.lattice.presence import EscapeChannel
from blacksite.server.storage.db import Storage
from tests.lattice.test_engine import actor, intent, jack, runners
from tests.lattice.test_encounters import cast, enter
from tests.lattice.test_silt_encounters import descend


@pytest.mark.parametrize("owner_kind,damage", [("institution", True), ("private", False)])
def test_game_5_only_explicit_npc_risk_permits_safe_body_feedback(runners, owner_kind, damage):
    game, a, b, c = runners
    content = game.core.loop.content
    spec = content.cores["lat-civic-ledger"]
    # Labelled NPC-risk scenario at a real safe body, with a black defender.
    content.cores[spec.id] = replace(spec, owner_kind=owner_kind,
        rooms=(replace(spec.rooms[0], ice=("ice_kiln",)), *spec.rooms[1:]))
    presence = jack(game, a)
    presence.cell = next(c.id for c in game.core.lattice.sectors.records[presence.sector].cells if c.core_id == spec.id)
    intent(game, a, "lat.enter", core=spec.id)
    assert presence.instance is None
    hp = actor(game, a).health
    intent(game, a, "lat.enter", core=spec.id, risk=True)
    assert presence.instance
    kiln = game.core.lattice.encounters.defenders(presence)[0]
    cast(game, a, "prg_pick", kiln.id)
    game.step(22)
    assert (actor(game, a).health < hp) is damage
    assert actor(game, a).stance == "jacked"


def test_game_6_7_trace_dispatch_is_real_and_uses_nonrewarding_responders(runners):
    game, a, b, c = runners
    presence = enter(game, a, "lat-civic-ledger")
    encounters = game.core.lattice.encounters
    encounters.trace(presence, 100)
    player = game.core.characters.players[presence.player_id]
    assert player.warden_heat_until and player.progress["lattice_registry_until"]
    responses = [i for i in game.core.world.actors.values() if i.behaviour.get("response") == player.id]
    assert len(responses) == 2
    assert all(i.behaviour["template"] == "npc-warden-response" for i in responses)
    assert game.core.world.zones[actor(game, a).zone].safety_at(actor(game, a).position) == "safe"
    assert not game.core.combat.legal(responses[0], actor(game, a))


def test_game_6_7_single_use_charge_applies_only_after_successful_commit(runners):
    game, a, b, c = runners
    presence = jack(game, a)
    player = game.core.characters.players[presence.player_id]
    presence.rig = ("prg_residual_fragment", None, None)
    player.progress["lattice_charges"] = {"prg_residual_fragment": 1}
    cast(game, a, "prg_residual_fragment")
    assert not presence.effects.has("prg_residual_fragment", game.clock.now_tick())
    game.commit_commerce(error=True)
    assert player.progress["lattice_charges"]["prg_residual_fragment"] == 1
    cast(game, a, "prg_residual_fragment")
    game.commit_commerce()
    assert presence.effects.has("prg_residual_fragment", game.clock.now_tick())
    assert player.progress["lattice_charges"]["prg_residual_fragment"] == 0
    intent(game, a, "lat.jack_out")
    presence = jack(game, a)
    presence.rig = ("prg_residual_fragment", None, None)
    intent(game, a, "lat.cast", program="prg_residual_fragment")
    assert presence.cast is None and not presence.effects.active


def test_game_6_7_source_reward_and_metadata_rollback_together(runners, tmp_path):
    game, a, b, c = runners
    presence = enter(game, a, "lat-civic-ledger")
    presence.room = "r-cache"
    encounters, commerce = game.core.lattice.encounters, game.core.commerce
    player = game.core.characters.players[presence.player_id]
    data = encounters.core(presence).graph.room(presence.room).data[0]
    key = encounters.source(presence, data)
    game.core.lattice.sources.refresh(key, data, game.clock.now_tick())
    store = Storage(tmp_path/"world.db", game.clock)
    try:
        for effect in game.commit_characters():
            store.character_write(effect)
        before = player.chits_hand
        for fail in (True, False):
            intent(game, a, "lat.lift", target=data.id, generation=0)
            game.step(presence.procedure.until-game.clock.now_tick())
            effect = commerce.outbox.pop(0)
            if fail:
                store.db.execute("CREATE TRIGGER reject_reward BEFORE INSERT ON audit BEGIN SELECT RAISE(ABORT,'probe'); END")
                with pytest.raises(sqlite3.IntegrityError):
                    store.commerce_write(commerce.prepare(effect))
                commerce.committed(effect, False)
                assert store.meta("lattice_state") in (None, 0)
                assert player.chits_hand == before and game.core.lattice.sources.sources[key].generation == 0
                store.db.execute("DROP TRIGGER reject_reward")
            else:
                # A stale write-behind copy must never overwrite the receipt.
                store.mark_dirty("meta", "lattice_state", {"nonce": -1})
                store.commerce_write(commerce.prepare(effect))
                commerce.committed(effect, True)
                store.flush_now()
                saved = store.character_state()
                assert saved["lattice"]["sources"][key]["generation"] == 1
                record = next(p for p in saved["players"] if p["id"] == player.id)
                assert record["chits_hand"] == player.chits_hand == before+80
    finally:
        store.close()


def test_game_6_7_anchor_and_decoy_stop_drift_displacement(runners):
    game, a, b, c = runners
    presence = descend(game, a)
    encounters = game.core.lattice.encounters
    drift = next(i for i in encounters.core(presence).ice.values() if i.template.class_ == "drift")
    presence.room = drift.location[1]
    where = presence.room
    presence.effects.decoy = 30
    event = IceEvent("hit", drift.id, presence.player_id, 5)
    encounters.receive(presence, event, name="Drift")
    assert presence.room == where
    presence.effects.decoy = 0
    presence.effects.install(game.core.loop.content.programs["prg_anchor"], game.clock.now_tick())
    encounters.receive(presence, event, name="Drift")
    assert presence.room == where
    presence.effects.active.clear()
    encounters.receive(presence, event, name="Drift")
    assert presence.room in encounters.core(presence).graph.room(where).neighbours


def test_game_6_7_public_district_refuses_npc_black_burning(runners):
    game, a, b, c = runners
    presence = jack(game, a)
    hp = actor(game, a).health
    hit = IceEvent("hit", "pursuing-hound", presence.player_id, 20, 10)
    assert game.core.lattice.encounters.receive(presence, hit, name="Hound")
    assert presence.integrity == 100 and actor(game, a).health == hp


def test_game_6_7_source_identity_survives_an_authored_room_move(runners):
    game, a, b, c = runners
    presence = enter(game, a, "lat-civic-ledger")
    encounters = game.core.lattice.encounters
    data = encounters.core(presence).graph.room("r-cache").data[0]
    first = encounters.source(presence, data)
    presence.room = "r-cache"
    assert encounters.source(presence, data) == first


def test_game_6_7_burn_waits_for_other_players_transfer_without_charging(runners):
    game, a, b, c = runners
    first, second = enter(game, a, "lat-civic-ledger"), enter(game, b, "lat-civic-ledger")
    # Explicit contested-body scenario; no protected-body exception for PvP.
    zone = game.core.world.zones[actor(game, a).zone]
    zone.template = replace(zone.template, meta=replace(zone.template.meta, safety="contested"))
    for client in (a, b):
        game.core.characters.players[client.session.player_id].grade = 5
    first.rig = ("prg_burn", None, None)
    intent(game, a, "lat.cast", program="prg_burn", target=second.player_id)
    assert first.cast
    commerce = game.core.commerce
    commerce.settle(None, {}, commerce.items, commerce.caches, commerce.serial, lambda success: None)
    game.step(first.cast.until-game.clock.now_tick())
    player = game.core.characters.players[first.player_id]
    assert first.cast and second.integrity == 100 and player.marked_until is None
    assert "prg_burn" not in player.progress.get("lattice_cooldowns", {})
    before = first.trace
    game.commit_commerce()
    game.step()
    assert first.cast is None and second.integrity == 82
    assert player.marked_until and "prg_burn" in player.progress["lattice_cooldowns"]
    assert first.trace > before+14


def test_game_6_7_earned_hit_settles_before_escape_and_further_transfers(runners):
    game, a, b, c = runners
    presence = enter(game, a, "lat-civic-ledger")
    presence.room = "r-foyer"
    encounters, commerce = game.core.lattice.encounters, game.core.commerce
    ice = encounters.defenders(presence)[0]
    presence.escape = EscapeChannel(game.clock.now_tick()+1, encounters.hit_serial(presence))
    commerce.settle(None, {}, commerce.items, commerce.caches, commerce.serial, lambda success: None)
    # Isolate a hit already earned by the defender's warned attack.
    encounters.event(ice, IceEvent("hit", ice.id, presence.player_id, 10))
    assert presence.integrity == 100 and encounters.pending_hit(presence.player_id)
    queued = []
    commerce.enqueue_system(lambda: queued.append(presence.integrity))
    game.step()
    assert presence.player_id in game.core.lattice.presences
    game.commit_commerce()
    assert presence.integrity == 90 and queued == [90]
    game.step()
    assert presence.escape.interruptions == 1
    assert presence.player_id in game.core.lattice.presences
    assert not encounters.pending_hit(presence.player_id)
