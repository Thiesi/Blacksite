"""Game 12: labelled source fixtures, restart and exact warned footprints."""

from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import sqlite3
import json
from typing import Any

from blacksite.content.schema import Effect, EventTemplate, Region
from blacksite.server.rules.events import SCHEDULES
from blacksite.server.world.zone import GeometryLayer
from tests.harness import HeadlessServer
from tests.server.test_event_engine import base_content, events_game, force, advance
from blacksite.server.storage.db import Storage
import pytest


def author(game: Any) -> str:
    owner = game.core.events
    zid = 'vatside-clinics'
    zone = owner.world.zones[zid]
    reserved = {obj.spec.tile for obj in zone.objects.values()} | {e.tile for e in zone.template.meta.exits}
    tile = next((x, y) for y in range(2, zone.template.height-2) for x in range(2, zone.template.width-2)
        if all(zone.passable((x+dx, y+dy)) and zone.allows_hostile((x+dx, y+dy))
               and (x+dx, y+dy) not in reserved for dx in (-1, 0, 1) for dy in (-1, 0, 1)))
    template = EventTemplate('exhale', 'Exhale', (zid,), *SCHEDULES['exhale'], effects=(
        Effect('hazard', zone=zid, region=Region(tile[0]-1, tile[1]-1, 3, 3),
               warning_seconds=5, params={'radius': 0, 'seconds': 20}),
        Effect('key_drop', zone=zid, region=Region(*tile, 1, 1), params={'item': 'key_curfew_pass'})))
    owner.content.events[template.id] = template
    return zid


def saved(game: Any, player: Any) -> dict[str, Any]:
    return {'events': game.core.events.scheduler.record(), 'players': [player.record()],
        'identities': deepcopy(game.core.characters.identities),
        'items': [item.record() for item in game.core.commerce.items.values()],
        'caches': deepcopy(game.core.commerce.caches)}


def test_game_12_warning_and_impact_use_same_saved_site_and_cancel_preserves_other_layer(events_game: tuple[Any, ...]) -> None:
    game, client, player = events_game
    zid = author(game)
    force(game, 'exhale')
    owner = game.core.events
    plan = next(plan for plan in owner.scheduler.reserved() if plan.template == 'exhale')
    site = plan.allocations['sites']['0']
    zone = owner.world.zones[zid]
    layer = next(layer for name, layer in zone.layers.items() if name.startswith('event:'))
    assert layer.layout.warning_tiles == (tuple(site['tile']),)
    assert tuple(change.tile for change in layer.layout.changes) == layer.layout.warning_tiles
    assert not any(zone.tile_id(tuple(tile)) == 'hazard' for tile in site['tiles'])
    advance(game, 6)
    assert zone.tile_id(tuple(site['tile'])) == 'hazard'
    foreign = replace(layer, source='fixture-service')
    zone.layers['fixture-service'] = foreign
    owner.admin('event.cancel', {'plan': plan.id}, lambda value: None)
    game.step()
    game.commit_commerce()
    assert zone.layers['fixture-service'] is foreign
    assert not any(name.startswith('event:') for name in zone.layers)


def test_arch_15_exhale_restart_and_failed_source_do_not_duplicate_keys(events_game: tuple[Any, ...]) -> None:
    game, client, player = events_game
    author(game)
    force(game, 'exhale')
    owner = game.core.events
    game.clock.advance(60)
    game.step()
    game.commit_commerce(error=True)
    assert not any(':key:' in item.owner for item in owner.commerce.items.values())
    game.step(10)
    game.commit_commerce()
    keys = {iid for iid, item in owner.commerce.items.items() if ':key:' in item.owner}
    assert len(keys) == 1
    restored = HeadlessServer(owner.content, character_state=saved(game, player), clock=game.clock)
    assert {iid for iid, item in restored.core.commerce.items.items() if ':key:' in item.owner} == keys
    advance(restored, 10)
    assert {iid for iid, item in restored.core.commerce.items.items() if ':key:' in item.owner} == keys


def test_game_12_changed_content_cancels_published_site_instead_of_redirecting_it(events_game: tuple[Any, ...]) -> None:
    game, client, player = events_game
    author(game)
    force(game, 'exhale')
    owner = game.core.events
    plan = next(iter(owner.scheduler.reserved()))
    state = saved(game, player)
    content = deepcopy(owner.content)
    template = content.events['exhale']
    content.events['exhale'] = replace(template, effects=tuple(reversed(template.effects)))
    restored = HeadlessServer(content, character_state=state, clock=game.clock)
    corrected = restored.core.events.scheduler.plans[plan.id]
    assert corrected.state == 'cancelled' and corrected.revision > plan.revision
    assert corrected.allocations['sites'] == plan.allocations['sites']
    assert 'earlier forecast' in corrected.cancel_reason


def test_arch_6_2_sqlite_failure_cannot_save_key_without_event_receipt(events_game: tuple[Any, ...], scratch_dir: Path) -> None:
    game, client, player = events_game
    author(game)
    force(game, 'exhale')
    owner = game.core.events
    before = owner.scheduler.record()
    game.clock.advance(60)
    game.step()
    source = next(effect for effect in owner.commerce.outbox if 'events_state' in effect)
    prepared = owner.commerce.prepare(source)
    assert prepared['items'] and prepared['events_state'] != before
    store = Storage(scratch_dir/'event-atomic.db', game.clock)
    try:
        store.mark_dirty('meta', 'events_state', before)
        store.flush_now()
        store.db.execute("CREATE TRIGGER fail_event BEFORE INSERT ON meta WHEN NEW.key='events_state' BEGIN SELECT RAISE(ABORT,'injected event failure'); END")
        with pytest.raises(sqlite3.IntegrityError, match='injected event failure'):
            store.commerce_write(prepared)
        assert store.meta('events_state') == json.loads(json.dumps(before))
        assert store.db.execute('SELECT count(*) FROM items').fetchone()[0] == 0
        assert store.db.execute('SELECT count(*) FROM caches').fetchone()[0] == 0
        store.db.execute('DROP TRIGGER fail_event')
        store.commerce_write(prepared)
        assert store.meta('events_state') == json.loads(json.dumps(prepared['events_state']))
        assert store.db.execute('SELECT count(*) FROM items').fetchone()[0] == 1
        assert store.db.execute('SELECT count(*) FROM caches').fetchone()[0] == 1
    finally:
        store.close()
