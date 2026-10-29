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
