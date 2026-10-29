"""S25b TR-4: reject ineffective route doors, retain visible S08 debt."""

from dataclasses import replace
from pathlib import Path

import pytest

from blacksite.content.validate import door_wall_axis, route_door_warnings, validate
from blacksite.content.loader import load_content
from tests.content.support import World


def test_controlled_fixture_door_requires_a_real_wall_axis(world: World) -> None:
    assert not world.problems()
    rows = world.path('zones/fx-street.map').read_text(encoding='utf-8').splitlines()
    rows[6] = rows[6][:57] + '.' + rows[6][58:]
    world.write_text('zones/fx-street.map', '\n'.join(rows)+'\n')
    assert any('route-bearing door fx-street-gate' in p.message for p in world.problems())


@pytest.mark.parametrize('binding', ['decorative', 'control', 'credential', 'required_exit'])
def test_binding_behaviour_selects_route_doors(world: World, binding: str) -> None:
    zone = world.read('zones/fx-street.json')
    obj = {'id': 'new-door', 'kind': 'door', 'tile': [30, 10], 'params': {}}
    zone['objects'].append(obj)
    if binding == 'control':
        obj['params']['control'] = True
    elif binding == 'credential':
        zone['exits'][0]['requirement'] = {'kind': 'open', 'ref': 'fx-street', 'object': 'new-door'}
    elif binding == 'required_exit':
        obj['tile'] = zone['exits'][0]['tile']
        zone['exits'][0]['requirement'] = {'kind': 'pass', 'ref': world.read('items.json')['items'][0]['id']}
    world.write('zones/fx-street.json', zone)
    issues = [p for p in world.problems() if 'route-bearing door new-door' in p.message]
    assert bool(issues) == (binding != 'decorative')


def test_wall_axis_requires_open_sides() -> None:
    solid = {(0, -1), (0, 1)}
    assert door_wall_axis(lambda p: p not in solid, (0, 0)) == ((0, -1), (0, 1))
    solid.add((1, 0))
    assert door_wall_axis(lambda p: p not in solid, (0, 0)) is None


def test_s08_warning_is_named_and_future_zones_are_errors(repo_root: Path) -> None:
    content_tree = load_content(repo_root/'src/blacksite/content')
    warnings = route_door_warnings(content_tree)
    assert len(warnings) == 7
    assert all('C1 #92' in p.message for p in warnings)
    assert any('halo-back-room' in p.message for p in warnings)
    assert not any('marshal-office' in p.message for p in warnings)
    assert not validate(content_tree)
    old = content_tree.zones.pop('core-precinct')
    content_tree.zones['future-hub'] = replace(old, meta=replace(old.meta, id='future-hub',
        objects=tuple(replace(o, params={**o.params, 'control': True}) if o.id == 'holding-cell-west' else o
                      for o in old.meta.objects)))
    assert any('route-bearing door holding-cell-west' in p.message for p in validate(content_tree))


def test_new_bad_route_door_in_s08_hub_is_an_error(repo_root: Path) -> None:
    tree = load_content(repo_root/'src/blacksite/content')
    zone = tree.zones['core-precinct']
    used = {obj.tile for obj in zone.meta.objects}
    def floor(tile: tuple[int, int]) -> bool:
        key = zone.tile_at(tile)
        return key in tree.tiles and tree.tiles[key].passable
    tile = next((x, y) for y in range(1, zone.height-1) for x in range(1, zone.width-1)
                if (x, y) not in used and all(floor(p) for p in
                    ((x, y), (x-1, y), (x+1, y), (x, y-1), (x, y+1))))
    old = next(obj for obj in zone.meta.objects if obj.id == 'holding-cell-west')
    added = replace(old, id='new-route-door', tile=tile, params={'control': True})
    tree.zones[zone.id] = replace(zone, meta=replace(zone.meta, objects=(*zone.meta.objects, added)))
    assert any('route-bearing door new-route-door' in p.message for p in validate(tree))
    assert len(route_door_warnings(tree)) == 7
    assert not any('new-route-door' in p.message for p in route_door_warnings(tree))


def test_repairing_a_known_door_removes_its_warning(repo_root: Path) -> None:
    tree = load_content(repo_root/'src/blacksite/content')
    zone = tree.zones['sodium-tin-halo']
    door = next(obj for obj in zone.meta.objects if obj.id == 'halo-back-room')
    x, y = door.tile
    grid = [list(row) for row in zone.grid]
    grid[y-1][x] = grid[y+1][x] = 'wall'
    grid[y][x-1] = grid[y][x+1] = 'floor'
    tree.zones[zone.id] = replace(zone, grid=tuple(tuple(row) for row in grid))
    warnings = route_door_warnings(tree)
    assert len(warnings) == 6
    assert not any('halo-back-room' in p.message for p in warnings)
