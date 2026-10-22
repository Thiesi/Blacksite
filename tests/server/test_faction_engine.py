"""Game 7.1/11: recruitment through the real Core and Commerce queue."""

from copy import deepcopy
from pathlib import Path

import pytest

from blacksite.content.loader import load_content
from blacksite.server.protocol import Frame
from tests.character_helpers import act, create, place, state
from tests.harness import HeadlessServer


@pytest.fixture(scope="module")
def content():
    return load_content(Path(__file__).parents[2]/"src/blacksite/content")


@pytest.fixture
def contacts(content):
    game = HeadlessServer(content, character_state={})
    clients = []
    for uid in (1, 2, 3):
        client = game.connect({"user_id": uid, "handle": f"Wide界{uid}", "node_name": "test"})
        create(game, client, name=f"Applicant界{uid}")
        p = game.core.characters.players[client.session.player_id]
        p.grade = 5
        p.standing.update(halvard=30, choir=90)
        game.step()
        clients.append(client)
    place(game, clients[0], "vatside-wake-hall", (8, 10))
    place(game, clients[1], "vatside-wake-hall", (9, 10))
    place(game, clients[2], "vatside-wake-hall", (8, 11))
    for client in clients:
        game.frames_for(client)
    return game, *clients


def player(game, client):
    return game.core.characters.players[client.session.player_id]


def change(game, client, action="join", fid="halvard"):
    game.core.factions.propose(client.session, "recruiter-cards", action, fid)
    return game.commit_commerce()


def test_game_7_1_membership_is_not_published_before_receipt_or_after_failed_save(contacts):
    game, caller, _, _ = contacts
    f, p = game.core.factions, player(game, caller)
    f.propose(caller.session, "recruiter-cards", "join", "halvard")
    assert p.faction is None and game.core.combat.actor(p).faction is None
    game.commit_commerce(error=True)
    assert p.faction is None
    effects = change(game, caller)
    assert p.faction == game.core.combat.actor(p).faction == "halvard"
    assert effects[0]["player"]["faction"] == "halvard"
    assert game.core.chat.faction(caller.session) == "halvard"


def test_game_7_1_queued_second_join_rechecks_current_membership(contacts):
    game, caller, _, _ = contacts
    f = game.core.factions
    f.propose(caller.session, "recruiter-cards", "join", "halvard")
    f.propose(caller.session, "recruiter-cards", "join", "choir")
    effects = game.commit_commerce()
    assert len(effects) == 1 and player(game, caller).faction == "halvard"


def test_game_7_1_contact_confirm_and_escape_do_not_grant_membership(contacts):
    game, caller, _, _ = contacts
    act(game, caller, Frame("key", {"k": "e", "t": 0}))
    f = game.core.factions
    screen = f.menus[caller.session.id]
    assert game.core.characters.players[caller.session.player_id].faction is None
    act(game, caller, Frame("intent", {"name": "menu_select", "args": {"key": "j", "row": "halvard"}}))
    assert screen.confirm == "join" and not game.core.commerce.pending
    act(game, caller, Frame("intent", {"name": "menu_close", "args": {}}))
    assert caller.session.id not in f.menus and player(game, caller).faction is None


def test_game_7_1_stale_recruitment_choice_cannot_change_membership(contacts):
    game, caller, _, _ = contacts
    act(game, caller, Frame("key", {"k": "e", "t": 0}))
    caller.send(Frame("intent", {"name": "menu_select", "args": {"key": "j", "row": "halvard"},
        "expected_revision": caller.session.view_revision+1, "request_id": "stale-join"}))
    game.step()
    assert not game.core.factions.menus[caller.session.id].confirm
    assert player(game, caller).faction is None


def test_game_7_1_queued_join_requires_the_contact_to_still_be_nearby(contacts):
    game, caller, other, _ = contacts
    f = game.core.factions
    f.propose(other.session, "recruiter-cards", "join", "halvard")
    f.propose(caller.session, "recruiter-cards", "join", "halvard")
    place(game, caller, "vatside-wake-hall", (4, 4))
    game.commit_commerce()
    assert player(game, caller).faction is None


def test_game_7_1_choir_ninth_has_no_population_cap(contacts):
    game, a, b, _ = contacts
    change(game, a, fid="choir")
    change(game, b, fid="choir")
    assert player(game, a).faction == player(game, b).faction == "choir"


def test_game_11_faction_chat_membership_changes_immediately_at_commit(contacts):
    game, a, b, outsider = contacts
    change(game, a)
    change(game, b)
    for client in (a, b, outsider):
        game.frames_for(client)
    game.core.chat.speak(a.session, "faction", "Containment holds.", game.clock.now_tick())
    def texts(client):
        return [row["text"] for frame in game.frames_for(client) if frame.type == "log" for row in frame.data["lines"]]
    assert any("Containment holds" in text for text in texts(b))
    assert not any("Containment holds" in text for text in texts(outsider))
    change(game, b, "leave")
    assert player(game, b).standing["halvard"] == -20 and player(game, b).faction is None
    game.frames_for(b)
    game.core.chat.speak(a.session, "faction", "The door closes.", game.clock.now_tick())
    assert not any("The door closes" in text for text in texts(b))


def test_game_7_1_startup_migrates_legacy_card_standing_once(contacts, content):
    game, caller, _, _ = contacts
    saved = state(game)
    row = next(row for row in saved["players"] if row["id"] == caller.session.player_id)
    row["standing"] = {"red-sable": 10, "sable": 4}
    restarted = HeadlessServer(content, character_state=deepcopy(saved))
    migrated = restarted.core.characters.players[row["id"]]
    assert migrated.standing == {"sable": 14} and migrated.faction is None
    effects = restarted.commit_characters()
    assert any(e.get("player", {}).get("standing") == {"sable": 14} for e in effects if e.get("player"))
    saved = state(restarted)
    again = HeadlessServer(content, character_state=saved)
    assert again.core.characters.players[row["id"]].standing == {"sable": 14}


def member(game, client, fid):
    p = player(game, client)
    p.faction = fid
    p.standing[fid] = 90
    game.core.factions.refresh(p)
    return p


def test_game_7_6_inspector_sees_only_active_marked_zone_even_if_sitrep_hidden(contacts):
    from datetime import timedelta
    from blacksite.server.chat import Sitrep
    game, caller, target, _ = contacts
    inspector, other = member(game, caller, "wardens"), player(game, target)
    other.marked_until = (game.clock.now_utc()+timedelta(minutes=15)).isoformat()
    game.core.chat.settings(target.session)["sitrep_hidden"] = True
    game.core.chat.sitreps[caller.session.id] = Sitrep(0, game.clock.now_tick())
    game.step()
    body = game.core.characters.sim.external_views[caller.session.id][1]
    row = next(row for row in body["rows"] if row["id"] == other.id)
    assert row["cells"][3] == "MARKED Wake Hall" and row["cells"][5] == ""
    assert game.core.factions.rank_of(caller.session) == "Inspector"
    inspector.standing["wardens"] = 89
    assert game.core.factions.inspector_location(caller.session, target.session) is None
    inspector.standing["wardens"] = 90
    other.marked_until = game.clock.now_utc().isoformat()
    assert game.core.factions.inspector_location(caller.session, target.session) is None


def test_game_7_6_bound_loan_failed_claim_retries_and_daily_identity_prevents_reclaim(contacts):
    game, caller, _, _ = contacts
    p = member(game, caller, "unmoored")
    f = game.core.factions
    f.service(caller.session, "recruiter-cards", "unmoored", "loan")
    assert "faction_loan" not in p.progress
    game.commit_commerce(error=True)
    f.service(caller.session, "recruiter-cards", "unmoored", "loan")
    game.commit_commerce()
    assert f.loan_programs(p) == {"prg_residual_fragment"}
    assert "prg_residual_fragment" not in p.progress.get("known_programs", [])
    f.clear_loan(p)
    assert not f.loan_programs(p) and not p.progress["lattice_charges"].get("prg_residual_fragment")
    with pytest.raises(ValueError, match="already claimed"):
        f.service(caller.session, "recruiter-cards", "unmoored", "loan")


def test_game_7_6_loan_stops_on_standing_loss_without_removing_learned_programs(contacts):
    game, caller, _, _ = contacts
    p = member(game, caller, "unmoored")
    f = game.core.factions
    p.progress.update(faction_loan=True, known_programs=["prg_needle"], lattice_charges={"prg_residual_fragment": 1})
    p.rig["slots"] = ["prg_residual_fragment", "prg_needle"]
    p.standing["unmoored"] = 89
    game.step()
    assert not f.loan_programs(p) and not p.progress.get("faction_loan")
    assert p.rig["slots"] == [None, "prg_needle"] and p.progress["known_programs"] == ["prg_needle"]


def test_game_7_6_sablier_choice_requires_visited_live_vat_and_ends_below_90(contacts):
    game, caller, _, _ = contacts
    p = member(game, caller, "sablier")
    f = game.core.factions
    assert "wardens" not in f.vats(p)
    with pytest.raises(ValueError, match="Visit"):
        f.service(caller.session, "recruiter-cards", "sablier", "vat:wardens")
    p.progress.setdefault("reward_receipts", {})["zone_discovery:core-precinct"] = "core-precinct"
    f.service(caller.session, "recruiter-cards", "sablier", "vat:wardens")
    game.commit_commerce()
    assert game.core.combat.vat(p)[0] == "core-precinct"
    p.standing["sablier"] = 89
    assert f.vat(p) is None
    p.progress["faction_respawn"] = "hall"
    assert f.vat(p)[0] == "vatside-wake-hall"


def test_game_7_6_unannounced_events_never_spend_or_invent_forecasts(contacts):
    game, caller, _, _ = contacts
    for fid in ("kestrel", "choir", "ferrymen"):
        p = member(game, caller, fid)
        before = deepcopy(p.progress)
        with pytest.raises(ValueError, match="No committed event"):
            game.core.factions.service(caller.session, "recruiter-cards", fid, "preview")
        assert not game.core.commerce.pending and p.progress == before


def test_game_7_6_sable_reservation_serializes_two_members_and_never_blocks_fixed_stock(contacts):
    game, caller, other, _ = contacts
    p, second = member(game, caller, "sable"), member(game, other, "sable")
    f, commerce = game.core.factions, game.core.commerce
    vendor = game.core.loop.content.vendors["vesper"]
    obj = next(o for o in game.core.world.zones[vendor.zone].objects.values() if o.spec.params.get("vendor") == vendor.id)
    for client in (caller, other):
        place(game, client, vendor.zone, game.core.world.free_tile(vendor.zone, obj.spec.tile))
    rotating = next(entry.item for entry in commerce.stock(vendor) if f.rotating(vendor, entry.item))
    commerce.propose(caller.session, "vendor.reserve", {"target": obj.spec.id, "item": rotating})
    commerce.propose(other.session, "vendor.reserve", {"target": obj.spec.id, "item": rotating})
    game.commit_commerce()
    counter = vendor.zone+":"+obj.spec.id
    assert f.reservation(counter, rotating).id == p.id
    assert not f.stock_available(second, vendor, counter, rotating)
    assert all(f.stock_available(second, vendor, counter, entry.item) for entry in vendor.stock)
    p.standing["sable"] = 89
    assert f.stock_available(second, vendor, counter, rotating)
    p.standing["sable"] = 90
    game.clock.advance(6000)
    assert f.stock_available(second, vendor, counter, rotating)
    with pytest.raises(ValueError, match="already used"):
        commerce.propose(caller.session, "vendor.reserve", {"target": obj.spec.id, "item": rotating})


def test_game_7_6_residual_bonus_caps_at_100_and_jackout_consumes_without_touching_permanent_skill(contacts):
    from blacksite.server.lattice.presence import Presence
    game, caller, _, _ = contacts
    p = member(game, caller, "unmoored")
    f = game.core.factions
    p.skills["programs"] = 90
    p.progress.update(faction_loan=True, lattice_charges={"prg_residual_fragment": 1})
    presence = Presence(p.id+":presence", p.id, "lat-vatside", "fixture", ("prg_residual_fragment",))
    f.lat.presences[p.id] = presence
    presence.effects.install(f.content.programs["prg_residual_fragment"], game.clock.now_tick())
    assert game.core.progression.modifiers(p).skill(p, "programs") == 100
    assert p.skills["programs"] == 90
    p.standing["unmoored"] = 89
    assert game.core.progression.modifiers(p).skill(p, "programs") == 90
    p.standing["unmoored"] = 90
    f.clear_loan(p)
    assert not presence.effects.active and not f.loan_programs(p)


def test_game_7_6_event_offer_pins_convoy_plan_and_kin_threshold_is_90(contacts):
    from blacksite.server.factions import EventOffer
    game, caller, _, _ = contacts
    f = game.core.factions
    p = member(game, caller, "kestrel")
    f.preview = lambda player, kind: EventOffer("convoy:committed-1", "Departure at 14:00 UTC.")
    f.service(caller.session, "recruiter-cards", "kestrel", "preview")
    game.commit_commerce()
    assert p.progress["convoy_reservation"] == "convoy:committed-1"
    p = member(game, caller, "ferrymen")
    p.standing["ferrymen"] = 70
    with pytest.raises(ValueError, match="90"):
        f.service(caller.session, "recruiter-cards", "ferrymen", "preview")


def test_game_5_5_new_heat_doubles_under_zone_curfew_only(contacts):
    from datetime import datetime
    game, caller, _, _ = contacts
    p = player(game, caller)
    f = game.core.factions
    f.curfew = lambda zone: zone == p.zone
    game.core.npcs.dispatch(game.core.combat.actor(p))
    assert (datetime.fromisoformat(p.warden_heat_until)-game.clock.now_utc()).total_seconds() == 1200


def test_game_8_1_rotating_weapon_brings_its_public_ammunition(contacts, monkeypatch):
    from dataclasses import replace
    game, caller, _, _ = contacts
    commerce = game.core.commerce
    tree = game.core.loop.content
    # Isolate one optional candidate with actual rifle/ammo catalog blocks.
    vendor = tree.vendors["vesper"]
    content = commerce.content
    monkeypatch.setattr(content, "items", {key: replace(item, tier=1) if item.tier == 2 else item
                     for key, item in content.items.items()})
    rifle = "wpn_halvard_hv7"
    content.items[rifle] = replace(content.items[rifle], tier=2)
    stock = commerce.stock(vendor)
    ids = [row.item for row in stock]
    assert rifle in ids and content.items[rifle].weapon.ammo in ids
    assert not game.core.factions.rotating(vendor, content.items[rifle].weapon.ammo)
