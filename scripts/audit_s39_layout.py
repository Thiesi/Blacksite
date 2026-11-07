"""Report exit arrivals and talker access; never change authored geometry."""

import argparse
from collections import deque
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT)]

from blacksite.content.loader import load_content
from blacksite.server.world.registry import World


def audit(root: Path = ROOT) -> dict[str, Any]:
    content = load_content(root/'src/blacksite/content')
    assert not content.load_problems, content.load_problems
    assert len(content.zones) == len(list((root/'src/blacksite/content/zones').glob('*.json')))
    world = World(content, {zid: 0 for zid in content.zones})
    arrivals, stranded, unreachable, threshold_givers = [], [], [], []
    checked_positions = 0
    for zid, zone in sorted(world.zones.items()):
        active = content.active('zones', zid)
        for exit_ in zone.template.meta.exits:
            target = world.zones.get(exit_.target_zone)
            if target is None:
                continue
            underfoot = [ex.id for ex in target.template.meta.exits if ex.tile == exit_.target_tile]
            if underfoot:
                arrivals.append({'zone': zid, 'exit': exit_.id, 'target_zone': target.id,
                    'target_tile': exit_.target_tile, 'underfoot': underfoot, 'active': active})
        def safe(tile: tuple[int, int]) -> bool:
            key = zone.tile_id(tile)
            return zone.can_enter(None, tile) and not content.tiles[key].hazard
        spawn = zone.template.meta.spawn
        reached = {spawn} if spawn is not None and safe(spawn) else set()
        pending = deque(reached)
        while pending:
            x, y = pending.popleft()
            for tile in ((x+1, y), (x-1, y), (x, y+1), (x, y-1)):
                if tile not in reached and safe(tile):
                    reached.add(tile)
                    pending.append(tile)
        exits = {ex.tile for ex in zone.template.meta.exits}
        contacts: list[tuple[str, tuple[int, int], bool, bool]] = []
        for obj in zone.objects.values():
            did = obj.spec.params.get('dialogue')
            talker = content.dialogue.get(did)
            if obj.spec.params.get('contract_handler') or talker and any(o.kind == 'contract' for o in talker.offers):
                for exit_ in zone.template.meta.exits:
                    if max(abs(exit_.tile[0]-obj.spec.tile[0]), abs(exit_.tile[1]-obj.spec.tile[1])) <= 1:
                        threshold_givers.append({'zone': zid, 'exit': exit_.id, 'giver': obj.spec.id,
                                                 'position': obj.spec.tile, 'active': active})
            if talker and not talker.machine_mind or obj.spec.params.get('contract_handler'):
                contacts.append((obj.spec.id, obj.spec.tile, False,
                                 active and (not talker or content.active('dialogue', did))))
        for spawner in zone.template.meta.spawners:
            npc = content.npcs[spawner.npc]
            talker = content.dialogue.get(npc.dialogue)
            if not (talker and not talker.machine_mind or any(b.kind == 'talker' for b in npc.behaviours)):
                continue
            positions = set(spawner.region.tiles()) if spawner.region else {spawner.tile}
            for behaviour in npc.behaviours:
                positions.update(tuple(tile) for tile in behaviour.params.get('waypoints', ()))
            for tile in sorted(p for p in positions if p is not None and safe(p)):
                contacts.append((spawner.id+':'+npc.id, tile, True,
                                 active and (not talker or content.active('dialogue', npc.dialogue))))
                if talker and any(o.kind == 'contract' for o in talker.offers):
                    for exit_ in zone.template.meta.exits:
                        if max(abs(exit_.tile[0]-tile[0]), abs(exit_.tile[1]-tile[1])) <= 1:
                            threshold_givers.append({'zone': zid, 'exit': exit_.id,
                                'giver': spawner.id+':'+npc.id, 'position': tile, 'active': active})
        for name, (x, y), occupied, live in contacts:
            checked_positions += 1
            neighbours = {(x+dx, y+dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                          if not occupied or dx or dy} & reached
            row = {'zone': zid, 'contact': name, 'position': (x, y), 'active': live,
                   'reachable_interaction_tiles': sorted(neighbours)}
            if neighbours and neighbours <= exits:
                stranded.append(row)
            elif not neighbours:
                unreachable.append(row)
    return {'scope': 'Every shipped zone, including inactive authoring bundles. Static base geometry, '
            'public flood from spawn; ignores temporary actors and dynamic locks. NPC regions and patrol '
            'waypoints are possible positions, not observations of live placement.',
            'zones': len(world.zones), 'contact_positions_checked': checked_positions,
            'arrivals_on_exits': arrivals, 'only_exit_access': stranded,
            'no_public_access': unreachable, 'exit_adjacent_givers': threshold_givers}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = audit()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print({key: len(value) if isinstance(value, list) else value for key, value in result.items()})
