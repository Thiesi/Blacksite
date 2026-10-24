"""S25 actual-city native survey, without placement or reward fixtures.

Each case starts a real caller, chooses a recruiter card with keys and
walks the shipped maps through a registered NetBBS native stdio door.
This survey is one acceptance component; it does not claim the separate
commerce, earnings, membership, hardware-operation or human pacing gates.
"""

from __future__ import annotations

import argparse
import asyncio
from collections import deque
import json
from pathlib import Path
import time
import traceback
from typing import Any

from accept_s10_netbbs import Connection, wait
from accept_s16_netbbs import commit_key, key
from accept_s19_netbbs import ContractProbe
from blacksite.content.loader import content_hash
from blacksite.server.world.exits import permitted


CASES = {
    'districts': ('vatside-clinics', 'core-plaza', 'spire-atrium', 'spire-mezzanine',
        'spire-atrium', 'core-plaza', 'core-tram-hub', 'tramyard-market',
        'tramyard-depots', 'tramyard-wall-gate', 'scour-ring-1', 'scour-landing'),
    'southern': ('vatside-clinics', 'core-tram-hub', 'sink-rim', 'sink-terraces',
        'sink-floor', 'under-caverns', 'under-service', 'chapel-towers', 'chapel-nave',
        'chapel-towers', 'terraces-blocks', 'terraces-lobby', 'terraces-blocks',
        'chapel-towers', 'under-service', 'oldworks-yards', 'oldworks-main', 'oldworks-drop'),
    'deep': ('vatside-vat-row', 'under-service', 'under-drowned', 'under-caverns',
        'under-outworks', 'under-shaft-foot', 'under-outworks', 'under-caverns',
        'scour-ring-2', 'scour-landing', 'scour-ring-1', 'scour-ring-2',
        'scour-ring-3', 'scour-ring-4'),
}


class CityProbe(ContractProbe):
    def __init__(self, root: Path, python: Path, show: bool) -> None:
        super().__init__(root, python, show)
        self.walks: list[dict[str, Any]] = []
        self.journeys: list[dict[str, Any]] = []
        # A complete large-map tour includes normal tram/Gate Nine waits.
        # This changes only the private acceptance node's door allowance.
        self.native_time_limit = 3600

    async def start(self) -> None:
        assert not (self.root/'world/content.local').exists(), 'S25 requires the shipped city without overlays'
        await super().start()
        check = await asyncio.create_subprocess_exec(str(self.python), '-I', '-c',
            'from pathlib import Path; import blacksite.content; '
            'from blacksite.content.loader import content_hash; '
            'print(content_hash(Path(blacksite.content.__file__).parent))',
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        output, errors = await asyncio.wait_for(check.communicate(), 30)
        assert check.returncode == 0, errors.decode(errors='replace')
        installed = output.decode().strip()
        assert installed == self.game.content.hash, (installed, self.game.content.hash)
        (self.root/'native-content.json').write_text(json.dumps({
            'installed_content_sha256': installed, 'server_content_sha256': self.game.content.hash,
            'source_content_sha256': content_hash(Path(__file__).parents[1]/'src/blacksite/content'),
            'zones': len(self.game.content.zones), 'local_overlay': False}, indent=2)+'\n', encoding='utf-8')

    async def walk(self, connection: Connection, target: tuple[int, int]) -> None:
        avatar = connection.avatar
        zone = self.service.world.zones[avatar.zone]
        began, start = time.monotonic(), avatar.actor.position
        steps = 0
        while avatar.actor.position != target:
            assert time.monotonic()-began < 120, ('walk timeout', zone.id, avatar.actor.position, target)
            assert avatar.actor.health > 0, ('survey caller defeated', zone.id, avatar.actor.position)
            position = avatar.actor.position
            occupied = {actor.position for actor in zone.actors.values()
                        if actor is not avatar.actor and not (actor.behaviour.get('training') and actor.owner != avatar.actor.id)}
            pending, previous = deque([position]), {position: None}
            streets = {ex.tile for ex in zone.template.meta.exits if ex.kind == 'street'}
            while pending and target not in previous:
                x, y = pending.popleft()
                for tile in ((x+1, y), (x, y+1), (x-1, y), (x, y-1)):
                    if (tile in previous or tile in occupied or not zone.can_enter(avatar.actor, tile)
                            or tile in streets and tile != target):
                        continue
                    if zone.tiles[zone.tile_id(tile)].hazard:
                        continue
                    previous[tile] = (x, y)
                    pending.append(tile)
            if target not in previous:
                await asyncio.sleep(.2)
                continue
            next_ = target
            while previous[next_] != position:
                next_ = previous[next_]
            await wait(lambda: self.service.clock.now_tick() >= max(
                avatar.actor.cooldowns.get('move', 0), avatar.actor.cooldowns.get('knockdown', 0)))
            vector = next_[0]-position[0], next_[1]-position[1]
            await connection.caller.write({(1, 0): b'\x1b[C', (-1, 0): b'\x1b[D',
                                           (0, 1): b'\x1b[B', (0, -1): b'\x1b[A'}[vector])
            try:
                await wait(lambda: avatar.actor.position != position or avatar.zone != zone.id, .7)
            except TimeoutError:
                continue
            steps += 1
            if avatar.zone != zone.id:
                break
        self.walks.append(dict(zone=zone.id, start=list(start), target=list(target), steps=steps,
                               seconds=time.monotonic()-began, health=avatar.actor.health))

    async def travel(self, connection: Connection, destination: str) -> None:
        avatar = connection.avatar
        origin, began = avatar.zone, time.monotonic()
        self.report(f'S25 journey: {origin} -> {destination}')
        choices = [ex for ex in self.service.world.zones[origin].template.meta.exits if ex.target_zone == destination]
        # Prefer the real free ladder; cable payment is tested separately.
        exit_ = min(choices, key=lambda ex: (ex.kind == 'cable', ex.hidden, ex.id))
        zone = self.service.world.zones[origin]
        assert permitted(exit_, self.game.access(connection.session)), (origin, exit_.id)
        tile = exit_.tile
        if not zone.can_enter(avatar.actor, tile):
            x, y = tile
            tile = next(p for p in ((x-1, y), (x+1, y), (x, y-1), (x, y+1)) if zone.can_enter(avatar.actor, p))
        await self.walk(connection, tile)
        if avatar.zone == origin:
            await key(connection, b'e')
        panels = self.service.core.relays.views.menus
        if connection.session.id in panels and panels[connection.session.id].route:
            assert exit_.kind == 'gate'
            await commit_key(self, connection, b'e', lambda: avatar.travel is not None)
        # A tram can wait a complete timetable interval before its ride;
        # a normal lift's timeout must not abort a valid platform wait.
        timeout = {'gate': 310, 'tram': 150}.get(exit_.kind, 15)
        await wait(lambda: avatar.zone == destination, timeout)
        await wait(lambda: self.service.world.zones[destination].template.meta.name in
                   connection.caller.screen.screen_text().splitlines()[0])
        assert avatar.actor.zone == destination
        self.journeys.append(dict(source=origin, target=destination, exit=exit_.id,
                                  seconds=time.monotonic()-began))

    async def inspect(self, caller: Connection, label: str) -> None:
        zid = caller.avatar.zone
        zone = self.service.world.zones[zid]
        for obj in list(zone.objects.values()):
            if obj.spec.kind not in ('hardware', 'relay', 'descent_console'):
                continue
            await self.near(caller, obj.spec.id)
            self.save(caller, label+'-'+zid+'-'+obj.spec.id)
            if obj.spec.kind == 'relay':
                # Stand on the terminal to choose it in a crowded cluster.
                if zone.can_enter(caller.avatar.actor, obj.spec.tile):
                    await self.walk(caller, obj.spec.tile)
                rid = str(obj.spec.params['relay'])
                if not self.service.core.relays.active(rid):
                    await key(caller, b'e')
                    self.save(caller, label+'-'+zid+'-'+obj.spec.id+'-pending-level')
                    continue
                await commit_key(self, caller, b'e', lambda: caller.session.id in self.service.core.relays.views.menus)
                self.save(caller, label+'-'+zid+'-'+obj.spec.id+'-card')
                await commit_key(self, caller, b'\x1b', lambda: caller.session.id not in self.service.core.relays.views.menus)
                await wait(lambda: zone.template.meta.name in caller.caller.screen.screen_text().splitlines()[0])
            elif obj.spec.kind == 'descent_console' and obj.spec.params.get('season_door'):
                await key(caller, b'e')
                await wait(lambda: 'season' in caller.caller.screen.screen_text().lower())
        self.save(caller, label+'-'+zid)
        await key(caller, b'm')
        await wait(lambda: 'CITY MAP' in caller.caller.screen.screen_text())
        self.save(caller, label+'-'+zid+'-overview')
        await key(caller, b'\x1b')
        await wait(lambda: caller.session.id not in self.game.sim.maps)
        await wait(lambda: zone.template.meta.name in caller.caller.screen.screen_text().splitlines()[0])
        if zid in ('spire-mezzanine', 'under-shaft-foot'):
            destination = 'spire-shaft-head'
            exit_ = next(ex for ex in zone.template.meta.exits if ex.target_zone == destination)
            await self.walk(caller, exit_.tile)
            await key(caller, b'e')
            word = 'membership' if zid == 'spire-mezzanine' else 'finale'
            await wait(lambda: word in caller.caller.screen.screen_text().lower())
            assert caller.avatar.zone == zid and caller.avatar.travel is None
            self.save(caller, label+'-'+zid+'-closed-route')
        self.report(f'S25 SURVEY {label}: walked {zid}; hardware/relay and map screenshots saved')


async def accept(root: Path, python: Path, show: bool, size: tuple[int, int], case: str) -> None:
    probe = CityProbe(root, python, show)
    visited = []
    try:
        await probe.start()
        caller = await probe.open(*size, 'S25'+case, 0, True, card='halvard')
        player = probe.game.players[caller.session.player_id]
        assert player.standing.get('halvard') == 10 and player.chits_hand == 200 and player.faction is None
        probe.report('S25 survey: shipped content; actual Halvard recruiter-card choice; no placement, funds, grade, reward, combat or clock fixtures.')
        await probe.walk(caller, (21, 14))
        await key(caller, b'b')
        await wait(lambda: player.progress.get('wake_combat') == 'skipped')
        for destination in CASES[case]:
            await probe.travel(caller, destination)
            if destination not in visited:
                await probe.inspect(caller, case)
                visited.append(destination)
        await probe.leave(caller, 's25-'+case+'-'+str(size[0])+'-left')
        assert not probe.errors and probe.service.failure is None
        (root/'s25-survey.json').write_text(json.dumps({
            'passed': True, 'scope': 'actual-city walking, terminal cards and map rendering',
            'full_slice_acceptance': False, 'case': case, 'size': list(size), 'visited': visited,
            'journeys': probe.journeys, 'walks': probe.walks,
            'transport': 'NetBBS Telnet -> registered native stdio', 'fixtures': [],
            'pending': ['earned membership and Shaft Head', 'commerce/clinics/housing',
                        'hardware operations', 'event/service play', 'earnings and human pacing']},
            indent=2)+'\n', encoding='utf-8')
    except BaseException:
        (root/'failure-trace.txt').write_text(traceback.format_exc(), encoding='utf-8')
        (root/'s25-partial.json').write_text(json.dumps({
            'passed': False, 'case': case, 'size': list(size), 'visited': visited,
            'journeys': probe.journeys, 'walks': probe.walks}, indent=2)+'\n', encoding='utf-8')
        raise
    finally:
        if hasattr(probe, 'node'):
            await probe.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--door-python', type=Path, required=True)
    parser.add_argument('--show', action='store_true')
    parser.add_argument('--size', choices=('80x24', '132x50'), required=True)
    parser.add_argument('--case', choices=tuple(CASES), required=True)
    args = parser.parse_args()
    asyncio.run(accept(args.root, args.door_python, args.show,
                       tuple(map(int, args.size.split('x'))), args.case))
