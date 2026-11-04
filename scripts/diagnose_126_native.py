"""Observe the unchanged P4/S19 probes; never supply acceptance or approvals."""

import argparse
import asyncio
from collections import deque
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

import accept_p4_netbbs as p4
import accept_s19_netbbs as s19
from accept_s10_netbbs import NativeProbe
from blacksite.server.sessions import Session

BASE = 'fe4dcf1a841c1b29f833389beea2f6238e58f8b8'
SOURCE = 'e6940dd7a51003850b4f0478b3cab2128a5d97cf'
ROOT = Path(__file__).resolve().parents[1]
original_start = NativeProbe.start
original_close = NativeProbe.close
original_approach = p4.approach
original_publish = Session.publish_view
view_history: dict[str, dict[int, dict[str, Any]]] = {}


def actor_state(actor: Any) -> dict[str, Any]:
    return {'id': actor.id, 'zone': actor.zone, 'position': actor.position,
            'stance': actor.stance, 'health': actor.health,
            'move_cooldown': actor.cooldowns.get('move'),
            'template': actor.behaviour.get('template')}


async def start(probe: NativeProbe) -> None:
    probe.diagnostic_approaches = []
    probe.diagnostic_inputs = deque(maxlen=512)
    await original_start(probe)
    core = probe.service.core
    receive, resolve = core.receive, core.resolve_interaction
    pending: dict[int, int] = {}
    sequence = 0

    def published(session: Any, full: Any, delta: Any, tick: int) -> bool:
        result = original_publish(session, full, delta, tick)
        if result:
            history = view_history.setdefault(session.id, {})
            body = full.data['body']
            history[session.view_revision] = {
                'revision': session.view_revision, 'tick': tick,
                'focus': body.get('focus'), 'jack_focus': body.get('jack_focus')}
            while len(history) > 512:
                del history[next(iter(history))]
        return result

    def context(session: Any, frame: Any, phase: str) -> dict[str, Any]:
        avatar = probe.game.sim.avatars.get(session.user_id)
        return {'phase': phase, 'at': time.monotonic(),
                'tick': probe.service.clock.now_tick(), 'data': dict(frame.data),
                'ack_revision': session.ack_revision, 'view_revision': session.view_revision,
                'actor': actor_state(avatar.actor) if avatar else None,
                'acked_view': view_history.get(session.id, {}).get(session.ack_revision),
                'latest_view': view_history.get(session.id, {}).get(session.view_revision)}

    def received(session: Any, frame: Any) -> None:
        nonlocal sequence
        if frame.type == 'key' and frame.data.get('k') in ('e', 'E'):
            sequence += 1
            pending[id(frame)] = sequence
            row = context(session, frame, 'received')
            row['sequence'] = sequence
            probe.diagnostic_inputs.append(row)
        receive(session, frame)

    def resolved(session: Any, frame: Any, routes: Any = None) -> Any:
        selected = resolve(session, frame, routes)
        if (frame.type == 'key' and frame.data.get('k') in ('e', 'E')
                and sys._getframe(1).f_code.co_name == '_echo'):
            row = context(session, frame, 'resolved')
            row['sequence'] = pending.pop(id(frame), None)
            row['selected'] = None if selected is None else {
                'route': selected.route.name,
                'focus': selected.choice.focus.record() if selected.choice.focus else None,
                'tile': selected.choice.tile, 'actor_id': selected.choice.actor_id,
                'kind': selected.choice.kind}
            probe.diagnostic_inputs.append(row)
        return selected

    core.receive, core.resolve_interaction = received, resolved
    Session.publish_view = published


async def approach(probe: NativeProbe, caller: Any, target: Any,
                   *, hostile_tile: bool = True) -> None:
    started = time.monotonic()
    row = {'start': {'caller': actor_state(caller.avatar.actor), 'target': actor_state(target)},
           'hostile_tile': hostile_tile}
    try:
        await original_approach(probe, caller, target, hostile_tile=hostile_tile)
        row['outcome'] = 'returned'
    except BaseException as error:
        row['outcome'] = type(error).__name__
        raise
    finally:
        actor = caller.avatar.actor
        row['elapsed'] = time.monotonic()-started
        row['end'] = {'caller': actor_state(actor), 'target': actor_state(target)}
        row['distance_squared'] = (actor.x-target.x)**2+(actor.y-target.y)**2
        row['caller_sees_target'] = probe.combat.visible(actor, target)
        row['target_sees_caller'] = probe.combat.visible(target, actor)
        row['target_still_registered'] = probe.service.world.actors.get(target.id) is target
        row['tick'] = probe.service.clock.now_tick()
        row['ack_revision'] = caller.session.ack_revision
        row['view_revision'] = caller.session.view_revision
        probe.diagnostic_approaches.append(row)


async def close(probe: NativeProbe) -> None:
    try:
        await original_close(probe)
    finally:
        Session.publish_view = original_publish
        view_history.clear()
        report = {'diagnostic_only': True, 'approval': False, 'base': BASE,
                  'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT,
                                                  text=True).strip(),
                  'source_tree': SOURCE, 'approaches': probe.diagnostic_approaches,
                  'interactions': list(probe.diagnostic_inputs),
                  'probe_changes': 'observational wrappers only; no keys/deadlines/assertions changed'}
        (probe.root/'diagnostics.json').write_text(json.dumps(report, indent=2)+'\n',
                                                  encoding='utf-8', newline='\n')


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--door-python', type=Path, required=True)
    parser.add_argument('--scenario', choices=('p4', 'network'), required=True)
    parser.add_argument('--size', choices=('80x24', '132x50'), required=True)
    args = parser.parse_args()
    source = subprocess.check_output(['git', 'rev-parse', 'HEAD:src/blacksite'],
                                     cwd=ROOT, text=True).strip()
    assert source == SOURCE
    for name in ('accept_p4_netbbs.py', 'accept_s10_netbbs.py',
                 'accept_s11_netbbs.py', 'accept_s19_netbbs.py'):
        subprocess.check_call(['git', 'diff', '--exit-code', BASE, 'HEAD', '--', 'scripts/'+name], cwd=ROOT)
    NativeProbe.start, NativeProbe.close, p4.approach = start, close, approach
    sizes = (tuple(map(int, args.size.split('x'))),)
    if args.scenario == 'p4':
        await p4.accept(args.root, args.door_python, False, sizes)
    else:
        await s19.accept(args.root, args.door_python, False, sizes, (True,), False)


if __name__ == '__main__':
    asyncio.run(main())
