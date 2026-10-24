"""Game 7.1/7.2/7.6: deterministic reputation and identity-scoped perks."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from blacksite.content.loader import load_content
from blacksite.content.schema import Rank
from blacksite.server import factions as rules
from blacksite.server.players import Player


@pytest.fixture(scope="module")
def factions():
    return load_content(Path(__file__).parents[1]/"src/blacksite/content").factions


@pytest.fixture
def player():
    return Player("origin:player:1", "origin", "1", "Wide界", "Resident", "ghost", "2026-01-01T00:00:00+00:00")


def test_game_7_1_propagates_halves_toward_zero_and_explicit_vectors_once(factions, player):
    changes = rules.apply_delta(player, factions, "halvard", 5)
    assert changes["halvard"] == 5 and changes["sablier"] == 2
    assert changes["choir"] == -2 and "wardens" not in changes
    changes = rules.apply_delta(player, factions, "halvard", -3)
    assert changes["sablier"] == -1 and changes["choir"] == 1
    before = dict(player.standing)
    rules.apply_vector(player, factions, {"halvard": 7, "choir": 9}, "explicit")
    assert player.standing == {**before, "halvard": before["halvard"]+7, "choir": before["choir"]+9}


def test_game_7_1_clamps_only_after_combining_a_complete_vector(factions, player):
    player.standing = {"sablier": 99, "choir": -99}
    rules.apply_vector(player, factions, {"halvard": 10, "kestrel": -10})
    assert player.standing["sablier"] == 100 and player.standing["choir"] == -100
    rules.apply_delta(player, factions, "halvard", -1000, "explicit")
    assert player.standing["halvard"] == -100


@pytest.mark.parametrize("calendar", [False, True])
def test_game_3_4_7_1_join_requires_30_and_grade_or_calendar_discharge(factions, player, calendar):
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    player.standing["choir"] = 30
    with pytest.raises(ValueError, match="discharge"):
        rules.join(player, factions, "choir", now)
    identity = {"first_decanted_at": now.isoformat(), "legal_at": None}
    if calendar:
        now += timedelta(days=90)
    else:
        player.grade = 5
    player.update_personhood(identity, now)
    player.standing["choir"] = 29
    with pytest.raises(ValueError, match="30"):
        rules.join(player, factions, "choir", now)
    player.standing["choir"] = 30
    rules.join(player, factions, "choir", now)
    assert player.faction == "choir"
    with pytest.raises(ValueError, match="Leave"):
        rules.join(player, factions, "wardens", now)


def test_game_7_1_leave_costs_50_and_cooldown_does_not_reset_on_relogin(factions, player):
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    player.legal_at, player.faction = now.isoformat(), "halvard"
    player.standing = {"halvard": 90, "choir": 90}
    assert rules.perk(player, "halvard")
    changes = rules.leave(player, factions, now)
    assert changes == {"halvard": -50} and player.standing["choir"] == 90
    assert player.faction is None and not rules.perk(player, "halvard")
    player = Player.from_record(player.record())
    with pytest.raises(ValueError, match="Seven days"):
        rules.join(player, factions, "choir", now+timedelta(days=7)-timedelta(microseconds=1))
    rules.join(player, factions, "choir", now+timedelta(days=7))
    assert player.faction == "choir"


def test_game_7_2_freelance_is_neutral_and_faction_matrix_is_authority(factions):
    assert rules.relation(factions, None, None) == "N"
    assert rules.relation(factions, None, "halvard") == "N"
    assert rules.relation(factions, "choir", "choir") == "A"
    assert rules.relation(factions, "halvard", "sablier") == "A"
    assert rules.relation(factions, "halvard", "choir") == "H"
    assert rules.relation(factions, "ferrymen", "unmoored") == "N"


def test_game_7_6_rank_titles_do_not_grant_perks_below_90_or_after_leaving(factions, player):
    data = {**factions, "ferrymen": replace(factions["ferrymen"], ranks=(
        Rank(30, "Walker"), Rank(50, "Roadwise"), Rank(70, "Charter"), Rank(90, "Kin")))}
    player.faction = "ferrymen"
    for value, title in ((29, ""), (30, "Walker"), (50, "Roadwise"), (70, "Charter"), (90, "Kin")):
        player.standing["ferrymen"] = value
        assert rules.rank(player, data) == title
        assert rules.perk(player, "ferrymen") == (value >= 90)
    player.faction = None
    assert not rules.perk(player, "ferrymen")


def test_game_7_6_daily_perk_receipt_survives_character_switch_and_utc_boundary():
    now = datetime(2026, 1, 1, 23, 59, tzinfo=timezone.utc)
    identity = {"receipts": {}}
    assert rules.claim_daily(identity, "deep_loan", now)
    assert not rules.claim_daily(identity, "deep_loan", now+timedelta(seconds=59))
    assert rules.claim_daily(identity, "charge_service", now)
    assert rules.claim_daily(identity, "deep_loan", now+timedelta(minutes=1))


def test_game_7_1_npc_outcomes_are_explicit_without_secondary_reputation(factions, player):
    changes = rules.npc_kill(factions, "halvard")
    applied = rules.apply_vector(player, factions, changes, "explicit")
    assert applied["halvard"] == -5 and applied["choir"] == 2
    assert "sablier" not in applied


def test_game_7_1_marked_kill_has_identity_scoped_rolling_day_cap(factions, player):
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    victim = Player("origin:player:2", "origin", "2", "Other界", "Other", "ghost", now.isoformat(),
                    faction="halvard", marked_until=(now+timedelta(days=2)).isoformat())
    identity = {"receipts": {}}
    assert rules.player_kill(player, victim, factions, identity, now) == {"halvard": -10, "wardens": 5}
    victim.id = "origin:player:3"  # Another character on the same victim identity cannot reset it.
    assert rules.player_kill(player, victim, factions, identity, now+timedelta(hours=23)) == {"halvard": -10}
    assert rules.player_kill(player, victim, factions, identity, now+timedelta(days=1)) == {"halvard": -10, "wardens": 5}


def test_game_7_1_card_alias_migrates_once_and_never_grants_membership(player):
    content = load_content(Path(__file__).parents[1]/"src/blacksite/content")
    player.standing = {"red-sable": 10, "sable": 4}
    assert rules.normalize_card_standing(player, content.wake_cards)
    assert player.standing == {"sable": 14} and player.faction is None
    assert not rules.normalize_card_standing(player, content.wake_cards)
    assert player.standing == {"sable": 14}


def test_game_7_1_actual_sable_wake_card_grants_ten_to_real_faction():
    from tests.harness import HeadlessServer
    from tests.character_helpers import create
    content = load_content(Path(__file__).parents[1]/"src/blacksite/content")
    game = HeadlessServer(content, character_state={})
    client = game.connect()
    create(game, client, card="red-sable")
    resident = game.core.characters.players[client.session.player_id]
    assert resident.standing == {"sable": 10} and resident.faction is None


def test_entities_1_9_all_eight_sites_resolve_to_commissioned_halls():
    from blacksite.content.validate import validate
    content = load_content(Path(__file__).parents[1]/"src/blacksite/content")
    assert not validate(content)
    assert len(content.factions) == len(content.faction_sites) == 8
    assert all(content.active("factions", fid) for fid in content.factions)
    assert {s.faction for sid, s in content.faction_sites.items() if content.active("faction_sites", sid)} == set(content.factions)
    site = content.faction_sites["site-unmoored"]
    assert site.hall == "oldworks-drop" and site.recruiter_zone == "oldworks-main"
    assert content.active("faction_sites", site.id) and site.hall in content.zones
    assert all(tuple(r.standing for r in f.ranks) == (30,50,70,90) for f in content.factions.values())
