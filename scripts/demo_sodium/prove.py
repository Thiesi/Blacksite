"""Round4 native smoke, through a real NetBBS registered stdio door.

Disclosed fixtures: grade/funding, initial positions, skipped combat
tutorial and zero shock. No timing acceptance, human playtest or S11
credit. Raw ANSI and directly rendered terminal-grid PNGs are retained.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT), str(ROOT / 'scripts')]

from accept_s10_netbbs import NativeProbe, wait
from scripts.demo_sodium.content import install_overlay


def position(probe: NativeProbe, connection: Any, zone_id: str, tile: tuple[int, int]) -> None:
    """Explicit scenario placement; movement/access mechanics are not waived."""
    sim, avatar = probe.game.sim, connection.avatar
    if avatar.zone:
        probe.service.world.zones[avatar.zone].deactivate(connection.session.id, probe.service.clock.now_tick())
    zone = probe.service.world.zones[zone_id]
    probe.service.world.enter(avatar.actor, zone_id, probe.service.world.free_tile(zone_id, tile, avatar.actor))
    avatar.zone = connection.session.subscribed = zone_id
    zone.activate(connection.session.id, probe.service.clock.now_tick())
    sim.reset_view(connection.session, avatar)


def save(probe: NativeProbe, connection: Any, label: str) -> None:
    """Save actual caller bytes/grid; PNG is a replay, not a new rendering."""
    from scripts.presentation_mockups.website.screenshot import png
    probe.save(connection, label)
    png(connection.caller.screen, probe.root / (label + '.png'))


async def position_ack(probe: NativeProbe, connection: Any) -> None:
    """Wait for this placement's published view, not a prior acknowledged one."""
    avatar = connection.avatar
    zone, tile = avatar.zone, avatar.actor.position
    def current() -> bool:
        view = probe.game.sim.views[connection.session.id].previous or {}
        body = view.get('body', {})
        return (view.get('kind') == 'zone' and body.get('me', {}).get('zone') == zone
                and any(actor['id'] == avatar.actor.id and (actor['x'], actor['y']) == tile
                        for actor in body.get('actors', []))
                and connection.session.ack_revision == connection.session.view_revision)
    await wait(current)


async def run(root: Path, python: Path) -> None:
    os.environ['KARST41_DEMO'] = 'sodium-row-evening'
    probe = NativeProbe(root, python, False, door_environment={'DOOR_KARST41_PRESENTATION': '1'})
    probe.service.install_dir.mkdir(parents=True, exist_ok=True)
    install_overlay(probe.service.install_dir)
    results: list[dict[str, Any]] = []
    try:
        await probe.start()
        for width, height in ((80, 24), (132, 50)):
            source = await probe.open(width, height, 'Round4', truecolor=width == 132)
            peer = await probe.open(width, height, 'Peer', truecolor=width == 132)
            for connection in (source, peer):
                probe.fixture(connection)
                probe.game.players[connection.session.player_id].progress['wake_combat'] = 'skipped'
                connection.avatar.actor.shock = 0
                connection.avatar.actor.target = None
            position(probe, source, 'sodium-row', (41, 12))
            position(probe, peer, 'sodium-row', (42, 13))
            await position_ack(probe, source)
            before = len(probe.service.core.npcs.provocations)
            await source.caller.write(b'f')
            actor = source.avatar.actor
            await wait(lambda: actor.behaviour.get('drawn') is True)
            await wait(lambda: 'DRAWN' in source.caller.screen.screen_text())
            assert len(probe.service.core.npcs.provocations) == before
            await wait(lambda: 'sodium-row' in probe.service.core.demo_weapons.watchers)
            watch = probe.service.core.demo_weapons.watchers['sodium-row']
            guard = probe.service.world.actors[watch.guard]
            await wait(lambda: max(abs(guard.x-actor.x), abs(guard.y-actor.y)) <= 4)
            save(probe, source, f'drawn-watch-{width}x{height}')
            await probe.target(peer, actor.id)
            await wait(lambda: any('Round4' in line and 'drawn' in line
                                  for line in peer.caller.screen.screen_text().splitlines()[1:4]))
            save(probe, peer, f'peer-target-drawn-{width}x{height}')
            position(probe, source, 'sodium-row', (89, 12))
            await position_ack(probe, source)
            await source.caller.write(b'e')
            await wait(lambda: any('Put it away first.' in line.get('text', '') for line in source.session.log_ring))
            assert source.avatar.zone == 'sodium-row'
            await wait(lambda: 'Put it away first.' in source.caller.screen.screen_text())
            save(probe, source, f'halo-drawn-refusal-{width}x{height}')
            await source.caller.write(b'd')
            await wait(lambda: actor.behaviour.get('drawn') is False)
            await source.caller.write(b'e')
            await wait(lambda: source.avatar.zone == 'sodium-tin-halo')
            await position_ack(probe, source)
            await wait(lambda: 'The Tin Halo' in source.caller.screen.screen_text().splitlines()[0])
            save(probe, source, f'halo-holstered-entry-{width}x{height}')
            halo = probe.service.world.zones['sodium-tin-halo']
            door = halo.objects['halo-back-room']
            choices = [(door.spec.tile[0]+dx, door.spec.tile[1]+dy)
                       for dx, dy in ((-1,0),(1,0),(0,-1),(0,1))]
            for tile in choices:
                if not halo.passable(tile):
                    continue
                position(probe, source, halo.id, tile)
                choice = probe.game.sim.interaction_target(source.avatar)
                if getattr(getattr(choice.value, 'spec', None), 'id', '') != door.spec.id:
                    continue
                await position_ack(probe, source)
                await source.caller.write(b'e')
                await wait(lambda: any('Locked. The latch runs off the Tin Halo core.' in line.get('text', '')
                                       for line in source.session.log_ring))
                await wait(lambda: 'latch runs off the Tin Halo core.' in source.caller.screen.screen_text())
                break
            else:
                raise AssertionError('No usable back-room door approach')
            save(probe, source, f'back-way-core-name-{width}x{height}')
            core = probe.game.content.cores['lat-tin-halo']
            assert next(r for r in core.rooms if r.id == 'room-3').label == 'Back room'
            results.append({'size': [width,height], 'first_fire_draws': True, 'watch': True,
                            'peer_drawn': True, 'halo_refusal': True, 'holstered_entry': True,
                            'locked_core_name': True, 'back_room_label': True})
            await probe.leave(peer, f'peer-return-{width}x{height}')
            await probe.leave(source, f'owner-return-{width}x{height}')
        assert not probe.errors, probe.errors
        (root/'result.json').write_text(json.dumps({'passed': True, 'transport': 'NetBBS Telnet native stdio',
            'fixtures': ['grade5/funding/ammunition', 'zero shock', 'initial positions', 'skipped combat tutorial'], 'teleports': True,
            'human_playtest': False, 's11_credit': False, 'runs': results}, indent=2)+'\n', encoding='utf-8')
    finally:
        if hasattr(probe, 'node'):
            await probe.close()
        else:
            await probe.service.stop()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--door-python', type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(run(args.root.resolve(), args.door_python))


if __name__ == '__main__':
    main()
