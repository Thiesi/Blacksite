"""Game 8.7: commissioned fixture housing and atomic tenancy lifecycle."""

from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest

from blacksite.content.loader import load_content
from blacksite.content.validate import validate
from blacksite.server.apartments import HousingMenu
from blacksite.server.clock import TICK_HZ
from blacksite.server.housing_rules import LAPSE_SECONDS, WEEK_SECONDS
from blacksite.server.items import make_item
from blacksite.server.protocol import Frame
from scripts.housing_fixture import build_fixture
from tests.character_helpers import act, create, place, state
from tests.harness import HeadlessServer


@pytest.fixture(scope="module")
def housing_content(tmp_path_factory):
    local = tmp_path_factory.mktemp("housing-content")
    shipped = Path(__file__).parents[1]/"src/blacksite/content"
    build_fixture(shipped, local)
    content = load_content(shipped, local)
    problems = validate(content)
    assert not problems, problems
    return content


@pytest.fixture
def housing(housing_content):
    game = HeadlessServer(deepcopy(housing_content), character_state={})
    clients = []
    for user in (1, 2):
        client = game.connect({"user_id": user, "handle": f"Wide界{user}", "node_name": "test"})
        create(game, client, name=f"Resident界{user}")
        clients.append(client)
    return game, *clients


def player(game, client):
    return game.core.characters.players[client.session.player_id]


def rent(game, client, index=1):
    p = player(game, client)
    p.grade, p.chits_bank = 5, 20000
    p.update_personhood(game.core.characters.identity(p.bbs_user_id), game.clock.now_utc())
    place(game, client, "vatside-wake-hall", (6, 8))
    a = game.core.apartments
    unit = a.geometry.units[f"vatside-wake-hall:fixture-home-{index}"]
    a.propose(client.session, "rent", {"target": "fixture-letting", "unit": unit.id})
    assert a.lease(p) is None
    game.commit_commerce()
    return a, a.lease(p), unit


def inside(game, client, unit):
    place(game, client, unit.zone, unit.tile(unit.room.meta.spawn))


def test_game_8_7_closed_home_does_not_freeze_public_geometry(housing):
    game, client, outsider = housing
    apartments, record, unit = rent(game, client)
    inside(game, client, unit)
    actor = game.core.combat.actor(player(game, client))
    zone = game.core.world.zones[unit.zone]
    assert zone.objects[unit.door].open is False
    assert zone.safe_geometry({})
    assert not zone.safe_geometry({actor.position: 'wall'})
    assert not zone.safe_geometry({actor.position: 'hazard'})
    # Recovery from a lapsed private saved position must find public floor.
    returning = game.core.combat.actor(player(game, outsider))
    tile = game.core.world.free_tile(unit.zone, actor.position, returning)
    assert apartments.geometry.containing(unit.zone, tile) is None
    # A closed home still has its existing explicit egress action.
    place(game, client, unit.zone, unit.tile(unit.anchor.vestibule))
    act(game, client, Frame('intent', {'name': 'interact', 'args': {}}))
    assert actor.position == unit.anchor.doorstep


def test_game_8_7_dropped_goods_beside_doorstep_do_not_steal_entry(housing):
    game, client, _ = housing
    apartments, record, unit = rent(game, client)
    p = player(game, client)
    issued = next(i for i in p.inventory if game.core.commerce.items[i].key_for == p.apartment_id)
    place(game, client, unit.zone, (unit.anchor.doorstep[0]-1, unit.anchor.doorstep[1]))
    game.core.commerce.propose(client.session, 'inv.drop', {'item': issued})
    game.commit_commerce()
    cache = next(iter(game.core.commerce.caches))
    # Force the production ordering: a hex world-origin cache sorts before
    # the fixture's home ID, so ID ordering alone selects the wrong target.
    zone = game.core.world.zones[unit.zone]
    obj = zone.objects.pop(cache)
    zone.objects['0-cache-before-door'] = replace(obj, spec=replace(obj.spec, id='0-cache-before-door'))
    place(game, client, unit.zone, unit.anchor.doorstep)
    prediction = game.core.resolve_interaction(client.session, Frame('intent', {'name': 'interact', 'args': {}}))
    assert prediction.route.name == 'apartments' and prediction.choice.focus.id == unit.door
    act(game, client, Frame('intent', {'name': 'interact', 'args': {}}))
    assert unit.region.contains(game.core.combat.actor(p).position)
    assert client.session.id not in game.core.lattice.interlock.log_menus


def test_architecture_6_1_public_crowd_shares_housing_escape_search(housing):
    game, client, _ = housing
    from blacksite.server.world.actors import Actor
    zone = game.core.world.zones['vatside-wake-hall']
    zone.actors.clear()
    for n in range(30):
        actor = Actor(f'crowd:{n}', 'Wide界', zone=zone.id)
        actor.x, actor.y = game.core.world.free_tile(zone.id, zone.template.meta.spawn, actor)
        zone.actors[actor.id] = actor
    calls = 0
    original = zone.entry_policy

    def counted(actor, tile):
        nonlocal calls
        calls += 1
        return original(actor, tile)

    zone.entry_policy = counted
    assert zone.safe_geometry({})
    assert calls < 4*zone.template.width*zone.template.height


def item(game, client, template="wpn_halvard_hv7", quality=1.08, count=1):
    commerce, p = game.core.commerce, player(game, client)
    commerce.serial = max(commerce.serial, 100000)+1
    result = make_item(f"test-origin:item:{commerce.serial}", commerce.content.items[template], p.id, "now", count, quality)
    commerce.items[result.id] = result
    p.inventory.append(result.id)
    return result


def action(game, client, name, record, **args):
    game.core.apartments.propose(client.session, name, {"apartment": record["id"], **args})
    receipts = game.commit_commerce()
    for session in game.core.sessions.active.values():
        session.send_queue.clear()
    return receipts


@pytest.mark.parametrize("calendar", [False, True])
def test_game_3_4_8_7_legal_discharge_required_grade_or_calendar(housing, calendar):
    game, client, _ = housing
    a, p = game.core.apartments, player(game, client)
    place(game, client, "vatside-wake-hall", (6, 8))
    args = {"target": "fixture-letting", "unit": next(iter(a.geometry.units))}
    with pytest.raises(ValueError, match="Legal discharge"):
        a.propose(client.session, "rent", args)
    if calendar:
        game.clock.epoch += timedelta(days=90)
    else:
        p.grade = 5
    game.step()
    p.chits_bank = 1000
    a.propose(client.session, "rent", args)
    game.commit_commerce()
    assert p.apartment_id and p.legal_at


def test_game_8_7_one_apartment_and_failed_signing_keeps_funds_and_cell(housing):
    game, client, _ = housing
    a, record, unit = rent(game, client)
    p = player(game, client)
    assert p.chits_bank == 19700
    assert a.private.core_id(record) in a.content.cores
    with pytest.raises(ValueError, match="already rent"):
        a.propose(client.session, "rent", {"target": "fixture-letting", "unit": unit.id})
    assert len(a.state["apartments"]) == 1


def test_game_8_7_failed_rental_does_not_allocate_core_or_money(housing):
    game, client, _ = housing
    p = player(game, client)
    p.grade, p.chits_bank = 5, 500
    game.step()
    place(game, client, "vatside-wake-hall", (6, 8))
    a = game.core.apartments
    unit = next(iter(a.geometry.units.values()))
    before = deepcopy(a.state), deepcopy(a.commerce.items), p.chits_bank
    a.propose(client.session, "rent", {"target": "fixture-letting", "unit": unit.id})
    game.commit_commerce(error=True)
    assert (a.state, a.commerce.items, p.chits_bank) == before
    assert not p.apartment_id
    assert a.lat.sectors.cells[unit.anchor.sector][unit.anchor.cell].core_id is None


def test_game_8_7_lazy_rent_bank_then_hand_and_stable_discount_invoice(housing):
    game, client, _ = housing
    a, record, unit = rent(game, client)
    p = player(game, client)
    p.chits_bank, p.chits_hand = 100, 200
    game.clock.epoch += timedelta(days=7)
    a.rent_modifier = lambda p, due: .9
    assert not a.ensure_rent(p.id)
    assert (p.chits_bank, p.chits_hand) == (100, 200)
    game.commit_commerce()
    assert (p.chits_bank, p.chits_hand) == (0, 30)
    assert a.lease(p)["last_invoice"]["amount"] == 270
    a.rent_modifier = lambda p, due: 1
    game.clock.epoch += timedelta(days=7)
    a.ensure_rent(p.id)
    game.commit_commerce()
    assert a.lease(p)["invoice"]["amount"] == 300
    a.rent_modifier = lambda p, due: .9
    p.chits_bank = 300
    a.ensure_rent(p.id)
    game.commit_commerce()
    assert p.chits_bank == 0  # Already issued invoice cannot be rewritten.


@pytest.mark.parametrize("index,slots,tier,rent_price", [(1, 40, 1, 300), (2, 80, 2, 900), (3, 120, 3, 2200)])
def test_game_8_7_storage_capacity_per_class_and_protected_half(housing, index, slots, tier, rent_price):
    game, client, _ = housing
    a, record, unit = rent(game, client, index)
    assert (unit.definition.storage_slots, record["tier"], record["last_invoice"]["amount"]) == (slots, tier, rent_price)
    inside(game, client, unit)
    for n in range(slots):
        supplied = item(game, client)
        supplied.secured = n < slots//2
        action(game, client, "deposit", record, item=supplied.id)
    assert len(a.lease(player(game, client))["storage"]) == slots
    extra = item(game, client)
    with pytest.raises(ValueError, match="full"):
        action(game, client, "deposit", record, item=extra.id)
    unsecured = a.lease(player(game, client))["storage"][-1]
    with pytest.raises(ValueError, match="Protected"):
        action(game, client, "secure", record, item=unsecured)


def test_game_8_7_storage_and_carried_secured_limits_are_independent(housing):
    game, client, _ = housing
    a, record, unit = rent(game, client)
    inside(game, client, unit)
    rifle = item(game, client)
    rifle.secured = True
    action(game, client, "deposit", record, item=rifle.id)
    p = player(game, client)
    for _ in range(3):
        item(game, client).secured = True
    with pytest.raises(ValueError, match="secured slots"):
        action(game, client, "withdraw", record, item=rifle.id)
    assert a.commerce.items[rifle.id].secured
    action(game, client, "secure", record, item=rifle.id)
    action(game, client, "withdraw", record, item=rifle.id)
    assert rifle.id in p.inventory and a.commerce.items[rifle.id].quality == 1.08


def test_game_8_7_two_weeks_lapsed_evicts_safe_and_items_to_protected_impound(housing):
    game, client, _ = housing
    a, record, unit = rent(game, client)
    p = player(game, client)
    inside(game, client, unit)
    rifle = item(game, client)
    action(game, client, "deposit", record, item=rifle.id)
    p.chits_hand = 90
    action(game, client, "safe_deposit", record, amount=90)
    p.chits_hand = p.chits_bank = 0
    game.clock.epoch += timedelta(days=15)
    a.ensure_rent(p.id)
    game.commit_commerce()
    assert a.lease(p) and a.lease(p)["lapsed_since"] == record["rent_paid_until"]
    game.clock.epoch += timedelta(days=7)
    a.ensure_rent(p.id)
    game.commit_commerce()
    assert p.apartment_id is None and p.tile == unit.anchor.doorstep
    assert a.private.core_id(record) not in a.content.cores
    impound = a.state["impounds"][p.id]
    assert impound["chits"] == 90 and rifle.id in impound["items"]
    assert a.commerce.items[rifle.id].quality == 1.08
    assert a.commerce.items[rifle.id].owner == "impound:"+p.id
    place(game, client, unit.zone, (9, 8))
    a.propose(client.session, "reclaim_chits", {"target": "fixture-bank"})
    game.commit_commerce()
    assert p.chits_bank == 90
    fee = impound["items"][rifle.id]["fee"]
    assert fee == a.content.items[rifle.template].base_price//10
    p.chits_bank = fee
    a.propose(client.session, "reclaim", {"target": "fixture-bank", "item": rifle.id})
    game.commit_commerce()
    assert p.chits_bank == 0 and rifle.id in p.inventory
    assert a.commerce.items[rifle.id].quality == 1.08
    assert not a.state["impounds"][p.id]["items"]


def test_game_8_7_stale_resident_menu_and_uninvited_entry_rejected(housing):
    game, owner, visitor = housing
    a, record, unit = rent(game, owner)
    place(game, visitor, unit.zone, unit.anchor.doorstep)
    with pytest.raises(ValueError, match="Locked. Tier 1"):
        a.door(visitor.session, unit)
    with pytest.raises(ValueError, match="blocked"):
        inside(game, visitor, unit)
    inside(game, owner, unit)
    with pytest.raises(ValueError, match="resident"):
        a.resident(visitor.session, record["id"])
    action(game, owner, "surrender", record)
    assert player(game, owner).apartment_id is None
    with pytest.raises(ValueError, match="resident"):
        action(game, owner, "key", record)


def test_game_8_7_lock_800_and_flat_core_upgrade_2000(housing):
    game, client, _ = housing
    a, record, unit = rent(game, client, 2)
    inside(game, client, unit)
    before = player(game, client).chits_bank
    action(game, client, "upgrade_core", record)
    assert a.lease(player(game, client))["tier"] == 3
    assert player(game, client).chits_bank == before-2000
    action(game, client, "upgrade_lock", record)
    assert a.lease(player(game, client))["lock_tier"] == 3
    assert player(game, client).chits_bank == before-2800
    assert any(i.key_for == record["id"] and i.key_tier == 3 for i in a.commerce.items.values())


def test_game_8_7_key_visitors_only_vestibule_thirty_seconds(housing):
    game, owner, visitor = housing
    a, record, unit = rent(game, owner)
    p, v = player(game, owner), player(game, visitor)
    key = next(a.commerce.items[i] for i in p.inventory if a.commerce.items[i].key_for == record["id"])
    p.inventory.remove(key.id)
    v.inventory.append(key.id)
    key.owner = v.id
    place(game, visitor, unit.zone, unit.anchor.doorstep)
    a.door(visitor.session, unit)
    game.commit_commerce()
    actor = game.core.combat.actor(v)
    assert actor.position == unit.tile(unit.anchor.vestibule)
    assert not a.geometry.can_enter(actor, unit.zone, unit.tile(unit.room.meta.spawn))
    with pytest.raises(ValueError, match="resident"):
        a.resident(visitor.session, record["id"])
    game.clock.epoch += timedelta(seconds=31)
    game.step()
    assert not unit.region.contains(actor.position)


def test_game_8_7_surrender_moves_goods_without_fee_and_reissued_tenancy_is_unique(housing):
    game, client, _ = housing
    a, record, unit = rent(game, client)
    inside(game, client, unit)
    supplied = item(game, client)
    action(game, client, "deposit", record, item=supplied.id)
    action(game, client, "surrender", record)
    assert a.state["impounds"][player(game, client).id]["items"][supplied.id]["fee"] == 0
    _, next_record, _ = rent(game, client)
    assert next_record["id"] != record["id"]


def test_game_8_7_failed_storage_and_eviction_leave_live_goods_and_rent_intact(housing):
    game, client, _ = housing
    a, record, unit = rent(game, client)
    inside(game, client, unit)
    supplied = item(game, client)
    a.propose(client.session, "deposit", {"apartment": record["id"], "item": supplied.id})
    game.commit_commerce(error=True)
    assert supplied.id in player(game, client).inventory and not a.lease(player(game, client))["storage"]
    action(game, client, "deposit", record, item=supplied.id)
    p = player(game, client)
    p.chits_bank = p.chits_hand = 0
    game.clock.epoch += timedelta(days=22)
    before = deepcopy(a.state), deepcopy(a.commerce.items), p.apartment_id
    a.ensure_rent(p.id)
    game.commit_commerce(error=True)
    assert (a.state, a.commerce.items, p.apartment_id) == before
    a.ensure_rent(p.id)
    game.commit_commerce()
    assert p.apartment_id is None


def test_game_8_7_competing_rentals_revalidate_the_same_unit(housing):
    game, first, second = housing
    a = game.core.apartments
    args = {"target": "fixture-letting", "unit": next(iter(a.geometry.units))}
    for client in (first, second):
        p = player(game, client)
        p.grade, p.chits_bank = 5, 1000
        game.step()
        place(game, client, "vatside-wake-hall", (6, 8) if client is first else (7, 8))
    a.propose(first.session, "rent", args)
    a.propose(second.session, "rent", args)
    game.commit_commerce()
    assert player(game, first).apartment_id
    assert player(game, second).apartment_id is None and player(game, second).chits_bank == 1000
    assert len(a.state["apartments"]) == 1


def test_game_8_7_bed_safe_logout_returns_to_the_same_room(housing):
    game, client, _ = housing
    a, record, unit = rent(game, client)
    inside(game, client, unit)
    actor = game.core.combat.actor(player(game, client))
    a.select(client.session, HousingMenu("apartment", record["id"]), "enter", "logout")
    assert client.session.closed
    game.core.sessions.disconnect(client.session)
    assert actor.id not in game.core.world.actors
    again = game.connect(client.session.door_info)
    game.step()
    assert game.core.combat.actor(player(game, again)).position == unit.tile(unit.room.meta.spawn)


def test_game_8_7_visitor_cannot_see_or_target_resident_even_with_scouting(housing):
    from blacksite.server.world.sight import sees_actor
    from blacksite.server.views.zone_view import Perception, build
    game, owner, visitor = housing
    a, record, unit = rent(game, owner)
    inside(game, owner, unit)
    place(game, visitor, unit.zone, unit.anchor.doorstep)
    target, observer = game.core.combat.actor(player(game, owner)), game.core.combat.actor(player(game, visitor))
    assert target.behaviour["private_owner"] == target.id
    assert not sees_actor(observer, target, {target.position}, 100)
    body = build(observer, game.core.world.zones[unit.zone], Perception(), a.content, 80, 24,
                 "12:00", False, game.clock.now_tick(), {target.position}, {target.id})
    assert target.id not in {actor["id"] for actor in body["actors"]}
    observer.target = target.id
    assert game.core.combat.target_view(observer) is None


def test_game_8_7_passkey_lock_tier_and_no_resident_privileges(housing):
    from blacksite.server.lattice.presence import Presence
    game, owner, visitor = housing
    a, record, unit = rent(game, owner)
    inside(game, owner, unit)
    action(game, owner, "upgrade_lock", record)
    presence = Presence("fixture-presence", player(game, visitor).id, unit.anchor.sector, unit.anchor.cell, ())
    presence.core = a.private.core_id(record)
    with pytest.raises(ValueError, match="Tier 3"):
        a.interlock.open_vestibule(presence, key_tier=1)
    a.interlock.open_vestibule(presence, key_tier=3)
    game.commit_commerce()
    assert a.lease(player(game, owner))["vestibule_access_until"][presence.player_id] == a.now()+30
    place(game, visitor, unit.zone, unit.anchor.doorstep)
    a.door(visitor.session, unit)
    assert game.core.combat.actor(player(game, visitor)).position == unit.tile(unit.anchor.vestibule)
    assert not a.private.manifest(presence)  # The vestibule is not the index.


def test_game_8_7_persistence_storage_safe_eviction_and_reclaim_round_trip(housing, housing_content, tmp_path):
    from blacksite.server.storage.db import Storage
    game, client, _ = housing
    a, record, unit = rent(game, client)
    inside(game, client, unit)
    supplied = item(game, client, "drn_sable_stinger", quality=1.13)
    supplied.health = 17
    action(game, client, "deposit", record, item=supplied.id)
    p = player(game, client)
    p.chits_hand = 137
    action(game, client, "safe_deposit", record, amount=137)
    storage = Storage(tmp_path/"world.db", game.clock)
    try:
        live = state(game)
        for row in live["players"]:
            storage.mark_dirty("players", row["id"], row)
        for iid, row in a.commerce.items.items():
            storage.mark_dirty("items", iid, row.record())
        for user, identity in live["identities"].items():
            storage.mark_dirty("identities", user, identity)
        storage.mark_dirty("meta", "interlock_state", a.state)
        storage.flush_now()
        saved = storage.character_state()
        restarted = HeadlessServer(deepcopy(housing_content), character_state=saved, clock=game.clock)
        other = restarted.core.apartments
        resident = restarted.core.characters.players[p.id]
        assert other.lease(resident)["safe_chits"] == 137
        assert other.commerce.items[supplied.id].quality == 1.13 and other.commerce.items[supplied.id].health == 17
        resident.chits_bank = resident.chits_hand = 0
        game.clock.epoch += timedelta(days=22)
        other.ensure_rent(resident.id)
        effect = restarted.core.commerce.outbox[0]
        storage.commerce_write(restarted.core.commerce.prepare(effect))
        restarted.commit_commerce()
        saved = storage.character_state()
        assert saved["players"][0]["apartment_id"] is None
        again = HeadlessServer(deepcopy(housing_content), character_state=saved, clock=game.clock)
        assert again.core.commerce.items[supplied.id].health == 17
        assert supplied.id in again.core.apartments.state["impounds"][p.id]["items"]
        assert a.private.core_id(record) not in again.core.loop.content.cores
        assert sum(i.id == supplied.id for i in again.core.commerce.items.values()) == 1
        returning = again.connect(client.session.door_info)
        again.step()
        place(again, returning, unit.zone, (9, 8))
        returned_player = again.core.characters.players[p.id]
        fee = again.core.apartments.state["impounds"][p.id]["items"][supplied.id]["fee"]
        returned_player.chits_bank = fee
        again.core.apartments.propose(returning.session, "reclaim", {"target": "fixture-bank", "item": supplied.id})
        effect = again.core.commerce.outbox[0]
        storage.commerce_write(again.core.commerce.prepare(effect))
        again.commit_commerce()
        final = storage.character_state()
        persisted_item = next(row for row in final["items"] if row["id"] == supplied.id)
        assert persisted_item["owner"] == p.id and persisted_item["quality"] == 1.13 and persisted_item["health"] == 17
        assert supplied.id in next(row for row in final["players"] if row["id"] == p.id)["inventory"]
        assert supplied.id not in final["interlock"]["impounds"][p.id]["items"]
    finally:
        storage.close()


def test_game_6_4_8_7_one_unit_cap_belongs_to_physical_home_across_tenancies(housing):
    from blacksite.server.lattice.presence import Presence, Procedure
    game, owner, thief = housing
    a, record, unit = rent(game, owner)
    inside(game, owner, unit)
    supplied = item(game, owner, "ammo_9x", count=3)
    action(game, owner, "deposit", record, item=supplied.id)
    cid = a.private.core_id(record)
    presence = Presence("fixture-intruder", player(game, thief).id, unit.anchor.sector, unit.anchor.cell, (),
                        core=cid, instance=cid, room="index")
    a.lat.encounters.instances[cid] = a.lat.encounters.spawn(cid, cid)
    for ice in a.lat.encounters.instances[cid].ice.values():
        ice.integrity = 0
    a.private.complete_theft(presence, Procedure("theft", supplied.id, 0, cid, 0))
    game.commit_commerce()
    assert a.commerce.items[supplied.id].stack == 2
    hacked_at = a.now()
    assert a.state["unit_hacks"][unit.id] == hacked_at
    action(game, owner, "surrender", record)
    _, new_record, _ = rent(game, owner)
    assert new_record["last_hacked_at"] == hacked_at
    assert new_record["id"] != record["id"]


def test_game_8_7_ammunition_impound_fee_counts_packs_and_rounds_halves_up(housing):
    from blacksite.server.housing_rules import reclaim_fee
    game, client, _ = housing
    supplied = item(game, client, "ammo_9x", count=10)
    template = game.core.loop.content.items[supplied.template]
    assert reclaim_fee(supplied, template) == int(template.base_price*10/template.stack_max/10+.5)


def test_game_8_7_deleted_character_releases_lease_after_durable_deletion(housing):
    game, client, _ = housing
    a, record, unit = rent(game, client)
    inside(game, client, unit)
    supplied = item(game, client)
    action(game, client, "deposit", record, item=supplied.id)
    game.core.sessions.disconnect(client.session)
    game.core.characters.players.pop(record["resident"])  # Fixture: deletion already committed.
    game.step()
    game.commit_commerce()
    assert not a.state["apartments"] and supplied.id not in a.commerce.items
    assert a.private.core_id(record) not in a.content.cores


def test_game_8_7_safe_chits_survive_actual_clone_settlement(housing):
    game, resident, attacker = housing
    a, record, unit = rent(game, resident)
    inside(game, resident, unit)
    victim = player(game, resident)
    victim.chits_hand = 100
    action(game, resident, "safe_deposit", record, amount=100)
    player(game, attacker).grade = 5
    place(game, resident, "vatside-clinics", (27, 4))
    place(game, attacker, "vatside-clinics", (25, 4))
    body = game.core.combat.actor(victim)
    game.core.combat.hurt(game.core.combat.actor(player(game, attacker)), body, 10000)
    assert body.stance == "down"
    game.step(50)
    game.commit_commerce()
    assert body.stance == "dead"
    assert a.lease(victim)["safe_chits"] == 100


def test_game_8_7_saved_vestibule_control_recomposes_on_restart(housing, housing_content):
    from blacksite.server.lattice.presence import Presence
    game, owner, visitor = housing
    a, record, unit = rent(game, owner)
    presence = Presence("fixture-passkey", player(game, visitor).id, unit.anchor.sector, unit.anchor.cell, (),
                        core=a.private.core_id(record))
    a.interlock.open_vestibule(presence, key_tier=3)
    game.commit_commerce()
    saved = state(game)
    saved["interlock"] = deepcopy(a.state)
    restarted = HeadlessServer(deepcopy(housing_content), character_state=saved, clock=game.clock)
    door = restarted.core.world.zones[unit.zone].objects[unit.door]
    assert door.open
    game.clock.epoch += timedelta(seconds=31)
    restarted.step()
    restarted.commit_commerce()
    assert not door.open


@pytest.mark.parametrize("broken", ["shared_cell", "public_object", "missing_room", "bad_doorstep"])
def test_entities_1_1_active_housing_rejects_unresolved_or_obstructed_anchors(housing_content, broken):
    from blacksite.content.schema import ObjectSpec
    content = deepcopy(housing_content)
    zone = content.zones["vatside-wake-hall"]
    objects = list(zone.meta.objects)
    homes = [index for index, obj in enumerate(objects) if obj.housing]
    first, second = objects[homes[0]], objects[homes[1]]
    if broken == "shared_cell":
        objects[homes[1]] = replace(second, housing=replace(second.housing, cell=first.housing.cell))
    elif broken == "public_object":
        objects.append(ObjectSpec("fixture-public", first.housing.origin, "terminal", essential=True))
    elif broken == "missing_room":
        objects[homes[0]] = replace(first, housing=replace(first.housing, room="missing-room"))
    else:
        objects[homes[0]] = replace(first, housing=replace(first.housing, doorstep=(18, 8)))
    content.zones[zone.id] = replace(zone, meta=replace(zone.meta, objects=tuple(objects)))
    assert validate(content)
