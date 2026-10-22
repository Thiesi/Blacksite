"""Game 8.4: real channel completion and atomic item/reward proposals."""

from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from blacksite.content.loader import load_content
from blacksite.content.schema import ObjectSpec, QualitySpec
from blacksite.server.clock import TICK_HZ
from blacksite.server.items import make_item
from blacksite.server.quality import detail, roll, validate_policy
from blacksite.server.protocol import Frame
from blacksite.server.storage.db import Storage
from blacksite.server.world.zone import ObjectState
from tests.character_helpers import create
from tests.harness import HeadlessServer


@pytest.fixture(scope="module")
def content():
    return load_content(Path(__file__).parents[1]/"src/blacksite/content")


@pytest.fixture
def game(content):
    return HeadlessServer(content, character_state={})


def caller(game, user=1):
    client = game.connect({"user_id": user, "handle": f"Wide界{user}", "node_name": "test"})
    create(game, client, name=f"Crafter{user}")
    return client, game.core.characters.players[client.session.player_id]


def shop(game, client, makes="any"):
    actor = game.core.characters.sim.avatars[client.session.user_id].actor
    zone = game.core.world.zones[actor.zone]
    zone.objects["fixture-shop"] = ObjectState(ObjectSpec("fixture-shop", actor.position, "workshop", params={"makes": makes}))
    return "fixture-shop"


def grant(game, player, template, count=1):
    commerce = game.core.commerce
    if count > commerce.content.items[template].stack_max:
        for _ in range(count):
            item = grant(game, player, template)
        return item
    commerce.serial = max(commerce.serial, 99999999999)+1
    item = make_item(f"test-origin:item:{commerce.serial}", commerce.content.items[template], player.id, "now", count)
    commerce.items[item.id] = item
    player.inventory.append(item.id)
    return item


def setup_recipe(game, client, player, recipe_id):
    recipe = game.core.loop.content.items[recipe_id]
    player.skills["fabrication"] = 100
    player.progress.setdefault("known_schematics", []).append(recipe_id)
    for grade, need in recipe.schematic.inputs.items():
        grant(game, player, "slv_"+grade, need)
    return shop(game, client)


@pytest.mark.parametrize("recipe_id", [
    "sch_scrap_bolts", "sch_scrap_plate", "sch_slugthrower", "sch_ring_wrench",
    "sch_flare_stick", "sch_cell", "sch_arcpen", "sch_coilgun", "sch_jury_rig",
    "sch_meteor_cannon", "sch_ringfall_rifle", "sch_railpistol", "sch_deepwater_rig",
    "sch_lifter", "sch_stinger", "sch_etcher", "sch_mirror_shell", "sch_hunterkiller",
])
def test_game_8_4_every_catalog_schematic_consumes_inputs_and_creates_output(game, recipe_id):
    client, player = caller(game)
    target = setup_recipe(game, client, player, recipe_id)
    fab = game.core.fabrication
    before_xp = player.xp
    fab.start(client.session, target, recipe_id)
    game.step(3*TICK_HZ-1)
    assert not game.core.commerce.outbox
    assert fab.amounts(player)
    game.step()
    effects = game.commit_commerce()
    assert effects and "salvage_state" in effects[-1]
    assert not fab.amounts(player)
    output_id = fab.content.items[recipe_id].schematic.output
    output = fab.content.items.get(output_id)
    if output:
        made = next(item for item in fab.commerce.items.values() if item.owner == player.id and item.template == output_id)
        assert made.stack == (output.stack_max if output.class_ == "ammo" else 1)
        assert 1 <= made.quality <= 1.15
        tier = output.tier
    else:
        assert output_id in player.progress["known_programs"]
        tier = fab.content.programs[output_id].tier
    assert player.xp-before_xp == 15*tier


def test_game_8_4_failed_save_keeps_inputs_rewards_and_rng(game):
    client, player = caller(game)
    target = setup_recipe(game, client, player, "sch_ring_wrench")
    player.skills["fabrication"] = 0
    fab = game.core.fabrication
    before = player.record(), deepcopy(fab.commerce.items), deepcopy(fab.salvage.state)
    fab.start(client.session, target, "sch_ring_wrench")
    game.step(3*TICK_HZ)
    game.commit_commerce(error=True)
    assert (player.record(), fab.commerce.items, fab.salvage.state) == before
    fab.start(client.session, target, "sch_ring_wrench")
    game.step(3*TICK_HZ)
    game.commit_commerce()
    assert player.skills["fabrication"] == 1
    assert player.xp > before[0]["xp"]


@pytest.mark.parametrize("interruption", ["move", "hit", "escape", "disconnect"])
def test_game_8_4_interrupted_craft_consumes_nothing(game, interruption):
    client, player = caller(game)
    target = setup_recipe(game, client, player, "sch_ring_wrench")
    fab = game.core.fabrication
    before = deepcopy(fab.commerce.items), player.xp
    fab.start(client.session, target, "sch_ring_wrench")
    game.step(2*TICK_HZ)
    actor = game.core.characters.sim.avatars[client.session.user_id].actor
    if interruption == "move":
        actor.x += 1
    elif interruption == "hit":
        actor.behaviour["hit_serial"] = actor.behaviour.get("hit_serial", 0)+1
    elif interruption == "escape":
        fab.input(client.session, Frame("key", {"k": "escape", "t": 0}), game.clock.now_tick())
    else:
        game.core.sessions.disconnect(client.session)
    game.step(2*TICK_HZ)
    game.commit_commerce()
    assert (fab.commerce.items, player.xp) == before


def test_game_8_4_skill_and_workshop_filters_are_authoritative(game):
    client, player = caller(game)
    target = setup_recipe(game, client, player, "sch_scrap_plate")
    fab = game.core.fabrication
    player.skills["fabrication"] = 0
    with pytest.raises(ValueError, match="Fabrication 10"):
        fab.start(client.session, target, "sch_scrap_plate")
    player.skills["fabrication"] = 100
    shop(game, client, "rigs_programs")
    with pytest.raises(ValueError, match="rigs and programs only"):
        fab.start(client.session, target, "sch_scrap_plate")


def test_game_8_4_learn_consumes_physical_schematic_and_duplicate_stays(game):
    client, player = caller(game)
    item = grant(game, player, "sch_ring_wrench")
    commerce = game.core.commerce
    commerce.propose(client.session, "inv.use", {"item": item.id})
    game.commit_commerce()
    assert item.id not in player.inventory and "sch_ring_wrench" in player.progress["known_schematics"]
    item = grant(game, player, "sch_ring_wrench")
    with pytest.raises(ValueError, match="already know"):
        commerce.propose(client.session, "inv.use", {"item": item.id})
    assert item.id in player.inventory


def test_game_8_4_chemical_workshop_fabricates_its_catalog_stinger(game):
    client, player = caller(game)
    target = setup_recipe(game, client, player, "sch_stinger")
    shop(game, client, "chemical_melee")
    fab = game.core.fabrication
    fab.start(client.session, target, "sch_stinger")
    game.step(3*TICK_HZ)
    game.commit_commerce()
    made = next(item for item in fab.commerce.items.values() if item.owner == player.id and item.template == "drn_sable_stinger")
    assert made.health == 35 and 1 <= made.quality <= 1.15
    assert not fab.amounts(player)


def test_game_8_4_quality_floor_cap_and_no_roll(content):
    from random import Random
    wrench = content.items["wpn_ferry_wrench"]
    for skill in (0, 30, 70, 100):
        rng = Random(7)
        draws = [roll(wrench, skill, rng) for _ in range(100)]
        assert min(draws) >= .85+.15*skill/100
        assert max(draws) <= min(1.15, 1+.15*skill/100)
        assert roll(wrench, skill, rng, .5) == 1.15
    rng = Random(4)
    state = rng.getstate()
    assert roll(content.items["ammo_scrap"], 100, rng) == 1
    assert roll(content.items["imp_rig_ow_jury"], 100, rng) == 1
    assert rng.getstate() == state


def test_game_8_4_repeated_crafts_keep_reward_watermark_and_daily_skill_cap(game):
    from blacksite.server.rules.character import attributes
    client, player = caller(game)
    target = setup_recipe(game, client, player, "sch_ring_wrench")
    for _ in range(4):
        grant(game, player, "slv_hull")
    player.skills["fabrication"] = 9
    fab = game.core.fabrication
    before_xp = player.xp
    for _ in range(3):
        fab.start(client.session, target, "sch_ring_wrench")
        game.step(3*TICK_HZ)
        game.commit_commerce()
    assert player.xp == before_xp+45
    assert player.skills["fabrication"] == 11
    assert player.attributes == attributes(player.archetype, player.skills, player.grade)
    crafts = [key for key in player.progress["reward_receipts"] if key.startswith("craft:")]
    assert crafts == ["craft:sch_ring_wrench"]


def test_game_8_4_quality_selects_one_armour_resistance_and_real_implant_effect(game):
    from blacksite.server.quality import effects
    client, player = caller(game)
    armour = grant(game, player, "arm_ostrom_mirror")
    armour.quality = 1.15
    player.equipment = {"body": armour.id}
    actor = game.core.characters.sim.avatars[client.session.user_id].actor
    combat = game.core.combat
    assert combat.armour(actor, "energy") == int(26*1.15)
    assert combat.armour(actor, "kinetic") == 10
    assert "K10 E29 C8 D0" in detail(game.core.loop.content.items[armour.template], armour.quality)
    implant = grant(game, player, "imp_halvard_dermal_plate")
    implant.quality = 1.15
    player.implants = {"torso": implant.id}
    mods = game.core.progression.modifiers(player)
    assert mods.bonus("arm_k") == pytest.approx(8*1.15)
    assert mods.bonus("arm_e") == 4 and mods.bonus("evasion") == -3
    template = game.core.loop.content.items["imp_halvard_reflex_arm"]
    assert effects(template, 1.15, "implant_effect", template.implant.effects)["weapon_cooldown_multiplier"] == pytest.approx(.885)
    assert validate_policy(replace(template, quality=QualitySpec("implant_effect", "secured_slots")))


def test_game_8_4_crafted_quality_reward_and_recipe_survive_sqlite_restart(game, tmp_path):
    client, player = caller(game)
    target = setup_recipe(game, client, player, "sch_ring_wrench")
    fab = game.core.fabrication
    fab.start(client.session, target, "sch_ring_wrench")
    game.step(3*TICK_HZ)
    effect = game.commit_commerce()[-1]
    storage = Storage(tmp_path/"world.db", game.clock)
    try:
        storage.commerce_write(effect)
        saved = storage.character_state()
    finally:
        storage.close()
    from tests.character_helpers import state
    # Identity, discovery and starter saves are separate fixture setup here.
    live = state(game)
    live.update(items=saved["items"], players=saved["players"], salvage=saved["salvage"])
    reloaded = HeadlessServer(game.core.loop.content, character_state=live)
    restored = reloaded.core.characters.players[player.id]
    assert restored.xp == player.xp
    assert restored.progress["known_schematics"] == player.progress["known_schematics"]
    output = next(item for item in fab.commerce.items.values() if item.owner == player.id and item.template == "wpn_ferry_wrench")
    assert reloaded.core.commerce.items[output.id].quality == output.quality
