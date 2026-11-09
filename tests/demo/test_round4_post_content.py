"""Post placement and cover validation, independent of the movement scheduler."""

from dataclasses import replace

from karst41.content.loader import load_content
from karst41.content.schema import Post, Spawner
from karst41.content.validate import validate
from tests.demo.test_truce_standin import boot


def problems(content, zone, spawner):
    content.zones[zone.id] = replace(zone, meta=replace(zone.meta,
        moving_budget=4, spawners=(spawner,)))
    return [p.message for p in validate(content) if 'spawner fixture' in p.message]


def test_posts_reject_objects_hazards_bad_holds_and_missing_homes(repo_root):
    content = load_content(repo_root / 'src/karst41/content')
    zone = content.zones['sodium-row']
    spawner = Spawner('fixture', 'npc-sodium-regular', 1, 60,
                      posts=(Post((84, 2), home=True),))
    assert any('clear of objects' in message for message in problems(content, zone, spawner))
    invalid = replace(spawner, posts=(Post((46, 17), hold_seconds=(30, 10), weight=0),))
    messages = problems(content, zone, invalid)
    assert any('one home per person' in message for message in messages)
    assert any('ordered positive hold' in message for message in messages)


def test_reserved_home_is_not_reused_while_resident_is_away(repo_root, monkeypatch):
    game, _ = boot(repo_root, monkeypatch)
    zone = game.core.world.zones['sodium-row']
    spec = Spawner('fixture', 'npc-sodium-regular', 1, 60,
                   posts=(Post((46, 17), home=True),))
    zone.template = replace(zone.template, meta=replace(zone.template.meta, spawners=(spec,)))
    game.core.npcs.spawners.process(zone, game.core.combat.now())
    resident = next(iter(zone.actors.values()))
    game.core.world.enter(resident, zone.id, (48, 17))
    assert game.core.npcs.spawners.location(zone, spec) is None


def test_cover_must_match_all_post_numbers(repo_root):
    content = load_content(repo_root / 'src/karst41/content')
    zone = content.zones['sodium-row']
    regular = Spawner('regular', 'npc-sodium-regular', 1, 60,
                      posts=(Post((46, 17), home=True), Post((58, 17), home=True)))
    cover = replace(regular, id='cover', npc='npc-plainclothes-warden', poses_as='regular',
                    posts=(Post((46, 17), home=True, hold_seconds=(1, 2)),))
    content.zones[zone.id] = replace(zone, meta=replace(zone.meta,
        moving_budget=4, spawners=(regular, cover)))
    assert any('poses_as must match posts' in p.message for p in validate(content))
