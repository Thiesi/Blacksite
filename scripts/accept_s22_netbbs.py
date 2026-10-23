"""S22 actual native stdio: consent, remote roster, beacon, pickup and XP.

Fixtures: grades five/seven, an attack-delayed one-HP maintenance drone,
and one direct legal drone hit to isolate the five-second down window.
Travel, crew choices, jacking, pickup, chat, targeting and firing use keys.
"""

import argparse
import asyncio
from collections import deque
import json
from pathlib import Path
import traceback

from accept_s10_netbbs import Connection, NativeProbe, wait
from accept_s16_netbbs import commit_key, key, select
from blacksite.server.npcs.templates import make_actor
from blacksite.server.rules.character import grade_threshold


class CrewProbe(NativeProbe):
    async def walk(self, connection: Connection, target: tuple[int, int]) -> None:
        write = connection.caller.write
        async def checked_write(data: bytes) -> None:
            if connection.session.pending_prompts.get('chat'):
                raise AssertionError('Unexpected chat prompt during native movement')
            await write(data)
        connection.caller.write = checked_write
        try:
            await super().walk(connection, target)
        finally:
            connection.caller.write = write


async def crew_menu(probe: NativeProbe, caller: Connection, row: str) -> object:
    crews = probe.service.core.crews
    await key(caller, b'g')
    await wait(lambda: caller.session.id in crews.menus)
    screen = crews.menus[caller.session.id]
    await select(caller, lambda: crews.body(caller.session, screen)['rows'], screen, row)
    return screen


async def close_menu(probe: NativeProbe, caller: Connection) -> None:
    await key(caller, b'\x1b')
    await wait(lambda: caller.session.id not in probe.service.core.crews.menus)


async def run_size(probe: NativeProbe, width: int, height: int) -> dict:
    a = await probe.open(width, height, 'CrewA', 3, True)
    await probe.walk(a, (12, 10))
    b = await probe.open(width, height, 'CrewB', 0, True)
    await probe.walk(b, (14, 10))
    pa, pb = [probe.game.players[c.session.player_id] for c in (a, b)]
    for caller, grade in ((a, 5), (b, 7)):
        player = probe.game.players[caller.session.player_id]
        player.update_progression(grade_threshold(grade))
        player.update_personhood(probe.game.identity(player.bbs_user_id), probe.service.clock.now_utc())
        probe.game.queue('save', player.bbs_user_id, player, immediate=True)
    probe.service._character_writes()
    crews = probe.service.core.crews
    await crew_menu(probe, a, pb.id)
    await commit_key(probe, a, b'i', lambda: any(i.target == pb.id for i in crews.registry.invites.values()))
    assert crews.crew_id(pa.id) is None
    await close_menu(probe, a)
    invitation = next(i for i in crews.registry.invites.values() if i.target == pb.id)
    await crew_menu(probe, b, invitation.id)
    await commit_key(probe, b, b'a', lambda: crews.crew_id(pb.id) is not None)
    await close_menu(probe, b)
    await wait(lambda: pb.name in a.caller.screen.screen_text())
    probe.save(a, f's22-consenting-crew-{width}')
    probe.report(f'S22 {width}x{height}: actual invite/accept and live roster passed')

    await key(a, b't')
    await wait(lambda: 'chat' in a.session.pending_prompts)
    token = f'CREW HOLDS {width}'
    await wait(lambda: 'Crew:' in a.caller.screen.screen_text())
    await a.caller.write(token.encode()+b'\r')
    await wait(lambda: token in b.caller.screen.screen_text())
    probe.save(b, f's22-crew-chat-{width}')

    await probe.travel(b, 'vatside-clinics')
    await probe.travel(b, 'core-plaza')
    await probe.walk(b, (30, 5))
    await wait(lambda: probe.service.world.zones['core-plaza'].template.meta.name in a.caller.screen.screen_text())
    await crew_menu(probe, a, pb.id)
    await commit_key(probe, a, b'o', lambda: crews.registry.crew_of(pa.id).beacon == (pa.id, pb.id))
    await close_menu(probe, a)
    probe.save(a, f's22-cross-zone-beacon-{width}')
    lattice = probe.service.core.lattice
    await key(b, b'e')
    await wait(lambda: pb.id in lattice.presences)
    await wait(lambda: 'jack /' in a.caller.screen.screen_text())
    assert next(r for r in crews.roster(pa.id) if r['id'] == pb.id)['hp_pct'] == 100
    probe.save(a, f's22-jacked-roster-{width}')
    await probe.travel(a, 'vatside-clinics')
    await probe.travel(a, 'core-plaza')
    await probe.walk(a, (31, 6))
    await wait(lambda: any(o.get('id') == 'crew-beacon' for o in
        probe.game.sim.views[a.session.id].previous['body'].get('objects', [])))
    probe.save(a, f's22-local-beacon-{width}')
    await key(b, b'j')
    await wait(lambda: pb.id not in lattice.presences, 10)
    for caller, tile in ((a, (25, 3)), (b, (26, 3))):
        await probe.travel(caller, 'vatside-clinics')
        await probe.walk(caller, tile)
    drone = make_actor(probe.game.content.npcs['npc-maintenance-drone'], f's22-fixture-drone:{width}',
                       {'home': (28, 3), 'phase': 0})
    drone.health = drone.health_max = 1
    drone.cooldowns['weapon'] = probe.service.clock.now_tick()+6000
    probe.service.world.enter(drone, 'vatside-clinics', (28, 3))
    await wait(lambda: not probe.commerce.pending)
    probe.combat.hurt(drone, a.avatar.actor, 10000)
    await wait(lambda: a.avatar.actor.stance == 'down')
    await key(b, b'e')
    await wait(lambda: a.avatar.actor.stance == 'normal', 4)
    assert a.avatar.actor.health > 0 and 'combat' not in pa.progress
    probe.save(b, f's22-five-second-pickup-{width}')
    await asyncio.sleep(10.2)
    before_a, before_b = pa.xp, pb.xp
    await probe.target(a, drone.id)
    async with asyncio.timeout(25):
        while drone.id in probe.service.world.actors:
            await key(a, b'f')
            await asyncio.sleep(.4)
    await wait(lambda: pb.xp > before_b)
    assert pa.xp-before_a == pb.xp-before_b
    await wait(lambda: '(crew)' in b.caller.screen.screen_text())
    probe.save(b, f's22-shared-kill-xp-{width}')
    await probe.target(a, pb.id)
    await wait(lambda: probe.service.clock.now_tick() >= a.avatar.actor.cooldowns.get('weapon', 0))
    before_health = b.avatar.actor.health
    await key(a, b'f')
    await wait(lambda: "You don't shoot crew." in a.caller.screen.screen_text())
    assert b.avatar.actor.health == before_health and not pa.marked_until
    probe.save(a, f's22-friendly-fire-refused-{width}')
    await probe.leave(b, f's22-b-return-{width}')
    await wait(lambda: crews.crew_id(pa.id) is None)
    await probe.leave(a, f's22-a-return-{width}')
    probe.report(f'S22 PASS {width}x{height}: remote/jacked roster, beacon, pickup, equal shared XP, friendly-fire refusal')
    return {'size': [width, height], 'wide_names': True, 'consenting_invitation': True,
            'crew_chat': True, 'remote_and_jacked_roster': True, 'operator_beacon': True,
            'five_second_pickup': True, 'equal_shared_xp': pa.xp-before_a,
            'friendly_fire_refused': True, 'logout_dissolves': True}


async def accept(root: Path, python: Path, show: bool) -> None:
    probe = CrewProbe(root, python, show)
    await probe.start()
    inputs = deque(maxlen=512)
    receive = probe.service.core.receive
    def traced_receive(session, frame):
        if frame.type == 'key':
            inputs.append({'session': session.id, 'tick': probe.service.clock.now_tick(), 'key': frame.data['k']})
        receive(session, frame)
    probe.service.core.receive = traced_receive
    try:
        results = [await run_size(probe, *size) for size in ((80, 24), (132, 50))]
        assert not probe.errors and probe.service.failure is None
        (root/'s22-results.json').write_text(json.dumps({'passed': True, 'runs': results,
            'transport': 'NetBBS Telnet -> registered native stdio',
            'fixtures': ['grades five/seven', 'one-HP attack-delayed maintenance drone',
                         'one direct legal drone hit to isolate the five-second down window']}, indent=2)+'\n', encoding='utf-8')
    except BaseException:
        (root/'input-tail.json').write_text(json.dumps(list(inputs), indent=2)+'\n', encoding='utf-8')
        (root/'failure-trace.txt').write_text(traceback.format_exc(), encoding='utf-8')
        raise
    finally:
        await probe.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--door-python', type=Path, required=True)
    parser.add_argument('--show', action='store_true')
    args = parser.parse_args()
    asyncio.run(accept(args.root, args.door_python, args.show))
