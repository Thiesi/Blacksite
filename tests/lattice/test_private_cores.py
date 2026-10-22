"""Game 6.4: the apartment, rather than each intruder, owns the allowance."""

from copy import deepcopy
from dataclasses import replace

import pytest

from blacksite.content.schema import ObjectSpec
from blacksite.server.clock import TICK_HZ
from blacksite.server.items import make_item
from blacksite.server.world.zone import ObjectState
from tests.character_helpers import place, state
from tests.harness import HeadlessServer
from tests.lattice.test_engine import actor, intent, jack, runners
from tests.lattice.test_encounters import cast


def apartment_fixture(game, resident):
    interlock = game.core.lattice.interlock
    zone = game.core.world.zones["terraces-blocks"]
    occupied = {o.spec.tile for o in zone.objects.values()} | {e.tile for e in zone.template.meta.exits}
    tiles = [(x, y) for y in range(2, zone.template.height-2) for x in range(2, zone.template.width-2)
             if zone.passable((x, y)) and (x, y) not in occupied][:3]
    specs = tuple(ObjectSpec("private-fixture-"+kind, tile, kind, {"open": False})
                  for kind, tile in zip(("hardware", "door", "light"), tiles))
    zone.template = replace(zone.template, meta=replace(zone.template.meta, objects=zone.template.meta.objects+specs))
    game.core.loop.content.zones[zone.id] = zone.template
    for spec in specs:
        obj = zone.objects[spec.id] = ObjectState(spec, False if spec.kind == "door" else None)
        if spec.kind == "door":
            zone.doors[spec.tile] = obj
    cell = next(c for c in interlock.lat.sectors.records["lat-terraces"].cells
                if c.access_kind == "public" and not c.core_id and not c.core_placeholder)
    record = {"id": "fixture", "resident": resident.session.player_id, "tier": 1,
              "sector": "lat-terraces", "cell": cell.id, "zone": zone.id,
              "door": specs[1].id, "light": specs[2].id, "hardware": specs[0].id,
              "storage": ["fixture:stack", "fixture:secured", "fixture:impounded"]}
    template = next(t for t in interlock.content.items.values() if t.stack_max >= 3 and not t.secured_default)
    for iid, secured, owner in (("fixture:stack", False, "apartment:fixture"),
                                 ("fixture:secured", True, "apartment:fixture"),
                                 ("fixture:impounded", False, "impound:fixture")):
        item = make_item(iid, template, owner, game.clock.now_utc().isoformat(), 3)
        item.secured = secured
        interlock.commerce.items[iid] = item
    interlock.private.register(record)
    game.commit_commerce()
    return interlock, record


def private_entry(game, client, record):
    place(game, client, "core-plaza", game.core.world.free_tile("core-plaza", (30, 5)))
    presence = jack(game, client)
    presence.sector, presence.cell = "lat-terraces", record["cell"]
    intent(game, client, "lat.enter", core="lat-apartment-fixture")
    assert presence.core == "lat-apartment-fixture"
    instance = game.core.lattice.encounters.core(presence)
    for ice in instance.ice.values():
        ice.integrity = 0
    presence.room = "index"
    return presence


def test_game_6_4_private_manifest_daily_race_and_atomic_unit(runners):
    game, a, b, c = runners
    interlock, record = apartment_fixture(game, a)
    one, two = private_entry(game, b, record), private_entry(game, c, record)
    before_xp = {p.player_id: game.core.characters.players[p.player_id].xp for p in (one, two)}
    assert [i.id for i in interlock.private.manifest(one)] == ["fixture:stack"]
    template = interlock.commerce.items["fixture:stack"].template
    initial = sum(i.stack for i in interlock.commerce.items.values() if i.template == template and i.owner in (one.player_id, two.player_id))
    for client in (b, c):
        intent(game, client, "lat.theft", item="fixture:stack")
    game.step(3*TICK_HZ)
    assert game.core.commerce.pending
    receipts = game.commit_commerce()
    game.step()
    game.commit_commerce()
    assert len(receipts) == 1
    assert receipts[0]["player"]["xp"] == before_xp[receipts[0]["player"]["id"]]+40*record["tier"]
    assert sum(game.core.characters.players[p.player_id].xp for p in (one,two)) == sum(before_xp.values())+40*record["tier"]
    assert game.core.commerce.items["fixture:stack"].stack == 2
    apt = interlock.state["apartments"]["fixture"]
    assert len(apt["hack_log"]) == 1
    transferred = sum(i.stack for i in interlock.commerce.items.values()
                      if i.template == template and i.owner in (one.player_id, two.player_id))
    assert transferred == initial+1
    assert receipts[0]["interlock_state"]["apartments"]["fixture"]["last_hacked_at"] == apt["last_hacked_at"]
    assert any("Someone was in your core" in line["text"] for f in game.frames_for(a) if f.type == "log" for line in f.data["lines"])
    with pytest.raises(ValueError, match="24 hours"):
        interlock.private.start_theft(two, "fixture:stack")
    interlock.private.open_log(a.session, "fixture")
    view = interlock.sim.external_views[a.session.id][1]
    assert "Someone was in your core" in view["rows"][0]["cells"][0]
    with pytest.raises(ValueError, match="resident"):
        interlock.private.open_log(b.session, "fixture")


def test_game_6_4_private_failed_receipt_leaves_stack_and_log(runners):
    game, a, b, c = runners
    interlock, record = apartment_fixture(game, a)
    presence = private_entry(game, b, record)
    before_xp = game.core.characters.players[presence.player_id].xp
    intent(game, b, "lat.theft", item="fixture:stack")
    game.step(3*TICK_HZ)
    game.commit_commerce(error=True)
    assert game.core.characters.players[presence.player_id].xp == before_xp
    apt = interlock.state["apartments"]["fixture"]
    assert not apt["hack_log"] and apt["last_hacked_at"] is None
    assert interlock.commerce.items["fixture:stack"].stack == 3
    intent(game, b, "lat.theft", item="fixture:stack")
    game.step(3*TICK_HZ)
    saved_effect = game.commit_commerce()[0]
    saved = state(game)
    saved["interlock"] = saved_effect["interlock_state"]
    restored = HeadlessServer(game.core.loop.content, character_state=saved, clock=game.clock)
    other = restored.core.lattice.interlock
    assert len(other.state["apartments"]["fixture"]["hack_log"]) == 1
    assert other.commerce.items["fixture:stack"].stack == 2
    assert restored.core.characters.players[presence.player_id].xp == before_xp+40*record["tier"]
    assert other.lat.sectors.cells["lat-terraces"][record["cell"]].core_id == "lat-apartment-fixture"


def test_game_6_4_passkey_only_opens_30s_delivery_vestibule(runners):
    game, a, b, c = runners
    interlock, record = apartment_fixture(game, a)
    presence = private_entry(game, b, record)
    presence.room = "vestibule"
    presence.rig = ("prg_passkey", None, None)
    cast(game, b, "prg_passkey")
    assert not presence.opened and presence.key_tier == 0
    game.commit_commerce()
    obj = game.core.world.zones[record["zone"]].objects[record["door"]]
    assert obj.open and not interlock.private.manifest(presence)
    game.clock.advance(30*TICK_HZ)
    game.step()
    assert not obj.open
    assert interlock.commerce.items["fixture:stack"].stack == 3


def test_game_6_4_private_log_cap_and_exact_rolling_allowance(runners):
    game, a, b, c = runners
    interlock, record = apartment_fixture(game, a)
    presence = private_entry(game, b, record)
    apartment = interlock.state["apartments"]["fixture"]
    template = interlock.commerce.items["fixture:stack"].template
    apartment["hack_log"] = [{"at": f"2025-12-{day:02}T00:00:00+00:00", "item": template, "unit": 1}
                             for day in range(1,21)]
    intent(game, b, "lat.theft", item="fixture:stack")
    game.step(3*TICK_HZ)
    game.commit_commerce()
    apartment = interlock.state["apartments"]["fixture"]
    assert len(apartment["hack_log"]) == 20
    assert apartment["hack_log"][0]["at"].startswith("2025-12-02")
    deadline = round((apartment["last_hacked_at"]+86400-game.clock.epoch.timestamp())*TICK_HZ)
    game.clock.advance(deadline-game.clock.now_tick()-1)
    with pytest.raises(ValueError, match="24 hours"):
        interlock.private.start_theft(presence, "fixture:stack")
    game.clock.advance()
    interlock.private.start_theft(presence, "fixture:stack")
    assert presence.procedure.kind == "theft"
