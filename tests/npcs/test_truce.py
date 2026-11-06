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


@pytest.mark.parametrize("owner_zone,drone_zone,hostile,marks,answers", [
    ("vatside-clinics", "sodium-row", True, False, False),
    ("vatside-clinics", "sodium-row", False, True, False),
    ("sodium-row", "vatside-clinics", True, True, True),
])
@pytest.mark.parametrize("path", ["direct", "remote", "machinery"])
def test_game_7_3_defending_drone_uses_owner_body_for_mark_and_keeper(
        operator, owner_zone, drone_zone, hostile, marks, answers, path):
    from tests.server.test_drone_combat import deploy
    game, a, b, player, engine = operator
    for caller in (a, b):
        game.core.characters.players[caller.session.player_id].grade = 5
    place(game, a, drone_zone, (25, 3))
    drone = deploy(game, a, player, engine)
    engine.command(player, drone.behaviour["item"], "hold")
    game.commit_commerce()
    place(game, a, owner_zone, (25, 3))
    place(game, b, drone_zone, (27, 3))
    source, owner = body(game, b), body(game, a)
    source.faction, owner.faction = "sable", "wardens" if hostile else None
    game.core.characters.players[source.id].faction = source.faction
    player.faction = owner.faction
    keeper = guard(game)
    combat = game.core.combat
    assert combat.legal(source, drone)
    assert combat.would_mark(source, drone) is marks
    assert game.core.npcs.truce_keeper(source, drone) == ("sable" if answers else None)
    if path == "direct":
        combat.mark(source, drone)
        combat.exchange(source, drone)
    elif path == "remote":
        combat.mark_indirect(source, drone)
        combat.mark_indirect(source, drone)
    else:
        physical = game.core.lattice.interlock.physical
        before = drone.health
        for _ in range(2):
            physical.pending_damage[drone.id, source.id, drone.zone] = 1
            physical.flush_hits()
            game.commit_commerce()
        assert drone.health == before - 2
    assert source.marked is marks
    assert keeper.target is None
    assert (("sodium-row", "keeper", source.id) in game.core.npcs.provocations) is answers
    lines = [line["text"] for line in b.session.log_ring]
    if answers:
        assert "You break Sodium Row's truce. You are Marked for 15 min." in lines
        assert lines.count("Sable is waiting for you on Sodium Row.") == 1
    else:
        assert not any("Sable is " in line for line in lines)
        if marks:
            assert "You are Marked for fifteen minutes." in lines


def test_ui_2_1_no_keeper_announcement_without_keeper_guards(runners):
    game, a, b, _ = runners
    for caller, tile in ((a, (25, 3)), (b, (27, 3))):
        game.core.characters.players[caller.session.player_id].grade = 5
        place(game, caller, "sodium-row", tile)
    for _ in range(3):
        game.core.combat.mark(body(game, a), body(game, b))
        game.core.combat.exchange(body(game, a), body(game, b))
    assert body(game, a).marked
    assert not any("Sable is coming" in line["text"] for line in a.session.log_ring)


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


@pytest.mark.parametrize("alert", ["marked", "heat"])
def test_ui_2_1_truce_warning_keeps_warden_cover_until_provocation(row, alert):
    game, a, _ = row
    source = body(game, a)
    player = game.core.characters.players[source.id]
    if alert == "marked":
        source.marked = True
        player.marked_until = datetime.fromtimestamp(
            game.core.combat.now() + rules.MARKED_SECONDS, timezone.utc).isoformat()
    else:
        player.warden_heat_until = datetime.fromtimestamp(
            game.core.combat.now() + HEAT_SECONDS, timezone.utc).isoformat()
    keeper = guard(game)
    regular = npc(game, "npc-sodium-regular", "regular", (28, 3))
    warden = npc(game, "npc-plainclothes-warden", "covered-warden", (29, 3))
    assert game.core.npcs.hostile(warden, source)
    views = []
    for target in (regular, warden):
        source.target = target.id
        view = game.core.combat.target_view(source)
        views.append({key: view[key] for key in ("name", "relation", "warning")})
    assert views[0] == views[1] == {
        "name": "Sodium regular", "relation": "neutral", "warning": "Truce: Sable answers"}
    assert source.id not in warden.revealed_to
    game.core.npcs.provoked(source, warden)
    assert keeper.target == source.id
    assert game.core.npcs.hostile(keeper, source)


@pytest.mark.parametrize("alert", ["marked", "heat"])
@pytest.mark.parametrize("closer,revealed", [("regular", False), ("warden", False), ("regular", True)])
def test_ui_2_1_tab_respects_warden_cover_and_distance(row, alert, closer, revealed):
    game, a, b = row
    place(game, b, "vatside-clinics", (25, 3))
    source = body(game, a)
    regular = npc(game, "npc-sodium-regular", "regular", (27 if closer == "regular" else 29, 3))
    warden = npc(game, "npc-plainclothes-warden", "covered-warden", (27 if closer == "warden" else 29, 3))
    player = game.core.characters.players[source.id]
    if alert == "marked":
        source.marked = True
        player.marked_until = datetime.fromtimestamp(
            game.core.combat.now() + rules.MARKED_SECONDS, timezone.utc).isoformat()
    else:
        player.warden_heat_until = datetime.fromtimestamp(
            game.core.combat.now() + HEAT_SECONDS, timezone.utc).isoformat()
    if revealed:
        game.core.combat.reveal(warden, source)
    assert game.core.combat.relation(source, warden) == "hostile"
    source.target = warden.id
    assert game.core.combat.target_view(source)["relation"] == ("hostile" if revealed else "neutral")
    first = warden if revealed or closer == "warden" else regular
    second = regular if first is warden else warden
    source.target = None
    game.core.combat.select(source)
    assert source.target == first.id
    game.core.combat.select(source)
    assert source.target == second.id
    game.core.combat.select(source, backwards=True)
    assert source.target == first.id
    assert (source.id in warden.revealed_to) is revealed


def test_game_5_5_live_provocation_exempts_npc_even_before_hunt(row):
    game, a, _ = row
    source = body(game, a)
    target = npc(game, "npc-plainclothes-warden", "provoked-warden", (28, 3))
    keeper = guard(game)
    source.target = target.id
    key = (target.zone, str(target.behaviour["spawner"]), source.id)
    game.core.npcs.provocations[key] = game.core.combat.now() + HEAT_SECONDS
    assert target.target is None
    assert game.core.combat.target_view(source)["warning"] == ""
    assert game.core.npcs.truce_keeper(source, target) is None
    # An expired entry is not a continuing provocation.
    game.core.npcs.provocations[key] = game.core.combat.now() - 1
    assert game.core.combat.target_view(source)["warning"] == "Truce: Sable answers"
    game.core.npcs.provoked(source, target)
    assert keeper.target == source.id


@pytest.mark.parametrize("victim_kind", ["player", "sable-npc"])
def test_game_5_5_remote_truce_attack_preserves_local_chase(row, victim_kind):
    game, a, b = row
    keeper = guard(game)
    local = body(game, a)
    game.core.combat.mark(local, body(game, b))
    game.core.combat.exchange(local, body(game, b))
    zone = game.core.world.zones["sodium-row"]
    far = next((x, y) for y in range(zone.template.height) for x in range(zone.template.width)
               if zone.passable((x, y)) and zone.allows_hostile((x, y))
               and (x - keeper.x)**2 + (y - keeper.y)**2 > 1600)
    place(game, a, zone.id, far)
    assert not game.core.combat.visible(keeper, local)
    remote = game.connect({"user_id": 3, "handle": "Remote", "node_name": "S38"})
    create(game, remote, card="none")
    game.core.characters.players[remote.session.player_id].grade = 5
    place(game, remote, "vatside-clinics", (25, 3))
    before = (keeper.target, dict(keeper.behaviour))
    victim = (body(game, b) if victim_kind == "player" else
              npc(game, "npc-sable-enforcer", "remote-victim", (28, 4)))
    game.core.combat.mark_indirect(body(game, remote), victim)
    assert (keeper.target, keeper.behaviour) == before
    assert (zone.id, "keeper", body(game, remote).id) in game.core.npcs.provocations
    game.core.npcs.evaluate(keeper, zone, game.clock.now_tick())
    assert keeper.target == local.id and keeper.behaviour["state"] == "hunt"


@pytest.mark.parametrize("zone_id,hostile,marks", [
    ("sodium-row", True, True),
    ("vatside-clinics", True, False),
    ("vatside-clinics", False, True),
])
def test_ui_2_1_drone_order_menu_uses_actual_mark_rule(operator, zone_id, hostile, marks):
    from tests.server.test_drone_combat import deploy
    game, a, b, player, engine = operator
    for caller, tile in ((a, (25, 3)), (b, (27, 3))):
        game.core.characters.players[caller.session.player_id].grade = 5
        place(game, caller, zone_id, tile)
    player.faction = body(game, a).faction = "sable"
    game.core.characters.players[b.session.player_id].faction = body(game, b).faction = "wardens" if hostile else None
    drone = deploy(game, a, player, engine)
    body(game, a).target = body(game, b).id
    engine.menus[a.session.id] = 0
    engine.menus[a.session.id] = next(index for index, row in enumerate(engine.view(a.session)["rows"])
                                    if row["id"] == drone.behaviour["item"])
    detail = " ".join(engine.view(a.session)["detail"].split())
    assert game.core.combat.would_mark(body(game, a), body(game, b), indirect=True) is marks
    expected = "order marks you for 15 minutes" if marks else "order gives a two-second warning"
    assert expected in detail


def test_ui_2_1_drone_target_warns_open_attacker_about_contested_owner(operator):
    from tests.server.test_drone_combat import deploy
    game, a, b, player, engine = operator
    for caller in (a, b):
        game.core.characters.players[caller.session.player_id].grade = 5
    place(game, a, "sodium-row", (25, 3))
    drone = deploy(game, a, player, engine)
    engine.command(player, drone.behaviour["item"], "hold")
    game.commit_commerce()
    place(game, a, "vatside-clinics", (25, 3))
    zone = game.core.world.zones["sodium-row"]
    # Explicit open variant, not shipped truce geography.
    zone.template = replace(zone.template, meta=replace(zone.template.meta, safety="open", truce=None, pockets=()))
    place(game, b, zone.id, (27, 3))
    source = body(game, b)
    source.target = drone.id
    assert game.core.combat.legal(source, drone)
    assert game.core.combat.target_view(source)["warning"] == "Firing marks you"
    game.core.combat.mark(source, drone)
    assert source.marked


@pytest.mark.parametrize("indirect", [False, True])
def test_game_5_5_attack_on_nontruce_player_never_provokes_npcs(row, indirect):
    game, a, b = row
    for caller, tile in ((a, (25, 3)), (b, (27, 3))):
        place(game, caller, "vatside-clinics", tile)
    keeper = guard(game)
    game.core.world.enter(keeper, "vatside-clinics", (30, 3))
    if indirect:
        game.core.combat.mark_indirect(body(game, a), body(game, b))
    else:
        game.core.combat.mark(body(game, a), body(game, b))
        game.core.combat.exchange(body(game, a), body(game, b))
    assert body(game, a).marked
    assert keeper.target is None
    assert not game.core.npcs.provocations
