"""Exercise the real probe helpers without importing/running a NetBBS node."""

import ast
import asyncio
from collections import deque
from pathlib import Path
from types import SimpleNamespace as NS
from typing import Any

import pytest


def helpers(**dependencies: Any) -> type:
    # The script's top-level imports require NetBBS. Compile only its actual
    # navigation methods so root tests remain stdlib-only and socket-free.
    path = Path(__file__).resolve().parents[2]/'scripts/accept_s10_netbbs.py'
    source = ast.parse(path.read_text(encoding='utf-8'))
    owner = next(n for n in source.body if isinstance(n, ast.ClassDef) and n.name == 'NativeProbe')
    methods = [n for n in owner.body if isinstance(n, ast.AsyncFunctionDef) and n.name in {'walk', 'travel'}]
    module = ast.parse('from __future__ import annotations\nclass Probe: pass\n')
    module.body[1].body = methods
    module.body.append(next(n for n in source.body if isinstance(n, ast.AsyncFunctionDef)
                            and n.name == 's10_tram_evacuation'))
    scope = {'deque': deque, **dependencies}
    exec(compile(ast.fix_missing_locations(module), str(path), 'exec'), scope)
    scope['Probe'].s10_tram_evacuation = scope['s10_tram_evacuation']
    return scope['Probe']


def test_walker_reselects_live_goal_after_each_real_key() -> None:
    actor = NS(position=(0, 0), cooldowns={})
    avatar = NS(actor=actor, zone='street')
    zone = NS(id='street', actors={'caller': actor},
              template=NS(meta=NS(exits=[])),
              passable=lambda p: 0 <= p[0] <= 3 and 0 <= p[1] <= 2)
    destination, keys = [(3, 0)], []

    async def write(key: bytes) -> None:
        keys.append(key)
        dx, dy = {b'\x1b[C': (1, 0), b'\x1b[D': (-1, 0),
                  b'\x1b[B': (0, 1), b'\x1b[A': (0, -1)}[key]
        actor.position = actor.position[0]+dx, actor.position[1]+dy
        destination[0] = (1, 2)  # The target wanders after the first key.

    async def wait(condition: Any, timeout: float = 10) -> None:
        assert condition()

    probe = helpers(asyncio=asyncio, time=NS(monotonic=lambda: 0), wait=wait)()
    probe.service = NS(world=NS(zones={'street': zone}), clock=NS(now_tick=lambda: 0))
    caller = NS(avatar=avatar, caller=NS(write=write))
    asyncio.run(probe.walk(caller, lambda: destination[0]))
    assert actor.position == (1, 2)
    assert keys == [b'\x1b[C', b'\x1b[B', b'\x1b[B']
    keys.clear()
    asyncio.run(probe.walk(caller, (3, 2)))
    assert actor.position == (3, 2)  # Existing fixed goals stay exact.
    assert keys == [b'\x1b[C', b'\x1b[C']


def test_missing_live_goal_does_not_restart_the_120_second_bound() -> None:
    readings = iter((0, 0, 121))

    async def sleep(delay: float) -> None:
        pass

    probe = helpers(asyncio=NS(sleep=sleep), time=NS(monotonic=lambda: next(readings)))()
    probe.service = NS(world=NS(zones={'street': NS(id='street')}))
    caller = NS(avatar=NS(zone='street', actor=NS(position=(0, 0))))
    with pytest.raises(AssertionError, match='walk timeout'):
        asyncio.run(probe.walk(caller, lambda: None))


@pytest.mark.parametrize('valid_focus', [True, False])
def test_travel_waits_for_arrival_ack_then_asserts_focus_without_waiting_for_a_talker(valid_focus: bool) -> None:
    actor, session = NS(id='avatar', position=(0, 0)), NS(id='caller', ack_revision=1, view_revision=2)
    avatar = NS(actor=actor, zone='street')
    exit_ = NS(id='to-halo', tile=(2, 2), target_zone='halo')
    visible_actor = {'id': actor.id, 'x': 0, 'y': 0}
    view = NS(previous={'kind': 'zone', 'body': {'me': {'zone': 'street'}, 'actors': [visible_actor],
                                              'focus': {'id': 'regular', 'verb': 'talk to'}}})
    keys, checks = [], []

    async def walk(caller: Any, target: tuple[int, int]) -> None:
        assert target == exit_.tile
        actor.position = target

    async def wait(condition: Any, timeout: float = 10) -> None:
        if not checks:
            checks.append(condition())  # The previous view is unacknowledged.
            session.ack_revision = 2
            checks.append(condition())  # An old, acked pose is still stale.
            visible_actor.update(x=exit_.tile[0], y=exit_.tile[1])
            if valid_focus:
                view.previous['body']['focus'] = {'id': exit_.id, 'verb': 'go to'}
            checks.append(condition())
        assert condition()

    async def write(key: bytes) -> None:
        assert checks == [False, False, True]
        keys.append(key)
        avatar.zone = 'halo'

    probe = helpers(asyncio=asyncio, wait=wait)()
    probe.walk = walk
    probe.game = NS(sim=NS(views={session.id: view}))
    probe.service = NS(world=NS(zones={
        'street': NS(template=NS(meta=NS(exits=[exit_]))),
        'halo': NS(template=NS(meta=NS(name='The Tin Halo')))}))
    caller = NS(avatar=avatar, session=session, caller=NS(
        write=write, screen=NS(screen_text=lambda: 'The Tin Halo\n')))
    if valid_focus:
        asyncio.run(probe.travel(caller, 'halo'))
        assert keys == [b'e']
    else:
        # S39 makes a talker focus here a bug, not a reason to wait/retry.
        with pytest.raises(AssertionError):
            asyncio.run(probe.travel(caller, 'halo'))
        assert keys == []


@pytest.mark.parametrize('failure', [None, 'walk-recovery', 'boarding-down', 'ride-down', 'curfew-refusal'])
def test_s10_tram_waits_for_scheduled_arrival_and_keeps_winner_death_blocking(failure: str | None) -> None:
    from blacksite.server.world.exits import MAX_HOLD_SECONDS

    actor = NS(position=(27, 25), stance='normal', health=18, marked=True)
    avatar = NS(actor=actor, zone='clinic', travel=None)
    session = NS(id='winner', ack_revision=1, view_revision=1)
    exit_ = NS(id='to-tram', kind='tram', tile=(3, 31), target_zone='core-tram-hub')
    view = NS(previous={'body': {'focus': {'id': exit_.id, 'verb': 'go to'}}})
    keys, onward, ride_allowances, reports = [], [], [], []
    now = [100.0]

    async def walk(caller: Any, tile: tuple[int, int]) -> None:
        assert tile == exit_.tile
        actor.position = tile
        if failure == 'walk-recovery':
            avatar.zone = 'wake-hall'  # Alive after a second death still fails.

    async def write(key: bytes) -> None:
        keys.append(key)
        if failure != 'curfew-refusal':
            avatar.travel = NS(exit=exit_, departure=190.0, arrival=200.0)

    async def wait(condition: Any, timeout: float = 10) -> None:
        if failure == 'boarding-down' and not keys:
            actor.stance = 'down'
        if failure == 'ride-down' and avatar.travel is not None:
            actor.stance = 'dead'
        if condition():
            return
        if failure == 'curfew-refusal':
            raise TimeoutError('Curfew refuses boarding')
        ride_allowances.append(timeout)
        # A scheduled 90-second wait, ride, and later permitted hold must fit.
        assert timeout >= 100 + MAX_HOLD_SECONDS
        now[0] = 200 + MAX_HOLD_SECONDS
        avatar.zone, avatar.travel = 'core-tram-hub', None
        assert condition()

    async def travel(caller: Any, destination: str) -> None:
        assert avatar.zone == 'core-tram-hub'
        onward.append(destination)
        avatar.zone = destination

    probe = helpers(wait=wait, MAX_HOLD_SECONDS=MAX_HOLD_SECONDS)()
    probe.walk, probe.travel, probe.report = walk, travel, reports.append
    probe.combat = NS(now=lambda: now[0])
    probe.game = NS(sim=NS(views={session.id: view}))
    probe.service = NS(world=NS(zones={'clinic': NS(template=NS(meta=NS(exits=[exit_])))}))
    caller = NS(avatar=avatar, session=session, caller=NS(write=write))
    if failure:
        expected = TimeoutError if failure == 'curfew-refusal' else AssertionError
        with pytest.raises(expected):
            asyncio.run(probe.s10_tram_evacuation(caller))
        assert onward == []
        assert len(keys) <= 1  # No retry, resurrection or alternative event state.
    else:
        asyncio.run(probe.s10_tram_evacuation(caller))
        assert keys == [b'e'] and onward == ['core-plaza']
        assert ride_allowances and reports
        assert actor.health == 18 and actor.marked
