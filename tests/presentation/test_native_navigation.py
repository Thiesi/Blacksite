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
    scope = {'deque': deque, **dependencies}
    exec(compile(ast.fix_missing_locations(module), str(path), 'exec'), scope)
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


@pytest.mark.parametrize('door_arrives', [True, False])
def test_travel_waits_for_acked_door_focus_before_one_e(door_arrives: bool) -> None:
    actor, session = NS(position=(0, 0)), NS(id='caller', ack_revision=1, view_revision=1)
    avatar = NS(actor=actor, zone='street')
    exit_ = NS(id='to-halo', tile=(2, 2), target_zone='halo')
    view = NS(previous={'body': {'focus': {'id': 'regular', 'verb': 'talk to'}}})
    keys, checks = [], []

    async def walk(caller: Any, target: tuple[int, int]) -> None:
        assert target == exit_.tile
        actor.position = target

    async def wait(condition: Any, timeout: float = 10) -> None:
        if not checks:
            checks.append(condition())  # Acked talker must not receive E.
            view.previous['body']['focus'] = {'id': exit_.id, 'verb': 'go to'}
            session.view_revision = 2
            checks.append(condition())  # Unacked door must not receive E.
            if not door_arrives:
                raise TimeoutError('no acknowledged door')
            session.ack_revision = 2
            checks.append(condition())
        assert condition()

    async def write(key: bytes) -> None:
        assert checks == [False, False, True]
        keys.append(key)
        avatar.zone = 'halo'

    probe = helpers(wait=wait)()
    probe.walk = walk
    probe.game = NS(sim=NS(views={session.id: view}))
    probe.service = NS(world=NS(zones={
        'street': NS(template=NS(meta=NS(exits=[exit_]))),
        'halo': NS(template=NS(meta=NS(name='The Tin Halo')))}))
    caller = NS(avatar=avatar, session=session, caller=NS(
        write=write, screen=NS(screen_text=lambda: 'The Tin Halo\n')))
    if door_arrives:
        asyncio.run(probe.travel(caller, 'halo'))
        assert keys == [b'e']
    else:
        with pytest.raises(TimeoutError, match='no acknowledged door'):
            asyncio.run(probe.travel(caller, 'halo'))
        assert keys == []
