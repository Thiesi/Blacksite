"""World Lattice 3 and game 6.7: the staged catalog is real content."""

from pathlib import Path
import re

from blacksite.content.loader import load_content
from blacksite.content.validate import validate
from blacksite.server.lattice.sectors import access


def test_world_3_complete_district_registry_and_inactive_templates(repo_root: Path):
    tree = load_content(repo_root/'src/blacksite/content')
    assert not validate(tree)
    entries = {c.core_id or c.planned_core for s in tree.sectors.values()
               for c in s.cells if c.kind == 'core_entrance'}
    assert len(entries) == 49  # World 3.8 adds the first-job Stairwell C cabinet.
    templates = {'lat-private-core', 'lat-relay-uplink', 'lat-uplink-hall'}
    assert set(tree.cores) == entries | templates
    assert all(tree.cores[cid].template and not tree.active('cores', cid) for cid in templates)
    assert sum(tree.active('cores', cid) for cid in tree.cores) == 14
    for sector in tree.sectors.values():
        for cell in sector.cells:
            if cell.core_id:
                assert access(cell) == 'public'
                assert tree.active('cores', cell.core_id)
            elif cell.planned_core:
                assert not tree.active('cores', cell.planned_core)
    for cid, core in tree.cores.items():
        if not tree.active('cores', cid) and not core.template:
            assert all(hw.tile is None for hw in core.hardware)
        if core.training or core.template:
            assert not core.hardware
        elif tree.active('cores', cid):
            assert all(hw.zone in tree.zones and hw.object_id for hw in core.hardware)
    assert {cid for cid, core in tree.cores.items() if len(core.hardware) == 2} == {'lat-shaft'}


def test_world_3_named_room_counts_and_bestiary_are_not_generic_placeholders(repo_root: Path):
    tree = load_content(repo_root/'src/blacksite/content')
    world = (repo_root/'docs/world/03-lattice.md').read_text(encoding='utf-8')
    for name, cid, description in re.findall(r'\*\*([^\n]+?)\*\* \(`(lat-[^`]+)`\)(.*?)(?=\n\n|\Z)', world, re.S):
        match = re.search(r'tier (\d),\s*(\d+) rooms', description)
        if 'planned (#' in description:
            # Canon ahead of content (#90): a Stage 2 slice builds it and removes the marker.
            assert cid not in tree.cores
        elif match:
            core = tree.cores[cid]
            assert (core.tier, len(core.rooms)) == tuple(map(int, match.groups()))
    assert len(tree.cores['lat-wake-hall'].rooms) == 1
    assert tree.cores['lat-wake-hall'].tier == 0
    assert len(tree.cores['lat-uplink-hall'].rooms) == 10
    assert sum('ice_suture' in r.ice for r in tree.cores['lat-vatline'].rooms) == 2
    assert sum(r.ice.count('ice_glasshouse') for r in tree.cores['lat-halvard-citadel'].rooms) == 2
    assert sum(r.ice.count('ice_blackglass') for r in tree.cores['lat-halvard-citadel'].rooms) == 2


def test_game_6_7_optional_credit_and_all_asset_references(repo_root: Path):
    tree = load_content(repo_root/'src/blacksite/content')
    tables = {'text': tree.text, 'evidence': tree.evidence, 'schematic': tree.items,
              'salvage_data': tree.items, 'item': tree.items, 'program': tree.programs}
    for cid, core in tree.cores.items():
        credits = [d for r in core.rooms for d in r.data if d.kind == 'chits']
        assert len(credits) <= 1
        if credits:
            assert credits[0].amount == 40*core.tier and credits[0].respawn_seconds == 1800
        if cid in ('lat-tram-signal', 'lat-kestrel-branch') or core.template:
            assert not credits
        for room in core.rooms:
            for data in room.data:
                if data.kind in tables:
                    assert data.asset in tables[data.kind]
        if not tree.active('cores', cid):
            continue
        for room in core.rooms:
            for control in room.controls:
                assert control.target.zone in tree.zones
                assert any(o.id == control.target.object for o in tree.zones[control.target.zone].meta.objects)


def test_world_08_finished_found_texts_are_loaded_verbatim(repo_root: Path):
    tree = load_content(repo_root/'src/blacksite/content')
    source = (repo_root/'docs/world/08-found-texts.md').read_text(encoding='utf-8')
    assets = [key for key in tree.text if key.startswith('text-') and '## '+key+'\n' in source]
    assert len(assets) == 13
    for asset in assets:
        section = source.split('## '+asset+'\n', 1)[1].split('\n## ', 1)[0]
        expected = section.split('```', 2)[1].strip('\n')
        assert tree.text[asset].body.strip('\n') == expected
