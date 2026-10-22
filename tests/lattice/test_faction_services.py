"""Game 7.1/7.6: source-owned receipts for cuts and private reports."""
from copy import deepcopy
from datetime import timedelta
import pytest
from blacksite.server.clock import TICK_HZ
from blacksite.server.items import make_item
from tests.lattice.test_engine import runners, intent
from tests.lattice.test_interlock import cut_fixture
from tests.lattice.test_private_cores import apartment_fixture, private_entry


def test_game_7_6_containment_fee_and_item_commit_once_failed_receipt_spends_neither(runners):
    game, a, _, _ = runners
    p = game.core.characters.players[a.session.player_id]
    p.faction, p.standing["halvard"], p.chits_hand = "halvard", 90, 500
    zid, oid = cut_fixture(game, a)
    interlock = game.core.lattice.interlock
    iid = "test-origin:item:989000"
    game.core.commerce.items[iid] = make_item(iid, interlock.content.items["key_containment_charge"], p.id, game.clock.now_utc().isoformat())
    p.inventory.append(iid)
    interlock.start_cut(a.session, "lat-civic-ledger", zid, oid, charge=True)
    game.step(5*TICK_HZ)
    assert iid in p.inventory and not interlock.offline("lat-civic-ledger")
    game.commit_commerce(error=True)
    assert iid in p.inventory and p.chits_hand == 500
    interlock.start_cut(a.session, "lat-civic-ledger", zid, oid, charge=True)
    game.step(5*TICK_HZ)
    effects = game.commit_commerce()
    assert iid not in p.inventory and p.chits_hand == 500 and interlock.offline("lat-civic-ledger")
    assert effects[0]["identities"][p.bbs_user_id]["receipts"]["faction_perks"]["halvard-service"] == game.clock.now_utc().date().isoformat()
    identity = deepcopy(game.core.characters.identities[p.bbs_user_id])
    assert game.core.factions.containment_fee(p, identity) == 150
    p.standing["halvard"] = 89
    assert game.core.factions.containment_fee(p, {}) == 150


def test_game_7_1_cut_owner_standing_joins_effect_but_permitted_work_is_exempt(runners):
    game, a, _, _ = runners
    p = game.core.characters.players[a.session.player_id]
    zid, oid = cut_fixture(game, a)
    interlock = game.core.lattice.interlock
    interlock.state["cores"]["lat-civic-ledger"] = {"owner_faction": "halvard"}
    before = dict(p.standing)
    interlock.start_cut(a.session, "lat-civic-ledger", zid, oid)
    game.step(5*TICK_HZ)
    assert p.standing == before
    game.commit_commerce()
    assert p.standing["halvard"] == before.get("halvard", 0)-10
    assert p.standing.get("sablier", 0) == before.get("sablier", 0)
    interlock.permit = lambda pid, core, action: True
    assert game.core.factions.cut_patch(p, "lat-civic-ledger") == {}


def test_game_7_1_private_report_is_resident_only_redacted_and_atomic_once(runners):
    game, resident, thief, stranger = runners
    interlock, record = apartment_fixture(game, resident)
    presence = private_entry(game, thief, record)
    intent(game, thief, "lat.theft", item="fixture:stack")
    game.step(3*TICK_HZ); game.commit_commerce()
    private = interlock.private
    apt = interlock.state["apartments"]["fixture"]
    row = apt["hack_log"][0]
    receipt = row["receipt"]
    p = game.core.characters.players[thief.session.player_id]
    before = p.standing.get("wardens", 0)
    with pytest.raises(ValueError, match="resident"):
        private.report_theft(stranger.session, "fixture", receipt)
    private.open_log(resident.session, "fixture")
    assert p.id not in str(private.lat.sim.external_views[resident.session.id])
    private.report_theft(resident.session, "fixture", receipt)
    game.commit_commerce(error=True)
    assert not apt["hack_log"][0]["reported"] and p.standing.get("wardens", 0) == before
    private.report_theft(resident.session, "fixture", receipt)
    effects = game.commit_commerce()
    assert p.standing["wardens"] == before-10
    assert effects[0]["interlock_state"]["apartments"]["fixture"]["hack_log"][0]["reported"]
    with pytest.raises(ValueError, match="already"):
        private.report_theft(resident.session, "fixture", receipt)


def test_game_7_3_remote_cut_mark_is_in_the_same_receipt_and_refused_cut_never_marks(runners):
    from tests.lattice.test_encounters import enter
    from tests.character_helpers import place
    game, a, b, _ = runners
    for client in (a, b):
        game.core.characters.players[client.session.player_id].update_progression(1500)
    enter(game, b, "lat-civic-ledger")
    # The initiator is open; the affected runner is contested. Both must be
    # open for the remote exception. Grade protection is independent.
    zid, oid = cut_fixture(game, a)
    place(game, b, "vatside-clinics", (25, 3))
    interlock = game.core.lattice.interlock
    p = game.core.characters.players[a.session.player_id]
    interlock.start_cut(a.session, "lat-civic-ledger", zid, oid)
    game.step(5*TICK_HZ)
    assert not p.marked_until
    game.commit_commerce(error=True)
    assert not p.marked_until
    interlock.start_cut(a.session, "lat-civic-ledger", zid, oid)
    game.step(5*TICK_HZ)
    effect = game.commit_commerce()[0]
    assert p.marked_until and game.core.combat.actor(p).marked
    assert next(row for row in effect["players"] if row["id"] == p.id)["marked_until"] == p.marked_until


def test_game_7_6_unaffordable_charge_is_refused_before_channel_and_quote_never_spends(runners):
    game, a, _, _ = runners
    p = game.core.characters.players[a.session.player_id]
    p.chits_hand = 0
    zid, oid = cut_fixture(game, a)
    interlock = game.core.lattice.interlock
    iid = "test-origin:item:989000"
    game.core.commerce.items[iid] = make_item(iid, interlock.content.items["key_containment_charge"], p.id, game.clock.now_utc().isoformat())
    p.inventory.append(iid)
    with pytest.raises(ValueError, match="fee is 150"):
        interlock.start_cut(a.session, "lat-civic-ledger", zid, oid, charge=True)
    assert not interlock.cuts and iid in p.inventory and not game.core.commerce.pending
    p.faction, p.standing["halvard"] = "halvard", 90
    interlock.start_cut(a.session, "lat-civic-ledger", zid, oid, charge=True)
    assert p.id in interlock.cuts and iid in p.inventory
    assert "halvard-service" not in game.core.characters.identities[p.bbs_user_id].get("receipts", {}).get("faction_perks", {})


def test_ui_5_manual_cut_is_only_offered_adjacent_and_charge_quote_is_visible(runners):
    from tests.character_helpers import place
    game, a, _, _ = runners
    zid, oid = cut_fixture(game, a)
    interlock = game.core.lattice.interlock
    zone = game.core.world.zones[zid]
    ox, oy = zone.objects[oid].spec.tile
    tile = next((ox+dx, oy+dy) for dx, dy in ((2, 0), (-2, 0), (0, 2), (0, -2))
                if zone.passable((ox+dx, oy+dy)))
    place(game, a, zid, tile)
    interlock.menus[a.session.id] = zid, oid, False
    game.step()
    body = game.core.characters.sim.external_views[a.session.id][1]
    assert {row["key"] for row in body["actions"]} == {"x"}
    interlock.menus[a.session.id] = zid, oid, "charge"
    game.step()
    assert "service fee 150 chits" in game.core.characters.sim.external_views[a.session.id][1]["detail"]
    place(game, a, zid, zone.objects[oid].spec.tile)
    interlock.menus[a.session.id] = zid, oid, False
    game.step()
    assert {row["key"] for row in game.core.characters.sim.external_views[a.session.id][1]["actions"]} == {"c", "x"}


def test_ui_5_stale_hardware_confirmation_does_not_start_a_paid_cut(runners):
    from blacksite.server.protocol import Frame
    game, a, _, _ = runners
    zid, oid = cut_fixture(game, a)
    interlock = game.core.lattice.interlock
    interlock.menus[a.session.id] = zid, oid, "charge"
    frame = Frame("intent", {"name": "menu_select", "args": {"key": "y", "row": "cut"},
                            "expected_revision": a.session.view_revision+1})
    assert interlock.input(a.session, frame, game.clock.now_tick())
    assert not interlock.cuts and interlock.menus[a.session.id][2] == "charge"
