"""World-coordinate rule projection and deterministic isolated walk."""

from copy import deepcopy
from dataclasses import asdict, replace
from hashlib import sha256
from typing import Any

from blacksite.content.loader import ContentTree
from blacksite.server.protocol import Frame
from blacksite.server.world.registry import World
from blacksite.server.world.sight import sight_radius
from tests.character_helpers import create, place
from tests.harness import FakeClient, HeadlessServer
from tests.presentation.snapshots import canonical


def zone_seed(zone_id: str) -> int:
    return int.from_bytes(sha256(('P1:'+zone_id).encode('utf-8')).digest()[:8], 'big')


def character_game(content: ContentTree, width: int = 80, height: int = 24, *,
                   isolate_npcs: bool = True) -> tuple[HeadlessServer, FakeClient]:
    tree = deepcopy(content)
    if isolate_npcs:
        tree.zones = {zid: replace(zone, meta=replace(zone.meta, spawners=()))
                      for zid, zone in tree.zones.items()}
    game = HeadlessServer(tree, character_state={},
                          zone_seeds={zid: zone_seed(zid) for zid in tree.zones})
    client = game.connect({'user_id': 1, 'handle': 'Verifier界', 'node_name': 'P1'}, width=width, height=height)
    create(game, client, archetype=0, name='Verifier界', card='none')
    return game, client


def projection(content: ContentTree) -> dict[str, Any]:
    world = World(content, {zid: zone_seed(zid) for zid in content.zones})
    zones: dict[str, Any] = {}
    for zid, zone in sorted(world.zones.items()):
        meta = zone.template.meta
        zones[zid] = {'size': [zone.template.width, zone.template.height],
            'spawn': meta.spawn, 'safety': meta.safety, 'pockets': [asdict(p) for p in meta.pockets],
            'sight': [meta.sight_radius, meta.sight_radius_night],
            'tiles': [[zone.tile_id((x, y)) for x in range(zone.template.width)]
                      for y in range(zone.template.height)],
            'state_overrides': [{'tile': [x, y], 'passable': zone.passable((x, y)),
                'opaque': zone.opaque((x, y))} for y in range(zone.template.height)
                for x in range(zone.template.width)
                if (zone.passable((x, y)), zone.opaque((x, y))) !=
                   (zone.tiles[zone.tile_id((x, y))].passable, zone.tiles[zone.tile_id((x, y))].opaque)],
            'exits': [{key: value for key, value in asdict(ex).items() if key != 'locked_text'}
                      for ex in sorted(meta.exits, key=lambda ex: ex.id)],
            'objects': [{'id': obj.id, 'kind': obj.kind, 'tile': obj.tile,
                         'essential': obj.essential} for obj in sorted(meta.objects, key=lambda obj: obj.id)],
            'layouts': [asdict(layout) for layout in meta.layouts]}
    sectors = {sid: {'entry': sector.entry, 'trace_policy': sector.trace_policy,
        'trace_owner': sector.trace_owner,
        'cells': [{key: value for key, value in asdict(cell).items() if key not in ('label', 'lore')}
                  for cell in sorted(sector.cells, key=lambda cell: cell.id)]}
        for sid, sector in sorted(content.sectors.items())}
    tile_rules = {tid: {'passable': tile.passable, 'opaque': tile.opaque, 'cover': tile.cover,
        'hazard': asdict(tile.hazard) if tile.hazard else None, 'movement_cost': tile.movement_cost}
        for tid, tile in sorted(content.tiles.items())}
    return {'tile_rules': tile_rules, 'zones': zones, 'sectors': sectors}


def walk(content: ContentTree, width: int = 80, height: int = 24) -> list[dict[str, Any]]:
    game, client = character_game(content, width, height)
    avatar = game.core.characters.sim.avatars[client.session.user_id]
    rows: list[dict[str, Any]] = []
    directions = (('right', (1, 0), 'left'), ('down', (0, 1), 'up'),
                  ('left', (-1, 0), 'right'), ('up', (0, -1), 'down'))
    for zid, zone in sorted(game.core.world.zones.items()):
        if not game.core.loop.content.active('zones', zid) or zone.template.meta.spawn is None:
            continue
        place(game, client, zid, zone.template.meta.spawn)
        game.commit_commerce()
        start = avatar.actor.position
        choice = next(((name, reverse) for name, (dx, dy), reverse in directions
            if zone.passable((start[0]+dx, start[1]+dy))
            and not any(ex.tile == (start[0]+dx, start[1]+dy) for ex in zone.template.meta.exits)), None)
        if choice is None:
            raise AssertionError(f'P1 walk needs a public adjacent tile: {zid}')
        for action in (*choice, *choice):
            client.send(Frame('intent', {'name': 'move', 'args': {'dir': action}}))
            game.step(2)
            game.commit_commerce()
            actor = avatar.actor
            tile = zone.tiles[zone.tile_id(actor.position)]
            rows.append({'zone': zid, 'action': action, 'position': actor.position,
                'health': actor.health, 'stamina': actor.stamina, 'shock': actor.shock,
                'stance': actor.stance, 'cooldowns': actor.cooldowns.copy(),
                'sight': sight_radius(actor, zone, False), 'cover': tile.cover,
                'hazard': asdict(tile.hazard) if tile.hazard else None})
    return rows


def fingerprint(content: ContentTree) -> dict[str, Any]:
    rules = projection(content)
    steps = walk(content)
    return {'schema': 1, 'seed': 'SHA256(P1:<zone-id>) first eight bytes, big endian',
        'npc_policy': 'isolated spawners; no runtime content changes',
        'projection': rules, 'walk': steps,
        'sha256': sha256(canonical({'projection': rules, 'walk': steps}).encode('utf-8')).hexdigest()}
