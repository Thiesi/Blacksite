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
