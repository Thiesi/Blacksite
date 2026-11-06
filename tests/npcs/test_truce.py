"""Game 5.5/7.3: truce hostility, keeper response and body attribution."""

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from blacksite.content.loader import load_content
from blacksite.content.schema import Behaviour
from blacksite.content.validate import validate
from blacksite.server.rules import combat as rules
from blacksite.server.npcs.templates import HEAT_SECONDS, make_actor
from blacksite.server.world.actors import Actor
from tests.character_helpers import create, place
from tests.combat.test_engine import body, build_duel
from tests.harness import HeadlessServer
from tests.lattice.test_engine import runners
from tests.lattice.test_encounters import cast, enter
from tests.server.test_drone_ownership import operator


@pytest.fixture
def row(repo_root):
    game, a, b = build_duel(repo_root)
    for client, tile in [(a, (25, 3)), (b, (27, 3))]:
        game.core.characters.players[client.session.player_id].grade = 5
        place(game, client, "sodium-row", tile)
    return game, a, b


def npc(game, template, aid, tile):
    actor = make_actor(game.core.loop.content.npcs[template], aid,
                       {"spawner": aid, "home": tile})
    game.core.world.enter(actor, "sodium-row", tile)
    return actor


def guard(game):
    return npc(game, "npc-sable-enforcer", "keeper", (30, 3))


@pytest.mark.parametrize("faction", ["halvard", "kestrel", "wardens", "unmoored"])
def test_game_5_5_truce_suppresses_matrix_but_not_provocation(row, faction):
    game, a, _ = row
    attacker = body(game, a)
    attacker.faction = faction
    keeper = guard(game)
    assert not game.core.npcs.hostile(keeper, attacker)
    game.core.npcs.evaluate(keeper, game.core.world.zones[keeper.zone], game.clock.now_tick())
    assert keeper.target is None
    game.core.npcs.provoked(attacker, keeper)
    assert game.core.npcs.hostile(keeper, attacker)


def test_game_5_5_truce_suppresses_explicit_hostility_and_retains_warden_heat(row):
    game, a, _ = row
    keeper = guard(game)
    content = game.core.loop.content
    template = content.npcs["npc-sable-enforcer"]
    content.npcs[template.id] = replace(template, behaviours=(Behaviour("guard", {"hostile_all": True}),))
    assert not game.core.npcs.hostile(keeper, body(game, a))
    warden = npc(game, "npc-plainclothes-warden", "warden", (29, 3))
    body(game, a).marked = True
    assert game.core.npcs.hostile(warden, body(game, a))
    body(game, a).marked = False
    player = game.core.characters.players[a.session.player_id]
    player.warden_heat_until = datetime.fromtimestamp(game.core.combat.now()+HEAT_SECONDS, timezone.utc).isoformat()
    assert game.core.npcs.hostile(warden, body(game, a))


@pytest.mark.parametrize("template", ["npc-sodium-regular", "npc-plainclothes-warden", "npc-sable-enforcer"])
def test_game_5_5_keeper_answers_attacks_on_every_row_resident(row, template):
    game, a, _ = row
    keeper = guard(game)
    target = npc(game, template, "victim", (28, 3))
    assert game.core.npcs.truce_keeper(body(game, a), target) == "sable"
    game.core.npcs.provoked(body(game, a), target)
    assert keeper.target == body(game, a).id
    assert game.core.npcs.hostile(keeper, body(game, a))
    assert any(line["text"] == "Sable is coming for you." for line in a.session.log_ring)


def test_game_7_3_truce_marks_hostile_faction_player_then_warns_keeper(row):
    game, a, b = row
    source, target = body(game, a), body(game, b)
    source.faction, target.faction = "sable", "wardens"
    keeper = guard(game)
    assert game.core.combat.would_mark(source, target)
    game.core.combat.mark(source, target)
    game.core.combat.exchange(source, target)
    assert source.marked and keeper.target == source.id
    lines = [line["text"] for line in a.session.log_ring]
    assert lines.index("You break Sodium Row's truce. You are Marked for 15 min.") < lines.index("Sable is coming for you.")


def test_game_7_3_firing_back_at_marked_player_does_not_provoke_keeper(row):
    game, a, b = row
    keeper = guard(game)
    body(game, b).marked = True
    assert not game.core.combat.would_mark(body(game, a), body(game, b))
    game.core.combat.mark(body(game, a), body(game, b))
    game.core.combat.exchange(body(game, a), body(game, b))
    assert not body(game, a).marked and keeper.target is None


def test_ui_2_1_keeper_announces_once_while_hits_refresh_provocation(row):
    game, a, b = row
    keeper = guard(game)
    second_guard = npc(game, "npc-sable-enforcer", "second-keeper", (31, 3))
    second_guard.behaviour["spawner"] = "keeper"
    source, target = body(game, a), body(game, b)
    combat = game.core.combat
    combat.mark(source, target)
    combat.exchange(source, target)
    key = ("sodium-row", "keeper", source.id)
    first_deadline = game.core.npcs.provocations[key]
    game.step()
    for _ in range(3):
        combat.exchange(source, target)
    assert game.core.npcs.provocations[key] > first_deadline
    lines = [line["text"] for line in a.session.log_ring]
    assert lines.count("Sable is coming for you.") == 1
    assert keeper.target == source.id
    # A genuinely expired response is announced again without waiting in real time.
    game.core.npcs.provocations[key] = combat.now() - 1
    combat.exchange(source, target)
    assert [line["text"] for line in a.session.log_ring].count("Sable is coming for you.") == 2


@pytest.mark.parametrize("marked", [False, True])
def test_game_7_3_lattice_burn_uses_target_body_truce_and_keeper(runners, marked):
    game, a, b, _ = runners
    first, second = enter(game, a, "lat-civic-ledger"), enter(game, b, "lat-civic-ledger")
    # Explicit remote-body fixture: the runners share a core, their bodies do not.
    place(game, a, "vatside-clinics", (25, 3))
    place(game, b, "sodium-row", (27, 3))
    source, target = body(game, a), body(game, b)
    source.faction, target.faction = "sable", "wardens"
    source.stance = target.stance = "jacked"
    target.marked = marked
    if marked:
        game.core.characters.players[target.id].marked_until = datetime.fromtimestamp(
            game.core.combat.now() + rules.MARKED_SECONDS, timezone.utc).isoformat()
    for caller in (a, b):
        game.core.characters.players[caller.session.player_id].grade = 5
    keeper = guard(game)
    first.rig = ("prg_burn", None, None)
    cast(game, a, "prg_burn", second.player_id)
    assert second.integrity == 82
    assert source.marked is not marked
    key = ("sodium-row", "keeper", source.id)
    assert (key in game.core.npcs.provocations) is not marked
    assert keeper.zone == "sodium-row" and keeper.target is None
    lines = [line["text"] for line in a.session.log_ring]
    if not marked:
        assert lines.index("You break Sodium Row's truce. You are Marked for 15 min.") < lines.index("Sable is waiting for you on Sodium Row.")
    else:
        assert "Sable is waiting for you on Sodium Row." not in lines


def test_game_5_5_already_hunting_npc_has_no_keeper_warning_or_response(row):
    game, a, _ = row
    keeper = guard(game)
    target = npc(game, "npc-plainclothes-warden", "hunter", (28, 3))
    target.target = body(game, a).id
    target.behaviour["state"] = "hunt"
    assert game.core.npcs.truce_keeper(body(game, a), target) is None
    body(game, a).target = target.id
    assert "Truce:" not in game.core.combat.target_view(body(game, a))["warning"]
    game.core.npcs.provoked(body(game, a), target)
    assert keeper.target is None


@pytest.mark.parametrize("source_safety", ["contested", "open"])
def test_game_7_3_remote_body_marks_and_keeper_waits_in_target_zone(row, source_safety):
    game, a, b = row
    keeper = guard(game)
    outside = game.core.world.zones["vatside-clinics"]
    outside.template = replace(outside.template, meta=replace(outside.template.meta, safety=source_safety))
    place(game, a, "vatside-clinics", (25, 3))
    source, target = body(game, a), body(game, b)
    assert game.core.combat.would_mark(source, target, indirect=True)
    game.core.combat.mark_indirect(source, target)
    assert source.marked and keeper.target is None
    assert any(line["text"] == "Sable is waiting for you on Sodium Row." for line in a.session.log_ring)
    assert game.core.npcs.provocations[("sodium-row", "keeper", source.id)] > game.core.combat.now()
    game.step(20)
    assert keeper.zone == "sodium-row"


@pytest.mark.parametrize("outside", [False, True])
def test_game_7_3_owned_drone_mark_and_keeper_respect_controller_authority(operator, outside):
    from tests.server.test_drone_combat import deploy
    game, a, b, player, engine = operator
    for client, tile in [(a, (25, 3)), (b, (27, 3))]:
        game.core.characters.players[client.session.player_id].grade = 5
        place(game, client, "sodium-row", tile)
    keeper = guard(game)
    drone = deploy(game, a, player, engine)
    if outside:
        place(game, a, "vatside-clinics", (25, 3))
        assert not game.core.combat.would_mark(drone, body(game, b))
        assert game.core.npcs.truce_keeper(drone, body(game, b)) is None
        assert keeper.target is None
    else:
        assert game.core.combat.would_mark(drone, body(game, b))
        game.core.combat.mark(drone, body(game, b))
        game.core.combat.exchange(drone, body(game, b))
        assert body(game, a).marked
        assert ("sodium-row", "keeper", player.id) in game.core.npcs.provocations
        assert keeper.target == drone.id


def test_game_7_3_grade_and_crew_protection_still_apply(row):
    game, a, b = row
    keeper = guard(game)
    game.core.characters.players[b.session.player_id].grade = 4
    assert not game.core.combat.would_mark(body(game, a), body(game, b))
    assert game.core.npcs.truce_keeper(body(game, a), body(game, b)) is None
    game.core.characters.players[b.session.player_id].grade = 5
    game.core.combat.crew_together = lambda first, second: True
    assert not game.core.combat.would_mark(body(game, a), body(game, b))
    assert game.core.npcs.truce_keeper(body(game, a), body(game, b)) is None
    assert keeper.target is None


@pytest.mark.parametrize("safety", ["safe", "pocket", "open"])
def test_game_5_5_truce_validator_rejects_other_zone_classes(repo_root, safety):
    content = load_content(repo_root/"src/blacksite/content")
    zone = content.zones["sodium-row"]
    content.zones[zone.id] = replace(zone, meta=replace(zone.meta, safety=safety))
    assert any("truce requires" in p.message for p in validate(content))


def test_game_5_5_truce_validator_rejects_unknown_keeper(repo_root):
    content = load_content(repo_root/"src/blacksite/content")
    zone = content.zones["sodium-row"]
    content.zones[zone.id] = replace(zone, meta=replace(zone.meta, truce="unknown-keeper"))
    assert any("truce" in p.message for p in validate(content))


def test_game_5_5_shipped_enforcer_never_selects_or_hurts_covered_warden(repo_root):
    content = load_content(repo_root/"src/blacksite/content")
    game = HeadlessServer(content, character_state={})
    caller = game.connect()
    create(game, caller, archetype=3, card="none")
    place(game, caller, "sodium-row", (2, 3))
    zone = game.core.world.zones["sodium-row"]
    keeper = next(a for a in zone.actors.values() if a.behaviour.get("template") == "npc-sable-enforcer")
    warden = next(a for a in zone.actors.values() if a.behaviour.get("template") == "npc-plainclothes-warden")
    game.core.world.enter(keeper, zone.id, (25, 3))
    game.core.world.enter(warden, zone.id, (26, 3))
    health = warden.health
    for _ in range(300):
        game.step()
        game.commit_commerce()
        assert keeper.target != warden.id and warden.target != keeper.id
        assert warden.zone == zone.id and warden.health == health
        assert not warden.revealed_to


@pytest.mark.parametrize("faction", ["ferrymen", "unmoored"])
def test_game_5_5_long_keeper_warning_fits_target_panel(row, faction):
    game, a, _ = row
    zone = game.core.world.zones["sodium-row"]
    zone.template = replace(zone.template, meta=replace(zone.template.meta, truce=faction))
    target = npc(game, "npc-sodium-regular", "victim", (28, 3))
    body(game, a).target = target.id
    warning = game.core.combat.target_view(body(game, a))["warning"]
    assert warning == game.core.loop.content.factions[faction].short + " answers"
    assert len(warning) <= 21


def test_game_7_3_attack_from_truce_to_nontruce_keeps_faction_exemption(row):
    game, a, b = row
    place(game, b, "vatside-clinics", (25, 3))
    body(game, a).faction, body(game, b).faction = "sable", "wardens"
    assert not game.core.combat.would_mark(body(game, a), body(game, b), indirect=True)
    assert game.core.npcs.truce_keeper(body(game, a), body(game, b)) is None



def test_game_5_5_remote_hook_does_not_change_nontruce_npc_response(row):
    game, a, _ = row
    resident = npc(game, "npc-sodium-regular", "outside-resident", (28, 3))
    game.core.world.enter(resident, "vatside-clinics", (26, 3))
    game.core.combat.mark_indirect(body(game, a), resident)
    assert resident.target is None
    assert not body(game, a).marked
