"""The three main-coordinate regressions, exercised on round 4's own city.

Canonical NPC tests retain main's coordinates when the explicit demo data
layer is installed. These are their counterparts for the demo geometry.
"""

import pytest

from dataclasses import replace

from karst41.content.loader import load_content
from karst41.server.npcs.templates import make_actor
from tests.character_helpers import place
from tests.demo.test_truce_standin import boot


def test_demo_halo_bouncer_fills_its_post_beside_an_arriving_caller(repo_root, monkeypatch):
    game, caller = boot(repo_root, monkeypatch)
    zone = game.core.world.zones['sodium-tin-halo']
    demo = load_content(repo_root / 'src/karst41/content')
    spec = next(sp for sp in demo.zones[zone.id].meta.spawners if sp.id == 'halo-bouncer')
    zone.template = replace(zone.template, meta=replace(zone.template.meta, spawners=(spec,)))
    place(game, caller, zone.id, zone.template.meta.spawn)
    bouncers = [a for a in zone.actors.values() if a.behaviour.get('spawner') == spec.id]
    assert len(bouncers) == 1
    assert bouncers[0].position == (9, 9)


@pytest.mark.parametrize('key, exit_id, start', [
    ('npc-sodium-regular', 'to-core-plaza', (3, 12)),
    ('npc-plainclothes-warden', 'to-sodium-tin-halo', (89, 12)),
])
def test_demo_posted_regulars_keep_both_row_exits_clear(repo_root, monkeypatch, key, exit_id, start):
    game, caller = boot(repo_root, monkeypatch)
    place(game, caller, 'sodium-row', (44, 20))
    zone = game.core.world.zones['sodium-row']
    demo = load_content(repo_root / 'src/karst41/content')
    spec = next(sp for sp in demo.zones[zone.id].meta.spawners if sp.npc == key)
    home = next(post.tile for post in spec.posts if post.home)
    actor = make_actor(game.core.world.content.npcs[key], 'demo-exit-regression',
        {'home': home, 'posts': spec.posts, 'post_crowd': spec.poses_as or spec.id,
         'post_cap': spec.moving_cap, 'post_until': 0, 'state': 'base'})
    game.core.world.enter(actor, zone.id, start)
    exit_ = next(ex for ex in zone.template.meta.exits if ex.id == exit_id)
    assert zone.can_enter(actor, exit_.tile)
    game.core.npcs.act(actor, zone, game.clock.now_tick(), game.core.npcs.spawners.reserved(zone))
    assert actor.position != exit_.tile
    assert actor.position != start
