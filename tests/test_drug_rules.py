"""Game 8.6: clocks, permanent withdrawal, real costs and offline detox."""

from copy import deepcopy
from pathlib import Path

import pytest

from blacksite.content.loader import load_content
from blacksite.server.drugs import advance, dose, end_ringdust_crash, start_detox
from blacksite.server.modifiers import collect, compose
from blacksite.server.players import Player


@pytest.fixture(scope="module")
def catalog():
    return load_content(Path(__file__).resolve().parents[1]/"src/blacksite/content").items


def runner():
    return Player("runner", "node", "bbs", "Wide\u754c", "Runner", "ghost", "2026-01-01T00:00:00+00:00")


def test_game_8_6_effect_crash_then_expiry_and_dependency_survives_redose(catalog):
    player = runner()
    drug = catalog["drug_sable_redline"]
    result = dose(player, drug, compose(()), 0)
    assert (result.effect_until, result.crash_until) == (90, 135)
    assert collect(player, {}, catalog, 89).multiplier("weapon_cooldown_multiplier") == .8
    assert advance(player, catalog, 90).crashes_started == (drug.id,)
    assert not advance(player, catalog, 91).crashes_started
    assert collect(player, {}, catalog, 90).multiplier("weapon_cooldown_multiplier") == 1.2
    advance(player, catalog, 135)
    assert collect(player, {}, catalog, 135).multiplier("weapon_cooldown_multiplier") == 1
    dose(player, drug, compose(()), 150)
    assert dose(player, drug, compose(()), 300).dependency_started
    assert len(player.drugs_active) == 1 and len(player.dependencies) == 1
    assert collect(player, {}, catalog, 301).multiplier("weapon_cooldown_multiplier") == pytest.approx(.96)
    advance(player, catalog, 100000)
    assert collect(player, {}, catalog, 100000).multiplier("weapon_cooldown_multiplier") == 1.2


def test_game_8_6_detox_gland_halves_window_and_crash_not_positive_duration(catalog):
    player, drug = runner(), catalog["drug_sable_redline"]
    gland = compose(({"addiction_window_multiplier": .5, "crash_duration_multiplier": .5},))
    first = dose(player, drug, gland, 0)
    assert (first.effect_until, first.crash_until) == (90, 112.5)
    dose(player, drug, gland, 601)
    assert not dose(player, drug, gland, 602).dependency_started
    assert dose(player, drug, gland, 603).dependency_started


def test_game_8_6_lullaby_heal_ringdust_damage_do_not_repeat_with_polls(catalog):
    player = runner()
    dose(player, catalog["drug_sable_lullaby"], compose(()), 0)
    dose(player, catalog["drug_ferry_ringdust"], compose(()), 0)
    assert advance(player, catalog, 5).health_delta == 15-5
    assert advance(player, catalog, 5).health_delta == 0
    assert advance(player, catalog, 10).health_delta == 15-5
    assert advance(player, catalog, 60).health_delta == -50
    assert end_ringdust_crash(player, 60)
    assert not end_ringdust_crash(player, 61)


def test_game_8_6_detox_offline_safe_exact_cost_and_draft_rollback(catalog):
    player, drug = runner(), catalog["drug_sable_redline"]
    for stamp in (0, 10, 20):
        dose(player, drug, compose(()), stamp)
    player.chits_hand = 500
    draft = deepcopy(player)
    assert start_detox(draft, 30, "vatside-clinics", (4, 5)) == 630
    assert player.chits_hand == 500 and "detox" not in player.progress
    assert draft.chits_hand == 100
    with pytest.raises(ValueError, match="progress"):
        dose(draft, drug, compose(()), 629)
    assert not advance(draft, catalog, 629).detox_completed
    restored = Player.from_record(draft.record())
    assert advance(restored, catalog, 100000).detox_completed
    assert not restored.dependencies and not restored.drugs_active and restored.progress["dose_log"] == {}
    assert restored.chits_hand == 100
