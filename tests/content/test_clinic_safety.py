"""Game 5.1/8.2: whole-zone pockets protect clinics without subregions."""

from dataclasses import replace
from pathlib import Path

from blacksite.content.loader import load_content
from blacksite.content.validate import validate
from blacksite.server.world.registry import World


def test_game_5_1_whole_zone_pocket_protects_clinic_but_contested_requires_region(repo_root: Path) -> None:
    tree = load_content(repo_root/'src/blacksite/content')
    zone = tree.zones['vatside-wake-hall']
    source = next(obj for obj in tree.zones['vatside-clinics'].meta.objects
                  if obj.params.get('vendor') == 'sablier-clinic')
    clinic = replace(source, id='test-clinic', tile=zone.meta.spawn)
    meta = replace(zone.meta, objects=(*zone.meta.objects, clinic), safety='pocket', pockets=())
    tree.zones[zone.id] = replace(zone, meta=meta)
    assert validate(tree) == []
    world = World(tree, {zid: 0 for zid in tree.zones})
    assert world.zones[zone.id].safety_at(clinic.tile) == 'pocket'
    assert not world.zones[zone.id].allows_hostile(clinic.tile)
    # Without a whole-zone safety class, the physical region is required.
    tree.zones[zone.id] = replace(zone, meta=replace(meta, safety='contested'))
    assert any('Sablier clinic requires an existing safe pocket' in p.message for p in validate(tree))
