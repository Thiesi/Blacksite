"""Catalog surgery and composable hardware, independent of I/O/UI."""

from pathlib import Path

import pytest

from blacksite.content.loader import load_content
from blacksite.server.implants import enforce_tolerance, install as operate, quote, removal_price, remove
from blacksite.server.items import ItemInstance
from blacksite.server.modifiers import collect, compose
from blacksite.server.players import Player


@pytest.fixture(scope="module")
def catalog():
    return load_content(Path(__file__).resolve().parents[1]/"src/blacksite/content").items


def runner(archetype="hardline"):
    return Player("runner", "node", "bbs", "Wide\u754c", "Runner", archetype, "2026-01-01T00:00:00+00:00")


def install(player, items, catalog, tid, slot=None):
    item = ItemInstance(tid, tid, player.id)
    items[item.id] = item
    player.inventory.append(item.id)
    player.implants[slot or catalog[tid].implant.slot] = item.id


def test_game_8_5_quotes_bought_owned_and_replacement(catalog):
    player, items = runner(), {}
    template = catalog["imp_halvard_reflex_arm"]
    mods = collect(player, items, catalog, 0)
    bought = quote(player, template, "sablier", mods, items, catalog, owned=False)
    owned = quote(player, template, "sablier", mods, items, catalog, owned=True)
    black = quote(player, template, "black", mods, items, catalog, owned=False)
    black_owned = quote(player, template, "black", mods, items, catalog, owned=True)
    assert bought.total == template.base_price*1.2 and bought.failure == .02
    assert owned.total == template.base_price*.2
    assert black.total == template.base_price*.6 and black.failure == .15
    assert black_owned.total == template.base_price*.12
    install(player, items, catalog, template.id, "arms1")
    install(player, items, catalog, "imp_halvard_stabiliser", "arms2")
    with pytest.raises(ValueError, match="occupied"):
        quote(player, template, "black", mods, items, catalog, owned=True)
    replacement = quote(player, template, "black", mods, items, catalog, owned=True, slot="arms1", replace=True)
    assert replacement.removal_price == removal_price(template)
    assert replacement.used == 4 and replacement.capacity == 6


def test_game_8_5_resonance_gate_only_on_installation(catalog):
    player, items = runner("cantor"), {}
    template = catalog["imp_res_first_ear"]
    with pytest.raises(ValueError, match="Choir"):
        quote(player, template, "sablier", collect(player, items, catalog, 0), items, catalog, owned=True)
    player.standing["choir"] = 20
    assert quote(player, template, "sablier", collect(player, items, catalog, 0), items, catalog, owned=True).used == 1
    install(player, items, catalog, template.id)
    player.standing["choir"] = -100
    assert collect(player, items, catalog, 0).bonus("hymn_tier") == 1


def test_game_8_5_native_rig_and_uninstalled_bag_do_not_stack(catalog):
    player, items = runner("ghost"), {}
    base = collect(player, items, catalog, 0)
    assert base.bonus("rig_slots") == 3 and base.flag("jack_anywhere")
    tid = "imp_rig_ow_deepwater"
    # An uninstalled purchase does not provide slots or movement effects.
    items[tid] = ItemInstance(tid, tid, player.id)
    player.inventory.append(tid)
    assert collect(player, items, catalog, 0).bonus("rig_slots") == 3
    player.implants["rig"] = tid
    mods = collect(player, items, catalog, 0)
    assert mods.bonus("rig_slots") == 6 and mods.multiplier("cell_move_multiplier") == .8


def test_game_8_5_tolerance_and_secured_slots_stay_separate_from_permanent_stats(catalog):
    player, items = runner(), {}
    install(player, items, catalog, "imp_sablier_secure_vault")
    before = dict(player.attributes)
    mods = collect(player, items, catalog, 0, ({"tolerance": 1},))
    assert mods.tolerance(player) == 7 and mods.secured_slots == 5
    assert player.attributes == before
    player.archetype = "ghost"
    assert collect(player, items, catalog, 0).tolerance(player) == 4


def test_game_8_6_same_substance_refresh_and_dependency_do_not_duplicate_crash(catalog):
    player = runner()
    tid = "drug_sable_redline"
    player.drugs_active = [{"template": tid, "effect_until": 90, "crash_until": 135}]
    player.dependencies = [{"template": tid, "since": 0}]
    assert collect(player, {}, catalog, 30).multiplier("weapon_cooldown_multiplier") == pytest.approx(.8*1.2)
    assert collect(player, {}, catalog, 100).multiplier("weapon_cooldown_multiplier") == 1.2
    assert collect(player, {}, catalog, 10000).multiplier("weapon_cooldown_multiplier") == 1.2


def test_game_8_5_multipliers_compose_unlocks_take_highest_resource_reads_are_pure():
    mods = compose(({"weapon_cooldown_multiplier": .9, "hymn_tier": 1, "health_over_time": 30},
                    {"weapon_cooldown_multiplier": .8, "hymn_tier": 2}))
    assert mods.multiplier("weapon_cooldown_multiplier") == pytest.approx(.72)
    assert mods.bonus("hymn_tier") == 2 and mods.bonus("health_over_time") == 0
    with pytest.raises(TypeError):
        mods.values["health"] = 10


def test_game_8_5_seeded_failure_consumes_owned_item_charges_and_keeps_old_quality(catalog):
    from random import Random
    player, items = runner(), {}
    old_tid, tid = "imp_sablier_secure_pocket", "imp_sablier_sub_dermal"
    install(player, items, catalog, old_tid)
    items[old_tid].quality = 1.12
    item = ItemInstance("purchase", tid, player.id, quality=1.08)
    items[item.id] = item
    player.inventory.append(item.id)
    player.chits_hand = 10000
    # Seed 31 begins below 2%; this is an actual reproducible seeded roll.
    result = operate(player, item, "sablier", collect(player, items, catalog, 0),
                     items, catalog, 0, Random(31).random(), owned=True, replace=True)
    assert not result.installed and result.returned == old_tid
    assert item.id not in items and item.id not in player.inventory
    assert items[old_tid].quality == 1.12 and old_tid in player.inventory
    assert "torso" not in player.implants and player.chits_hand == 10000-result.cost
    assert player.shock == 100 and player.progress["surgery_shock_until"] == 30


def test_game_8_5_native_replacement_never_creates_tradable_builtin(catalog):
    player, items = runner("ghost"), {}
    install(player, items, catalog, "imp_rig_native")
    player.chits_hand = 100000
    item = ItemInstance("new-rig", "imp_rig_ow_jury", player.id, quality=.91)
    result = operate(player, item, "sablier", collect(player, items, catalog, 0),
                     items, catalog, 0, .5, owned=False)
    assert result.installed and result.returned is None
    assert "imp_rig_native" not in items and "imp_rig_native" not in player.inventory
    assert remove(player, "rig", items, catalog) == item.id and items[item.id].quality == .91
    assert collect(player, items, catalog, 0).bonus("rig_slots") == 3
    assert collect(player, items, catalog, 0).flag("jack_anywhere")


def test_game_8_5_chrome_expiry_ejects_newest_keeps_item_unless_vitals_grew(catalog):
    from copy import deepcopy
    player, items = runner("ghost"), {}
    # 2+2+1 uses Chrome's fifth point; without it the newest item unseats.
    install(player, items, catalog, "imp_sablier_shock_sink")
    install(player, items, catalog, "imp_halvard_reflex_arm", "arms1")
    install(player, items, catalog, "imp_sablier_adrenal")
    player.progress["implant_order"] = list(player.implants.values())
    grown = deepcopy(player)
    grown.attributes["vitals"] = 50
    assert not enforce_tolerance(grown, items, catalog, collect(grown, items, catalog, 1200), 1200)
    assert enforce_tolerance(player, items, catalog, collect(player, items, catalog, 1200), 1200) == ("imp_sablier_adrenal",)
    assert "imp_sablier_adrenal" in player.inventory and "imp_sablier_adrenal" in items
    assert player.shock == 100 and player.progress["surgery_shock_until"] == 1230
