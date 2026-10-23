"""S14 acceptance through real NetBBS native stdio at both terminal sizes.

Training and Silt use fresh characters, ordinary travel and real keys,
without money, item, skill, grade or placement fixtures. Danger and Gate
Nine explicitly label content, trace-boundary, program-loan and committed
active-contract fixtures. Burn adds an explicit grade/XP fixture for S16. S14
now verifies S15 physical effects on the labelled control fixture.
"""

import argparse
import asyncio
import json
import time
from pathlib import Path
from math import ceil
from typing import Any
from collections.abc import Callable

from accept_s10_netbbs import Connection, NativeProbe, wait
from accept_s13_netbbs import lat_walk
from blacksite.server.lattice.silt import generate
from blacksite import content as content_package
from blacksite.server.rules import character


async def menu(probe: NativeProbe, connection: Connection, row_id: str, *, changes: bool = True) -> None:
    encounters = probe.service.core.lattice.encounters
    await wait(lambda: 'Choice' in connection.caller.screen.screen_text()
        and connection.session.ack_revision == connection.session.view_revision)
    screen = encounters.menus[connection.session.id]
    presence = probe.service.core.lattice.presences[connection.session.player_id]
    rows = encounters.rows(presence, screen)
    desired = next(i for i, row in enumerate(rows) if row['id'] == row_id)
    while screen.cursor != desired:
        old = screen.cursor
        await connection.caller.write(b'\x1b[B' if desired > old else b'\x1b[A')
        await wait(lambda: screen.cursor != old)
    state = screen.kind, screen.slot, screen.target
    for _ in range(6):
        await wait(lambda: connection.session.ack_revision == connection.session.view_revision)
        await connection.caller.write(b'\r')
        if not changes:
            return
        # Timed warnings may publish a newer revision while Enter travels.
        # Retry the same visible choice if the server rejected that revision.
        await asyncio.sleep(.2)
        if encounters.menus.get(connection.session.id) is not screen or (screen.kind, screen.slot, screen.target) != state:
            return


async def program(probe: NativeProbe, connection: Connection, slot: int,
                  completed: Callable[[], bool]) -> None:
    lattice = probe.service.core.lattice
    player = probe.game.players[connection.session.player_id]
    await wait(lambda: 'INTEGRITY' in connection.caller.screen.screen_text())
    async with asyncio.timeout(20):
        while not completed():
            assert player.id in lattice.presences, 'The run ended before the program completed.'
            presence = lattice.presences[player.id]
            pid = presence.rig[slot-1]
            ready = player.progress.get('lattice_cooldowns', {}).get(pid, 0) <= probe.service.clock.now_utc().timestamp()
            if presence.cast is None and ready:
                tick = probe.service.clock.now_tick()
                await connection.caller.write(str(slot).encode('ascii'))
                await wait(lambda: presence.cast is not None or completed() or probe.service.clock.now_tick() > tick+1)
            await asyncio.sleep(.03)


async def training(probe: NativeProbe, width: int, height: int) -> dict[str, Any]:
    connection = await probe.open(width, height, 'S14Ghost', 1, True)
    lattice = probe.service.core.lattice
    encounters = lattice.encounters
    player = probe.game.players[connection.session.player_id]
    assert player.archetype == 'ghost' and player.chits_hand == 200 and player.xp == 0
    await probe.walk(connection, (21, 14))
    await connection.caller.write(b'b')
    await wait(lambda: player.progress.get('wake_combat') == 'skipped')
    terminal = next(obj for obj in probe.service.world.zones[connection.avatar.zone].objects.values()
                    if obj.spec.params.get('training_core') == 'lat-wake-hall')
    # Adjacent floor belongs to the outfitter's spawn region. The actual
    # terminal is reserved by Spawners and stays available for the caller.
    await probe.walk(connection, terminal.spec.tile)
    body = connection.avatar.actor
    original = body.position
    health = body.health
    await connection.caller.write(b'j')
    await wait(lambda: player.id in lattice.presences)
    presence = lattice.presences[player.id]
    await wait(lambda: 'INTEGRITY' in connection.caller.screen.screen_text())
    await connection.caller.write(b'e')
    await wait(lambda: connection.session.id in encounters.menus)
    await menu(probe, connection, 'enter:lat-wake-hall')
    await wait(lambda: presence.core == 'lat-wake-hall')
    core_started = time.monotonic()
    await wait(lambda: 'Tripwire' in connection.caller.screen.screen_text())
    defender = encounters.defenders(presence)[0]
    assert defender.integrity == 10 and defender.attack == 5
    probe.save(connection, f's14-training-warning-{width}x{height}')
    await connection.caller.write(b'e')
    await wait(lambda: connection.session.id in encounters.menus)
    await menu(probe, connection, 'ice:'+defender.id)
    await wait(lambda: presence.target == defender.id and connection.session.id not in encounters.menus)
    await program(probe, connection, 2, lambda: presence.effects.shield is not None)
    assert 0 < presence.effects.shield.budget <= 15
    await program(probe, connection, 1, lambda: not defender.alive)
    await connection.caller.write(b'e')
    await wait(lambda: connection.session.id in encounters.menus)
    rows = encounters.rows(presence, encounters.menus[connection.session.id])
    lift = next(row['id'] for row in rows if row['id'].startswith('lift:decant-record:'))
    await menu(probe, connection, lift)
    await wait(lambda: 'lattice-training-record' in player.progress.get('lattice_records', {}))
    await connection.caller.write(b'e')
    await wait(lambda: connection.session.id in encounters.menus)
    await menu(probe, connection, 'read:lattice-training-record')
    await wait(lambda: 'YOUR DECANT RECORD' in connection.caller.screen.screen_text())
    assert 'lease' in connection.caller.screen.screen_text()
    probe.save(connection, f's14-training-record-{width}x{height}')
    assert presence.trace == 0 and body.health == health and body.position == original
    assert player.chits_hand == 200 and player.xp == 0 and player.clone_debt == 0
    await connection.caller.write(b'b')
    await wait(lambda: connection.session.id not in encounters.menus)
    await wait(lambda: 'WAKE HALL / CORE' in connection.caller.screen.screen_text().splitlines()[0])
    await connection.caller.write(b'b')
    await wait(lambda: presence.instance is None)
    await connection.caller.write(b'j')
    await wait(lambda: player.id not in lattice.presences and body.stance == 'normal')
    await wait(lambda: 'Wake Hall' in connection.caller.screen.screen_text().splitlines()[0])
    saved = probe.service.storage.character_state()
    durable = next(p for p in saved['players'] if p['id'] == player.id)
    assert 'lattice-training-record' in durable['progress']['lattice_records']
    result = {'stage': 'training', 'width': width, 'height': height,
        'transport': 'NetBBS Telnet -> native stdio door', 'tier': connection.session.caps['tier'],
        'archetype': player.archetype, 'chits': player.chits_hand, 'xp': player.xp,
        'body_hp': body.health, 'core_seconds': round(time.monotonic()-core_started,2), 'source_generation': next(v['generation'] for key, v in saved['lattice']['sources'].items() if 'decant-record' in key),
        'placement_fixture': False, 'funding_fixture': False, 'item_fixture': False,
        'grade_fixture': False, 'passed': True}
    probe.report(f'PASS S14 training {width}x{height}: fresh Ghost, inspect/Pick/Umbrella, atomic lift/read, zero trace/body harm/rewards, safe leave')
    await probe.leave(connection, f's14-training-return-{width}x{height}')
    return result


async def choose(probe: NativeProbe, connection: Connection, row: str, *, closes: bool = True) -> None:
    encounters = probe.service.core.lattice.encounters
    await wait(lambda: connection.session.id not in encounters.menus)
    await wait(lambda: any(label in connection.caller.screen.screen_text().splitlines()[0] for label in ('SILT /', '/ CORE', '/ LATTICE')))
    await connection.caller.write(b'e')
    await wait(lambda: connection.session.id in encounters.menus)
    await menu(probe, connection, row, changes=closes)
    if closes:
        await wait(lambda: connection.session.id not in encounters.menus)


async def room_walk(probe: NativeProbe, connection: Connection, target: str) -> None:
    lattice = probe.service.core.lattice
    presence = lattice.presences[connection.session.player_id]
    encounters = lattice.encounters
    async with asyncio.timeout(40):
        while presence.room != target:
            graph = encounters.core(presence).graph
            if presence.descent:
                route = graph.band.route(presence.room, target,
                    presence.found_silt.get(presence.instance, set()))
            else:
                route = graph.route(presence.room, target)
            assert len(route) >= 2, ('No known route', presence.room, target)
            source, other = graph.room(presence.room), graph.room(route[1])
            dx, dy = other.pos[0]-source.pos[0], other.pos[1]-source.pos[1]
            key = b'\x1b[C' if dx > 0 else b'\x1b[D' if dx < 0 else b'\x1b[B' if dy > 0 else b'\x1b[A'
            before = presence.room
            await wait(lambda: encounters.idle(presence))
            await wait(lambda: any(label in connection.caller.screen.screen_text().splitlines()[0] for label in ('SILT /', '/ CORE')))
            await connection.caller.write(key)
            await wait(lambda: presence.room != before)


async def silt(probe: NativeProbe, width: int, height: int) -> dict[str, Any]:
    connection = await probe.open(width, height, 'S14Silt', 2, True)
    lattice = probe.service.core.lattice
    encounters = lattice.encounters
    player = probe.game.players[connection.session.player_id]
    assert player.archetype == 'cantor' and player.skills['listening'] < 20
    await probe.walk(connection, (21, 14))
    await connection.caller.write(b'b')
    await wait(lambda: player.progress.get('wake_combat') == 'skipped')
    await probe.travel(connection, 'vatside-clinics')
    await probe.travel(connection, 'core-plaza')
    await probe.walk(connection, (30, 5))
    await connection.caller.write(b'e')
    await wait(lambda: player.id in lattice.presences)
    presence = lattice.presences[player.id]
    assert len(presence.rig) == 3 and not lattice.content.starts[player.archetype].rig_slots
    sector = lattice.sectors.records['lat-core']
    uplink = next(c for c in sector.cells if c.uplink and c.uplink.sector == 'lat-chapel-ward')
    await lat_walk(probe, connection, uplink.id)
    await connection.caller.write(b'e')
    await wait(lambda: presence.sector == 'lat-chapel-ward')
    entry = next(c for c in lattice.sectors.records[presence.sector].cells if c.kind == 'descent' and c.access_kind == 'public')
    await lat_walk(probe, connection, entry.id)
    await choose(probe, connection, 'descend')
    await wait(lambda: presence.descent is not None)
    await wait(lambda:not probe.commerce.pending and not probe.commerce.waiting)
    authored_xp = player.xp  # S16 pays the actual authored journey here.
    assert authored_xp > 0
    descent = encounters.descents[presence.descent]
    descent_started = time.monotonic()
    replay = generate('different-origin', lattice.season, presence.sector, descent.nonce, lattice.content.silt)
    assert replay.seed == descent.seed and replay.bands == descent.bands
    assert descent.nonce == 1, 'Use a fresh isolated world for reproducible acceptance.'
    band = encounters.core(presence).graph.band
    hidden = next(c for c in band.cells if c.hidden and any(not band.cell(n).hidden for n in c.neighbours))
    visible = next(n for n in hidden.neighbours if not band.cell(n).hidden)
    await room_walk(probe, connection, visible)
    assert hidden.id not in presence.found_silt[presence.instance]
    await choose(probe, connection, 'survey')
    await wait(lambda: presence.procedure is None)
    assert hidden.id not in presence.found_silt[presence.instance]
    await wait(lambda: 'Hidden signal directions:' in connection.caller.screen.screen_text())
    probe.save(connection, f's14-silt-survey-{width}x{height}')
    probe.report(f'PASS S14 Silt survey {width}x{height}: fresh Cantor, public loan rig, real public route, low Listening gives hidden branch direction without leaking its cell')
    # The visible continuation is chosen without opening optional danger rooms.
    for depth in range(2):
        graph = encounters.core(presence).graph
        sink = next(cid for cid in graph.band.sinks if not graph.band.cell(cid).hidden)
        await room_walk(probe, connection, sink)
        await choose(probe, connection, 'descend')
        await wait(lambda: presence.depth == depth+1)
    graph = encounters.core(presence).graph
    signal = next(i for i in encounters.core(presence).ice.values() if i.template.class_ == 'chorister')
    await room_walk(probe, connection, signal.location[1])
    await wait(lambda: signal.signal_phase(probe.service.clock.now_tick())[0] == 'listening'
        and signal.signal_phase(probe.service.clock.now_tick())[1] >= 38
        and player.progress.get('lattice_cooldowns', {}).get('survey', 0) <= probe.service.clock.now_utc().timestamp(), 35)
    await choose(probe, connection, 'survey')
    await wait(lambda: presence.procedure is None)
    assert signal.id in presence.survey_records
    await wait(lambda: signal.signal_phase(probe.service.clock.now_tick())[0] == 'sampling'
        and signal.signal_phase(probe.service.clock.now_tick())[1] >= 38, 25)
    await choose(probe, connection, 'sample')
    await wait(lambda: signal.id in presence.sampled)
    assert presence.mapping_until > probe.service.clock.now_tick() and player.xp == authored_xp
    probe.save(connection, f's14-silt-sample-{width}x{height}')
    probe.report(f'PASS S14 Chorister {width}x{height}: visible listening -> survey -> sampling -> hold, no answer, no XP payout')
    sink = next(cid for cid in graph.band.sinks if graph.band.route(presence.room, cid))
    await room_walk(probe, connection, sink)
    await choose(probe, connection, 'descend')
    await wait(lambda: presence.depth == 3)
    sweeper = next(i for i in encounters.core(presence).ice.values() if i.template.class_ == 'sweeper')
    # For this public nonce, a safe side cell borders the warned patrol.
    # All moves still follow the generated links through real arrow keys.
    graph = encounters.core(presence).graph
    patrol = {location[1] for location in sweeper.patrol}
    side = next(cid for cid in graph.band.route(graph.band.riser, graph.band.sinks[1])
                if cid not in patrol and any(n in patrol for n in graph.room(cid).neighbours))
    await room_walk(probe, connection, side)
    async def evade() -> str:
        async with asyncio.timeout(60):
            while True:
                next_cell = sweeper.patrol[(sweeper.patrol_index+1) % len(sweeper.patrol)][1]
                if (not sweeper.sweep_occupies_until and next_cell in graph.room(side).neighbours
                        and sweeper.next_move-probe.service.clock.now_tick() >= 25):
                    await room_walk(probe, connection, next_cell)
                    assert 'SWEEP' in connection.caller.screen.screen_text()
                    probe.save(connection, f's14-silt-sweep-warning-{width}x{height}')
                    await room_walk(probe, connection, side)
                    await wait(lambda: sweeper.location[1] == next_cell, 15)
                    assert presence.room == side and presence.integrity > 0
                    return next_cell
                await asyncio.sleep(.03)
    swept = await evade()
    assert presence.trace == 0 and player.chits_hand == 200 and player.xp == authored_xp
    await connection.caller.write(b'j')
    await wait(lambda: player.id not in lattice.presences, 12)
    probe.report(f'PASS S14 Sweeper {width}x{height}: real move into warned cell then linked bypass before occupation; bounded jack-out')
    result = {'stage': 'silt', 'size': [width, height], 'seed': str(descent.seed),
        'nonce': descent.nonce, 'descent_seconds': round(time.monotonic()-descent_started,2), 'same_seed_graph_replay': True, 'public_loan': True,
        'survey_hidden_direction': True, 'chorister_sampled': True, 'evaded_sweep': swept,
        'placement_fixture': False, 'funding_fixture': False, 'item_fixture': False,
        'grade_fixture': False, 'passed': True}
    await probe.leave(connection, f's14-silt-return-{width}x{height}')
    return result


def scenario_content(probe: NativeProbe, stage: str) -> None:
    """Labelled, validated content.local fixtures; never edits shipped data."""
    source = Path(content_package.__file__).parent
    local = probe.service.install_dir/'content.local'
    def read(name: str) -> dict[str, Any]:
        return json.loads((source/name).read_text(encoding='utf-8'))
    def write(name: str, value: dict[str, Any]) -> None:
        target = local/name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(value, indent=2)+'\n', encoding='utf-8')
    if stage == 'danger':
        core = read('cores/lat-civic-ledger.json')
        core['name'] = 'S14 LABELLED NPC RISK FIXTURE'
        core['trace_policy'] = 'corporate'
        # Preserve the actual hub entrance/hardware. Isolate a touched Kiln
        # and the ordinary tier-three corporate Hound in this content fixture.
        core['tier'] = 3
        for room in core['rooms']:
            room['ice'] = ['ice_kiln'] if room['id'] == core['entry'] else []
        write('cores/lat-civic-ledger.json', core)
    elif stage.startswith('gate-'):
        bundle = read('bundles/s25-cores.json')
        bundle['members']['cores'].remove('lat-gatehouse-east')
        write('bundles/s25-cores.json', bundle)
        core = read('cores/lat-gatehouse-east.json')
        core['name'] = 'S14 LABELLED GATE NINE FIXTURE'
        core['hardware'] = [{'zone': 'vatside-clinics', 'tile': [35,20],
            'object_id': 'cold-chain-replacement-socket', 'label': 'S14 fixture socket'}]
        payload=next(room for room in core['rooms'] if room['id']=='service-latch')['data'][0]
        write('contracts.json',{'schema':1,'contracts':[{
            'id':'fixture-s14-gate-record','name':'S14 fixture mission receipt',
            'faction':'halvard','type':'hack','story':True,'crew_scaling':False,
            'reward':{'chits':[0,0],'xp':0,'standing':{}},
            'stages':[{'id':'copy','verb':'hack','input':'lift','completion':'lifted',
                'receipt_key':'fixture-s14-gate-record:copy',
                'target':{'kind':'core_room','core':core['id'],'room':'service-latch','data':payload['id']}}]}]})
        for room in core['rooms']:
            for control in room.get('controls', []):
                control['target'] = {'zone': 'core-plaza', 'object': 'civic-ledger-hall-doors'}
        write('cores/lat-gatehouse-east.json', core)
        sector = read('sectors/lat-core.json')
        cell = next(c for c in sector['cells'] if c['id'] == 'lat-core-c16')
        cell.update(kind='core_entrance', access='public', core_id=core['id'], label='S14 Gate Nine fixture entrance')
        write('sectors/lat-core.json', sector)
        sector = read('sectors/lat-tramyard.json')
        old = next(c for c in sector['cells'] if c.get('planned_core') == core['id'])
        old['kind'] = 'gated'
        old.pop('core_placeholder',None)
        old.pop('planned_core',None)
        write('sectors/lat-tramyard.json',sector)


async def hub(probe: NativeProbe, connection: Connection) -> None:
    player = probe.game.players[connection.session.player_id]
    await probe.walk(connection, (21,14))
    await connection.caller.write(b'b')
    await wait(lambda: player.progress.get('wake_combat') == 'skipped')
    await probe.travel(connection, 'vatside-clinics')
    await probe.travel(connection, 'core-plaza')


async def danger(probe: NativeProbe, width: int, height: int) -> dict[str, Any]:
    lattice = probe.service.core.lattice
    encounters = lattice.encounters
    outcomes = []
    for safe in (False, True):
        suffix = 'Safe' if safe else 'Unsafe'
        runner = await probe.open(width,height,'S14Risk'+suffix,1,True)
        observer = await probe.open(width,height,'S14Witness'+suffix,0)
        for connection in (runner,observer):
            await hub(probe,connection)
            if not safe:
                await probe.travel(connection,'vatside-clinics')
        if safe:
            await probe.walk(runner,(30,5))
            await probe.walk(observer,(31,6))
            await runner.caller.write(b'e')
        else:
            await probe.walk(runner,(25,25))
            await probe.walk(observer,(27,25))
            await runner.caller.write(b'j')
        player = probe.game.players[runner.session.player_id]
        await wait(lambda: player.id in lattice.presences)
        presence = lattice.presences[player.id]
        body = runner.avatar.actor
        original = body.position
        hp = body.health
        assert probe.service.world.zones[body.zone].allows_hostile(original) is (not safe)
        if presence.sector != 'lat-core':
            uplink = next(c for c in lattice.sectors.records[presence.sector].cells if c.uplink and c.uplink.sector == 'lat-core')
            await lat_walk(probe,runner,uplink.id)
            await runner.caller.write(b'e')
            await wait(lambda: presence.sector == 'lat-core')
        entry = next(c for c in lattice.sectors.records['lat-core'].cells if c.core_id == 'lat-civic-ledger')
        await lat_walk(probe,runner,entry.id)
        await choose(probe,runner,'enter:lat-civic-ledger',closes=False)
        await wait(lambda: any('Choose Enter with NPC risk' in row['text'] for row in runner.session.log_ring))
        await runner.caller.write(b'b')
        await wait(lambda: runner.session.id not in encounters.menus)
        assert presence.instance is None and body.health == hp
        await choose(probe,runner,'risk:lat-civic-ledger')
        await wait(lambda: presence.core == 'lat-civic-ledger')
        await wait(lambda: 'BLACK ICE / BODY RISK' in runner.caller.screen.screen_text())
        kiln = next(i for i in encounters.defenders(presence) if i.template.class_ == 'kiln')
        await choose(probe,runner,'ice:'+kiln.id)
        await probe.target(observer,body.id)
        await program(probe,runner,1,lambda: kiln.integrity < kiln.maximum)
        await wait(lambda: body.health < hp,7)
        after = body.health
        assert body.stance == 'jacked' and body.position == original and hp-after == 10
        await wait(lambda: 'Kiln hits you for 10' in runner.caller.screen.screen_text())
        await wait(lambda: f'{ceil(100*after/body.health_max)}%' in observer.caller.screen.screen_text())
        probe.save(runner,f's14-black-body-{suffix}-{width}x{height}')
        probe.save(observer,f's14-black-witness-{suffix}-{width}x{height}')
        await room_walk(probe,runner,'r-foyer')
        # Explicit threshold fixture: the actual next passive trace tick
        # crosses 100. Do not claim a real hundred-second accumulation.
        presence.trace = 99
        started = time.monotonic()
        await wait(lambda: any(i.target == player.id for i in encounters.hunters.values()),4)
        elapsed = round(time.monotonic()-started,2)
        hunter = next(i for i in encounters.hunters.values() if i.target == player.id)
        assert hunter.maximum == 80 and hunter.meat_damage == 0
        probe.save(runner,f's14-corporate-hound-{suffix}-{width}x{height}')
        await runner.caller.write(b'b')
        await wait(lambda: presence.room == 'r-entry')
        await wait(lambda: '/ CORE' in runner.caller.screen.screen_text().splitlines()[0])
        await runner.caller.write(b'b')
        await wait(lambda: presence.instance is None)
        await wait(lambda: '/ LATTICE' in runner.caller.screen.screen_text().splitlines()[0])
        await runner.caller.write(b'j')
        await wait(lambda: player.id not in lattice.presences)
        assert body.stance == 'normal' and body.position == original
        outcomes.append({'safe_body':safe,'same_body_damage':hp-after,'observer_hp_visible':True,
            'explicit_npc_consent':True,'trace_fixture':99,'hound_threshold_seconds':elapsed,
            'retreated_to_public':True,'funding_fixture':False,'placement_fixture':False})
        probe.report(f'PASS S14 black body/Hound {width}x{height} {suffix}: same body/witness HP, attributed Kiln hit after warning, explicit NPC consent, labelled trace-99 fixture, real retreat/jack-out')
        for connection in (runner,observer):
            await probe.leave(connection,f's14-risk-return-{suffix}-{connection.session.user_id}-{width}x{height}')
    return {'stage':'danger','size':[width,height],'content_fixture':True,'runs':outcomes,'passed':True}


async def gate(probe: NativeProbe, width: int, height: int, duo: bool = False) -> dict[str, Any]:
    lattice = probe.service.core.lattice
    encounters = lattice.encounters
    connections = [await probe.open(width,height,'S14GateA',1,True)]
    if duo:
        connections.append(await probe.open(width,height,'S14GateB',1))
    for index, connection in enumerate(connections):
        await hub(probe,connection)
        await probe.walk(connection,(30,5) if index == 0 else (56,5))
        player = probe.game.players[connection.session.player_id]
        # Explicit loan-program/active-contract fixtures for S16/S19 hooks.
        # No extra money, XP, items, body statistics or scene placement.
        player.progress['known_programs'] = ['prg_skeleton']
        probe.game.queue('save',connection.session.user_id,player,immediate=True)
        await connection.caller.write(b'e')
        await wait(lambda: player.id in lattice.presences)
        presence = lattice.presences[player.id]
        await wait(lambda: '/ LATTICE' in connection.caller.screen.screen_text().splitlines()[0])
        await connection.caller.write(b'r')
        await wait(lambda: connection.session.id in encounters.menus)
        await menu(probe,connection,'2')
        await wait(lambda: encounters.menus[connection.session.id].kind == 'binding')
        await menu(probe,connection,'prg_skeleton')
        await wait(lambda: presence.rig[2] == 'prg_skeleton')
        await connection.caller.write(b'b')
        await wait(lambda: connection.session.id not in encounters.menus)
        await wait(lambda: '/ LATTICE' in connection.caller.screen.screen_text().splitlines()[0])
        await lat_walk(probe,connection,'lat-core-c16')
        await program(probe,connection,2,lambda: presence.effects.shield is not None)
    entered_times = {}
    # S19 now owns mission custody. Use committed fixture instances instead
    # of the pre-S19 placeholder callback; consent UI is covered by S19.
    owner=probe.service.core.contracts
    await wait(lambda:not probe.commerce.pending and not probe.commerce.waiting)
    draft=owner.state.fork()
    missions={}
    for connection in connections:
        pid=connection.session.player_id
        instance=draft.engine.accept(draft.engine.story_offer('fixture-s14-gate-record',pid),
                                     (owner.participant(pid),),owner.now())
        missions[pid]=instance.id
    owner.write(draft)
    await wait(lambda:all(iid in owner.state.engine.instances for iid in missions.values())
               and not probe.commerce.pending)
    for connection in connections:
        await choose(probe,connection,'enter:lat-gatehouse-east')
        presence = lattice.presences[connection.session.player_id]
        await wait(lambda: presence.core == 'lat-gatehouse-east')
        entered_times[presence.player_id] = time.monotonic()
        await room_walk(probe,connection,'turnstile')
        turnstile = next(i for i in encounters.defenders(presence) if i.template.class_ == 'turnstile')
        await program(probe,connection,3,lambda: turnstile.id in presence.opened)
        await room_walk(probe,connection,'service-latch')
        await choose(probe,connection,'control:gate-nine-service-latch')
        await wait(lambda: presence.procedure is None and 'lat-gatehouse-east:gate-nine-service-latch' in lattice.interlock.state['effects'])
        source = encounters.core(presence).graph.room(presence.room).data[0]
        generation = lattice.sources.refresh(encounters.source(presence,source),source,probe.service.clock.now_tick()).generation
        await choose(probe,connection,f'lift:{source.id}:{generation}')
        await wait(lambda:any(unit.get('mission')==missions[presence.player_id]
            for unit in probe.game.players[presence.player_id].progress.get('lattice_units',{}).values()))
        probe.save(connection,f's14-gate-latch-{connection.session.user_id}-{width}x{height}')
    # Stage the crew at the quiet latch before entering the Hornets room.
    for connection in connections:
        await room_walk(probe,connection,'tools-archive')
    first = lattice.presences[connections[0].session.player_id]
    hornets = next(i for i in encounters.defenders(first) if i.template.class_ == 'hornets')
    # Both callers use real target/attack keys against the same defender.
    for connection in connections:
        await choose(probe,connection,'ice:'+hornets.id)
    await asyncio.gather(*(program(probe,c,1,lambda: not hornets.alive) for c in connections))
    assert not hornets.alive
    before = sum(probe.game.players[c.session.player_id].chits_hand for c in connections)
    source = next(d for d in encounters.core(first).graph.room(first.room).data if d.kind == 'chits')
    key = encounters.source(first,source)
    generation = lattice.sources.refresh(key,source,probe.service.clock.now_tick()).generation
    if duo:
        # Both inspect the same generation before either attempt starts.
        for connection in connections:
            await connection.caller.write(b'e')
            await wait(lambda: connection.session.id in encounters.menus)
        await asyncio.gather(*(menu(probe,c,f'lift:{source.id}:{generation}') for c in connections))
    else:
        await choose(probe,connections[0],f'lift:{source.id}:{generation}')
    await wait(lambda: lattice.sources.sources[key].generation == generation+1)
    await wait(lambda: all(lattice.presences[c.session.player_id].procedure is None for c in connections))
    after = sum(probe.game.players[c.session.player_id].chits_hand for c in connections)
    assert after-before == 120
    receipt_seconds = {pid:round(time.monotonic()-started,2) for pid,started in entered_times.items()}
    saved = probe.service.storage.character_state()
    assert saved['lattice']['sources'][key]['generation'] == generation+1
    for connection in connections:
        presence = lattice.presences[connection.session.player_id]
        assert presence.core == 'lat-gatehouse-east' and connection.avatar.actor.stance == 'jacked'
        probe.save(connection,f's14-gate-shared-credit-{connection.session.user_id}-{width}x{height}')
        await connection.caller.write(b'j')
        await wait(lambda: connection.session.player_id not in lattice.presences,12)
        await probe.leave(connection,f's14-gate-return-{connection.session.user_id}-{width}x{height}')
    probe.report(f'PASS S14 Gate Nine {width}x{height} {len(connections)} caller(s): labelled content/loan/contract fixtures, real Skeleton and Hornets, mission receipts, one shared 120-chit generation; committed three-second latch on the labelled physical fixture')
    return {'stage':'gate-duo' if duo else 'gate-solo','size':[width,height],
        'content_fixture':True,'loan_program_fixture':'Skeleton','active_contract_fixture':True,
        'funding_fixture':False,'placement_fixture':False,'shared_reward':after-before,
        'source_generations_consumed':1,'entry_to_credit_seconds':receipt_seconds,'latch_effect_claimed':False,'passed':True}


async def burn(probe: NativeProbe, width: int, height: int) -> dict[str, Any]:
    lattice = probe.service.core.lattice
    encounters = lattice.encounters
    a = await probe.open(width,height,'S14BurnA',1,True)
    b = await probe.open(width,height,'S14BurnB',1)
    for connection,tile in ((a,(25,25)),(b,(27,25))):
        player = probe.game.players[connection.session.player_id]
        await probe.walk(connection,(21,14))
        await connection.caller.write(b'b')
        await wait(lambda: player.progress.get('wake_combat') == 'skipped')
        await probe.travel(connection,'vatside-clinics')
        await probe.walk(connection,tile)
        # Explicit S16 grade/learning fixtures; no funding or teleport.
        player.update_progression(1700)
        player.progress['known_programs'] = ['prg_burn']
        connection.avatar.actor.health = connection.avatar.actor.health_max = character.health_max(player.attributes['vitals'])
        probe.game.queue('save',connection.session.user_id,player,immediate=True)
        await connection.caller.write(b'j')
        await wait(lambda: player.id in lattice.presences)
        presence = lattice.presences[player.id]
        await wait(lambda: '/ LATTICE' in connection.caller.screen.screen_text().splitlines()[0])
        await connection.caller.write(b'r')
        await wait(lambda: connection.session.id in encounters.menus)
        await menu(probe,connection,'2')
        await wait(lambda: encounters.menus[connection.session.id].kind == 'binding')
        await menu(probe,connection,'prg_burn')
        await wait(lambda: presence.rig[2] == 'prg_burn')
        await connection.caller.write(b'b')
        await wait(lambda: connection.session.id not in encounters.menus)
        await wait(lambda: '/ LATTICE' in connection.caller.screen.screen_text().splitlines()[0])
        uplink = next(c for c in lattice.sectors.records[presence.sector].cells if c.uplink and c.uplink.sector == 'lat-core')
        await lat_walk(probe,connection,uplink.id)
        await connection.caller.write(b'e')
        await wait(lambda: presence.sector == 'lat-core')
        entry = next(c for c in lattice.sectors.records['lat-core'].cells if c.core_id == 'lat-civic-ledger')
        await lat_walk(probe,connection,entry.id)
    first,second = lattice.presences[a.session.player_id],lattice.presences[b.session.player_id]
    for connection in (a,b):
        assert probe.service.world.zones[connection.avatar.actor.zone].allows_hostile(connection.avatar.actor.position)
    await a.caller.write(b'\t')
    await wait(lambda: first.target == second.player_id)
    await wait(lambda: 'PROTECTED' in a.caller.screen.screen_text())
    await a.caller.write(b'3')
    await wait(lambda: any('Both runners and physical bodies must permit burning here' in row['text'] for row in a.session.log_ring))
    assert first.cast is None and second.integrity == 100 and first.trace == 0
    assert not probe.game.players[first.player_id].progress.get('lattice_cooldowns',{}).get('prg_burn')
    probe.save(a,f's14-burn-public-refusal-{width}x{height}')
    for connection in (a,b):
        await choose(probe,connection,'enter:lat-civic-ledger')
        await wait(lambda: lattice.presences[connection.session.player_id].core == 'lat-civic-ledger')
    await wait(lambda: '/ CORE' in a.caller.screen.screen_text().splitlines()[0])
    await a.caller.write(b'\t')
    await wait(lambda: first.target == second.player_id)
    await wait(lambda: '100%' in a.caller.screen.screen_text())
    await a.caller.write(b'3')
    await wait(lambda: second.integrity == 82)
    assert probe.game.players[first.player_id].marked_until
    assert all(connection.avatar.actor.stance == 'jacked' for connection in (a,b))
    probe.save(a,f's14-burn-selected-runner-{width}x{height}')
    probe.save(b,f's14-burn-received-{width}x{height}')
    for connection in (a,b):
        await connection.caller.write(b'j')
        await wait(lambda: connection.session.player_id not in lattice.presences,12)
        await probe.leave(connection,f's14-burn-return-{connection.session.user_id}-{width}x{height}')
    probe.report(f'PASS S14 Burn {width}x{height}: labelled grade-five/Burn loan fixtures, real R binding/Tab/3, public refusal costs nothing, co-located permitted runner loses exactly 18 integrity, attacker attributed/Marked')
    return {'stage':'burn','size':[width,height],'grade_xp_fixture':1700,
        'loan_program_fixture':'Burn','funding_fixture':False,'placement_fixture':False,
        'public_refusal':True,'real_keys':['R','Tab','3'],'runner_integrity_damage':18,'passed':True}


async def accept(root: Path, door_python: Path, show: bool,
                 sizes: tuple[tuple[int, int], ...], stage: str) -> None:
    probe = NativeProbe(root, door_python, show)
    scenario_content(probe, stage)
    await probe.start()
    results = []
    try:
        for width, height in sizes:
            if stage.startswith('gate-'):
                results.append(await gate(probe,width,height,stage == 'gate-duo'))
            else:
                results.append(await {'training':training,'silt':silt,'danger':danger,'burn':burn}[stage](probe,width,height))
        assert not probe.errors and probe.service.failure is None
        (probe.root/f's14-{stage}-results.json').write_text(json.dumps(results, indent=2)+'\n', encoding='utf-8')
    except BaseException:
        diagnostics = []
        for connection in probe.connections:
            presence = probe.service.core.lattice.presences.get(connection.session.player_id)
            screen = probe.service.core.lattice.encounters.menus.get(connection.session.id)
            diagnostics.append({'player':connection.session.player_id, 'room':presence.room if presence else None,
                'core':presence.core if presence else None, 'menu':screen.kind if screen else None,
                'tick':probe.service.clock.now_tick(), 'commerce_pending':probe.commerce.pending,
                'logs':[row['text'] for row in list(connection.session.log_ring)[-12:]]})
        (probe.root/'failure-state.json').write_text(json.dumps(diagnostics,indent=2)+'\n',encoding='utf-8')
        for index, connection in enumerate(probe.connections):
            probe.save(connection, f's14-failed-{index}')
        raise
    finally:
        await probe.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--door-python', type=Path, required=True)
    parser.add_argument('--show', action='store_true')
    parser.add_argument('--stage', choices=('training', 'silt', 'danger', 'gate-solo', 'gate-duo', 'burn'), default='training')
    parser.add_argument('--size', choices=('both', '80', '132'), default='both')
    args = parser.parse_args()
    sizes = ((80, 24), (132, 50)) if args.size == 'both' else ((80, 24),) if args.size == '80' else ((132, 50),)
    if args.stage != 'training':
        # Separate worlds preserve nonce 1 in both profiles; never rewind a ledger.
        for width, height in sizes:
            asyncio.run(accept(args.root/f'{width}x{height}', args.door_python, args.show, ((width, height),), args.stage))
    else:
        asyncio.run(accept(args.root, args.door_python, args.show, sizes, args.stage))
