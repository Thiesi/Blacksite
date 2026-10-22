"""Game 5/6.7/7.3: real physical bodies retain their safety and hit path."""

import pytest
from dataclasses import replace

from tests.character_helpers import place
from tests.lattice.test_engine import actor, runners


def open_area_fixture(game):
    # Open Scour maps arrive in S25. Use an explicitly labelled open
    # variant of the existing map, not a claimed production geography.
    zone = game.core.world.zones["sodium-row"]
    zone.template = replace(zone.template, meta=replace(zone.template.meta, safety="open"))


@pytest.mark.parametrize("source_zone,target_zone,grade,allowed", [
    ("core-plaza", "sodium-row", 5, False),
    ("sodium-row", "core-plaza", 5, False),
    ("vatside-clinics", "sodium-row", 1, False),
    ("sodium-row", "vatside-clinics", 1, False),
    ("vatside-clinics", "sodium-row", 5, True),
    ("sodium-row", "vatside-clinics", 5, True),
    ("sodium-row", "sodium-row", 1, True),
])
def test_design_6_7_remote_permission_uses_both_body_locations(runners, source_zone, target_zone, grade, allowed):
    game, a, b, _ = runners
    open_area_fixture(game)
    place(game, a, source_zone, (25, 25))
    place(game, b, target_zone, (27, 25))
    source, target = actor(game, a), actor(game, b)
    source.stance = "jacked"
    game.core.characters.players[source.id].grade = grade
    game.core.characters.players[target.id].grade = grade
    assert game.core.combat.permits_indirect(source, target) is allowed
    assert not game.core.combat.legal(source, target)  # Helpless body cannot fire.


def test_design_7_3_open_attacker_does_not_evade_contested_marking(runners):
    game, a, b, _ = runners
    open_area_fixture(game)
    place(game, a, "sodium-row", (25, 25))
    place(game, b, "vatside-clinics", (27, 25))
    source, target = actor(game, a), actor(game, b)
    assert game.core.world.zones[source.zone].safety_at(source.position) == "open"
    assert game.core.world.zones[target.zone].safety_at(target.position) == "contested"
    game.core.combat.mark_indirect(source, target)
    assert source.marked
    assert game.core.characters.players[source.id].marked_until


def test_design_5_npc_feedback_requires_authority_and_uses_the_normal_down_record(runners):
    game, a, _, _ = runners
    body = actor(game, a)
    combat = game.core.combat
    original = body.health
    assert not combat.feedback_hurt(body, 10, "node:ice:kiln", "Kiln", lambda:False)
    assert body.health == original
    combat.commerce.pending = True
    assert not combat.feedback_hurt(body, 10, "node:ice:kiln", "Kiln", lambda:True)
    assert body.health == original
    combat.commerce.pending = False
    bodies = set(game.core.world.actors)
    assert combat.feedback_hurt(body, original, "node:ice:kiln", "Kiln", lambda:True)
    assert body.health == 0 and body.stance == "down"
    player = game.core.characters.players[body.id]
    assert player.progress["combat"]["killer"] == "node:ice:kiln"
    assert set(game.core.world.actors) == bodies
    assert any(e.get("immediate") for e in game.core.characters.outbox if e["action"] == "save")
