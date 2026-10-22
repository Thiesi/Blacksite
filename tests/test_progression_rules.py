"""Game 3.3-3.5: receipt authority, repetition limits and permanent grades."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from blacksite.server.players import Player
from blacksite.server.progression import Grant, award, combat_xp
from blacksite.server.rules import character
from blacksite.server.skills import Use, gain, spend


NOW = datetime(2026, 1, 1, 23, 59, tzinfo=timezone.utc)


def resident(pid="one", uid="bbs-one"):
    player = Player(pid, "node", uid, "Wide\u754c", "Runner", "hardline", NOW.isoformat())
    player.health = character.health_max(player.attributes["vitals"])
    return player, {"first_decanted_at": NOW.isoformat(), "legal_at": None}


def test_game_3_4_grade1_zero_grade5_1500_and_retained_benefits():
    player, identity = resident()
    assert player.xp == 0 and player.grade == 1 and not player.progress.get("points")
    player.update_progression(1490)
    player.health = character.health_max(player.attributes["vitals"])//2
    before_vitals, before_points = player.attributes["vitals"], player.progress["points"]
    result = award(player, identity, Grant("combat", "spawn:one", True, opponent_grade=1), NOW)
    assert result.xp == 14 and player.grade == 5
    assert player.attributes["vitals"] == before_vitals+1
    assert player.progress["points"] == before_points+3 and player.health == 69
    assert result.discharged and player.legal_at == NOW.isoformat()
    legal = player.legal_at
    player.update_progression(0)
    player.update_personhood(identity, NOW+timedelta(days=1))
    assert player.grade == 5 and player.legal_at == legal


def test_game_3_5_combat_scale_minimum_and_duplicate_spawn_receipt():
    assert combat_xp(5, 5) == 20 and combat_xp(5, 10) == 30
    assert combat_xp(30, 1) == 5
    player, identity = resident()
    grant = Grant("combat", "npc:1", True, scope="spawn-slot:one", opponent_grade=5)
    assert award(player, identity, grant, NOW).xp == 28
    assert award(player, identity, grant, NOW) is None
    assert player.xp == 28
    assert award(player, identity, Grant("combat", "npc:2", True,
        scope="spawn-slot:one", opponent_grade=5), NOW).xp == 28


def test_game_3_5_core_daily_identity_receipt_survives_character_change():
    player, identity = resident()
    grant = Grant("run", "unit:one", True, tier=3, core="core:one")
    assert award(player, identity, grant, NOW).xp == 120
    other, _ = resident("two")
    assert award(other, identity, Grant("run", "unit:two", True, tier=3, core="core:one"), NOW) is None
    assert award(other, identity, Grant("run", "unit:two", True, tier=3, core="core:one"), NOW+timedelta(minutes=2)).xp == 120


def test_game_3_5_opposing_identity_limit_is_rolling_24h():
    player, identity = resident()
    first = Grant("combat", "pvp:1", True, opponent_grade=5, opponent_identity="other")
    assert award(player, identity, first, NOW)
    second = Grant("combat", "pvp:2", True, opponent_grade=5, opponent_identity="other")
    assert award(player, identity, second, NOW+timedelta(hours=23, minutes=59)) is None
    assert award(player, identity, second, NOW+timedelta(hours=24))
    before = player.xp
    assert award(player, identity, Grant("combat", "self", True,
        opponent_grade=5, opponent_identity=player.bbs_user_id), NOW) is None
    assert player.xp == before


def test_game_3_5_hold_daily_cap_is_shared_across_relays():
    player, identity = resident()
    for index in range(6):
        assert award(player, identity, Grant("relay_hold", str(index), True, scope=f"relay:{index%2}"), NOW).xp == 10
    assert player.xp == 60
    assert award(player, identity, Grant("relay_hold", "seventh", True), NOW) is None
    assert award(player, identity, Grant("relay_hold", "next-day", True), NOW+timedelta(minutes=2)).xp == 10


def test_game_3_5_discovery_is_once_per_character_and_not_per_generated_seed():
    player, identity = resident()
    assert award(player, identity, Grant("zone_discovery", "zone:one", True, authored=True), NOW).xp == 25
    assert award(player, identity, Grant("zone_discovery", "revisit", True, scope="zone:one", authored=True), NOW) is None
    assert award(player, identity, Grant("cell_discovery", "cell:one", True, authored=True), NOW).xp == 5
    assert award(player, identity, Grant("cell_discovery", "generated:seed2", True), NOW) is None
    assert award(player, identity, Grant("craft", "craft:one", True, tier=2), NOW) is None
    assert award(player, identity, Grant("craft", "craft:one", True, tier=2, consumed_inputs=True), NOW).xp == 30


def test_game_3_5_use_caps_do_not_cap_grade_point_spending():
    player, identity = resident()
    for index in range(20):
        gain(player, Use("weapon_hit", "kinetic", str(index), eligible=True, threat=True), NOW)
    assert player.skills["kinetic"] == 2
    player.progress["points"] = 5
    assert spend(player, "kinetic", 5) == 5 and player.skills["kinetic"] == 7
    assert gain(player, Use("weapon_hit", "kinetic", "more", eligible=True, threat=True), NOW) == 0
    assert gain(player, Use("weapon_hit", "kinetic", "tomorrow", eligible=True, threat=True), NOW+timedelta(minutes=2)) == .2


def test_game_3_3_group_spending_raises_attribute_but_never_vitals():
    player, identity = resident()
    original = dict(player.attributes)
    player.progress["points"] = 10
    for line, points in (("kinetic", 3), ("melee", 4), ("armour", 3)):
        spend(player, line, points)
    assert player.attributes["frame"] == original["frame"]+1
    assert player.attributes["vitals"] == original["vitals"] and player.progress["points"] == 0


def test_game_3_5_training_crew_empty_actions_and_replayed_use_give_nothing():
    player, identity = resident()
    for use in (Use("weapon_hit", "kinetic", "training", True, threat=True, training=True),
                Use("weapon_hit", "kinetic", "crew", True, threat=True, self_or_crew=True),
                Use("program_change", "programs", "empty", True),
                Use("authored_cell", "lattice", "generated", True, changed=True)):
        assert gain(player, use, NOW) == 0
    use = Use("program_change", "programs", "changed", True, changed=True)
    assert gain(player, use, NOW) == .15
    assert gain(player, use, NOW) == 0 and player.skills["programs"] == .15
    assert award(player, identity, Grant("run", "lesson", True, tier=0, core="training", training=True), NOW) is None


def test_game_3_5_stealth_encounter_cap_survives_midnight():
    player, identity = resident()
    use = Use("stealth_second", "stealth", "one", True, threat=True, seconds=40, encounter="same")
    assert gain(player, use, NOW) == 1
    assert gain(player, Use("stealth_second", "stealth", "two", True, threat=True,
        seconds=40, encounter="same"), NOW+timedelta(minutes=2)) == 0
    assert gain(player, Use("stealth_second", "stealth", "three", True, threat=True,
        seconds=40, encounter="new"), NOW+timedelta(minutes=2)) == 1


def test_game_3_5_proposal_failure_can_discard_reward_and_receipt_together():
    player, identity = resident()
    draft, proposed_identity = deepcopy(player), deepcopy(identity)
    grant = Grant("run", "unit", True, tier=2, core="core")
    assert award(draft, proposed_identity, grant, NOW)
    # A rejected storage proposal never mutates either live authority.
    assert player.xp == 0 and "run_xp_days" not in identity
    assert award(deepcopy(player), deepcopy(identity), grant, NOW)
