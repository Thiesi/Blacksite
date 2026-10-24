"""Architecture 15.2: ended event slots retire with their source receipt."""

from copy import deepcopy
from dataclasses import replace
from typing import Any
from pathlib import Path
import json
import sqlite3
import pytest

from blacksite.content.schema import Spawner
from tests.harness import HeadlessServer
from tests.server.test_event_convoy import base_content, convoy_game
from blacksite.server.storage.db import Storage


def cancel(game: Any, pid: str) -> None:
    game.core.events.admin('event.cancel',{'plan':pid},lambda result:None)


def test_arch_15_2_slot_retirement_rolls_back_and_preserves_static_spawners(convoy_game: tuple[Any, ...]) -> None:
    game,callers,players,actor,pid,points = convoy_game
    spawners = game.core.npcs.spawners
    key = actor.behaviour['slot']
    zone = game.core.world.zones[actor.zone]
    static = Spawner('event:ordinary','npc-courier',1,100,points[0])
    zone.template = replace(zone.template,meta=replace(zone.template.meta,spawners=(*zone.template.meta.spawners,static)))
    static_key = f'{zone.id}:{static.id}:0'
    spawners.slots[static_key] = {'until':game.core.events.now()+100}
    original = deepcopy(spawners.record())
    cancel(game,pid)
    assert key in spawners.slots and actor.id in game.core.world.actors
    game.commit_commerce(error=True)
    assert spawners.record() == original
    assert game.core.events.scheduler.plans[pid].state == 'active'
    cancel(game,pid)
    receipts = game.commit_commerce()
    assert key not in spawners.slots and key not in receipts[0]['npc_state']['slots']
    assert static_key in spawners.slots and static_key in receipts[0]['npc_state']['slots']
    assert spawners.serial == original['serial']
    assert actor.id not in game.core.world.actors


def test_arch_15_2_retirement_prepare_keeps_late_ordinary_spawn_and_serial(convoy_game: tuple[Any, ...]) -> None:
    game,callers,players,actor,pid,points = convoy_game
    spawners = game.core.npcs.spawners
    key = actor.behaviour['slot']
    cancel(game,pid)
    # Ordinary spawners can advance while a transfer awaits I/O. Snapshot
    # at prepare, and apply a removal delta rather than replace live slots.
    spawners.serial += 1
    spawners.slots['fixture:late-static:0'] = {'until':12345,'actor':'fixture:late-body'}
    serial = spawners.serial
    receipts = game.commit_commerce()
    state = receipts[0]['npc_state']
    assert state['serial'] == serial == spawners.serial
    assert state['slots']['fixture:late-static:0'] == spawners.slots['fixture:late-static:0']
    assert key not in state['slots'] and key not in spawners.slots


def test_arch_6_2_npc_death_prepare_also_preserves_late_spawn_serial(convoy_game: tuple[Any, ...]) -> None:
    game,callers,players,actor,pid,points = convoy_game
    actor.health,actor.stance = 0,'dead'
    game.core.npcs.died(game.core.world.actors[players[0].id],actor)
    spawners = game.core.npcs.spawners
    spawners.serial += 1
    spawners.slots['fixture:late-static:0'] = {'until':0,'actor':'fixture:late-body'}
    serial = spawners.serial
    receipts = game.commit_commerce()
    assert receipts[0]['npc_state']['serial'] == serial == spawners.serial
    assert receipts[0]['npc_state']['slots']['fixture:late-static:0'] == spawners.slots['fixture:late-static:0']


def test_arch_15_2_pending_death_keeps_its_slot_then_retires_without_another_roll(convoy_game: tuple[Any, ...]) -> None:
    game,callers,players,actor,pid,points = convoy_game
    spawners = game.core.npcs.spawners
    key = actor.behaviour['slot']
    cancel(game,pid)  # Pending close; the death queues behind it.
    actor.health,actor.stance = 0,'dead'
    game.core.npcs.died(game.core.world.actors[players[0].id],actor)
    assert actor.id in game.core.npcs.pending_deaths
    receipts = game.commit_commerce()
    assert key in receipts[0]['npc_state']['slots']
    assert actor.id not in game.core.npcs.pending_deaths and actor.id not in game.core.world.actors
    last_roll = game.core.events.scheduler.last_roll
    game.step(10)
    cleanup = game.commit_commerce()
    assert key not in spawners.slots and any('npc_state' in effect for effect in cleanup)
    assert game.core.events.scheduler.last_roll == last_roll


def test_arch_15_2_restart_removes_thousand_retired_slots_and_keeps_active_source_serial(convoy_game: tuple[Any, ...]) -> None:
    game,callers,players,actor,pid,points = convoy_game
    live_key = actor.behaviour['slot']
    state = deepcopy(game.core.npcs.spawners.record())
    state['serial'] = 5000
    state['slots']['fixture:static:0'] = {'until':10000}
    for index in range(1000):
        state['slots'][f'{actor.zone}:event:old-origin:event:{index}:0:0'] = {'until':0}
    saved = {'events':game.core.events.scheduler.record(),'npcs':state,
        'players':[player.record() for player in players],
        'items':[item.record() for item in game.core.commerce.items.values()],
        'identities':deepcopy(game.core.characters.identities),'contracts':game.core.contracts.record()}
    restored = HeadlessServer(game.core.loop.content,character_state=saved,clock=game.clock)
    spawners = restored.core.npcs.spawners
    assert live_key in spawners.slots and 'fixture:static:0' in spawners.slots
    assert not any(':event:old-origin:' in key for key in spawners.slots)
    assert spawners.serial == 5000
    restored.step()
    restored.commit_commerce()
    assert spawners.serial > 5000
    assert any(body.behaviour.get('convoy') == pid for body in restored.core.world.actors.values())


def test_arch_6_2_sqlite_retirement_and_event_close_commit_or_roll_back_together(convoy_game: tuple[Any, ...], scratch_dir: Path) -> None:
    game,callers,players,actor,pid,points = convoy_game
    original = deepcopy(game.core.npcs.spawners.record())
    original_events = game.core.events.scheduler.record()
    cancel(game,pid)
    effect = game.core.commerce.outbox[0]
    prepared = game.core.commerce.prepare(effect)
    key = actor.behaviour['slot']
    assert key not in prepared['npc_state']['slots']
    store = Storage(scratch_dir/'slot-retirement.db',game.clock)
    try:
        store.mark_dirty('meta','npc_state',original)
        store.mark_dirty('meta','events_state',original_events)
        store.flush_now()
        store.db.execute("CREATE TRIGGER fail_retirement BEFORE INSERT ON audit BEGIN SELECT RAISE(ABORT,'injected retirement failure'); END")
        with pytest.raises(sqlite3.IntegrityError,match='injected retirement failure'):
            store.commerce_write(prepared)
        assert store.meta('npc_state') == original
        assert store.meta('events_state') == json.loads(json.dumps(original_events))
        assert key in game.core.npcs.spawners.slots
        store.db.execute('DROP TRIGGER fail_retirement')
        store.commerce_write(prepared)
        assert key not in store.meta('npc_state')['slots']
        assert store.meta('events_state')['plans'][0]['state'] == 'cancelled'
        game.commit_commerce()
        assert key not in game.core.npcs.spawners.slots
    finally:
        store.close()
