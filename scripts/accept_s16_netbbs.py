"""S16 real NetBBS native stdio: progression, surgery and ten-minute detox.

Disclosed fixtures: grade4 at1485 XP,12000 chits, an owned Reflex Arm,
three Redline doses, and a1HP grade4 NPC. No placement or clock fixture.
The actual Spire purchase and Sink clinic remain S25 acceptance gates.
"""

import argparse
import asyncio
from dataclasses import replace
import json
from pathlib import Path
import time
import traceback
from typing import Any

from accept_s10_netbbs import Connection, NativeProbe, wait
from blacksite.server.drugs import detox_until
from blacksite.server.inventory import Inventory
from blacksite.server.items import make_item
from blacksite.server.npcs.templates import make_actor


def loan(probe: NativeProbe, connection: Connection, template: str) -> str:
    player = probe.game.players[connection.session.player_id]
    serial = probe.combat.next_serial()+1
    probe.commerce.serial = serial
    iid = f"{player.origin}:item:{serial}"
    item = make_item(iid,probe.game.content.items[template],player.id,
                     probe.service.clock.now_utc().isoformat())
    Inventory(probe.commerce.items,probe.game.content.items,
              probe.service.core.progression.modifiers(player).secured_slots).add(player,item)
    return iid


async def key(connection: Connection, value: bytes) -> None:
    await wait(lambda:connection.session.ack_revision == connection.session.view_revision)
    await connection.caller.write(value)


async def select(connection: Connection, rows: Any, screen: Any, row: str) -> None:
    wanted = next(i for i,r in enumerate(rows()) if r['id'] == row)
    while screen.cursor != wanted:
        old = screen.cursor
        await key(connection,b'\x1b[B' if wanted > old else b'\x1b[A')
        await wait(lambda:screen.cursor != old)


async def clinic(probe: NativeProbe, connection: Connection, row: str) -> None:
    clinics = probe.service.core.progression.clinics
    await key(connection,b'e')
    await wait(lambda:connection.session.id in probe.commerce.menus)
    await key(connection,b'c')
    await wait(lambda:connection.session.id in clinics.menus)
    screen = clinics.menus[connection.session.id]
    await select(connection,lambda:clinics.view(connection.session,screen)['rows'],screen,row)
    await key(connection,b'\r')
    await wait(lambda:bool(screen.confirm))
    await wait(lambda:'TOTAL' in connection.caller.screen.screen_text())


async def use(probe: NativeProbe, connection: Connection, iid: str) -> None:
    await key(connection,b'i')
    await wait(lambda:connection.session.id in probe.commerce.menus)
    screen = probe.commerce.menus[connection.session.id]
    await select(connection,lambda:probe.commerce.body(connection.session,screen)['rows'],screen,iid)
    await key(connection,b'u')
    await wait(lambda:iid not in probe.commerce.items)
    if connection.session.id in probe.commerce.menus:
        await key(connection,b'\x1b')
        await wait(lambda:connection.session.id not in probe.commerce.menus)


async def prepare(probe: NativeProbe, width: int, height: int) -> tuple[Connection,dict[str,Any]]:
    connection = await probe.open(width,height,'S16Ghost',1)
    await probe.walk(connection,(22,14))
    await key(connection,b'b')  # Ordinary skip of private training.
    await probe.travel(connection,'vatside-clinics')
    await probe.travel(connection,'core-plaza')
    await probe.travel(connection,'sodium-row')
    player = probe.game.players[connection.session.player_id]
    player.update_progression(1485)
    player.chits_hand = 12000
    progression = probe.service.core.progression
    progression.sync_actor(player)
    before = player.grade,player.progress['points'],connection.avatar.actor.health_max
    template = replace(probe.game.content.npcs['npc-wake-drone'],id='npc-s16-fixture',
        name='Labelled progression fixture',grade=4,health=1,training=False,xp=1)
    probe.game.content.npcs[template.id] = template
    victim = make_actor(template,f's16-fixture:{width}',{'home':connection.avatar.actor.position,'phase':0})
    tile = probe.service.world.free_tile(connection.avatar.zone,connection.avatar.actor.position)
    probe.service.world.enter(victim,connection.avatar.zone,tile)
    probe.report(f'FIXTURE S16 {width}x{height}: grade4/1485XP,12000 chits,1HP grade4 NPC; no teleport')
    await probe.target(connection,victim.id)
    async with asyncio.timeout(35):
        while player.grade < 5:
            await key(connection,b'f'); await asyncio.sleep(.25)
    assert player.progress['points'] == before[1]+3
    assert connection.avatar.actor.health_max > before[2] and player.legal_at
    await wait(lambda:'Ninety-Day' in connection.caller.screen.screen_text())
    probe.save(connection,f's16-grade-toast-{width}')
    await key(connection,b'p')
    await wait(lambda:connection.session.id in probe.game.screens)
    await key(connection,b's')
    await wait(lambda:connection.session.id in progression.menus)
    starting = player.skills['kinetic'],player.attributes['frame']
    for index in range(10):
        value = player.skills['kinetic']
        await key(connection,b'+')
        await wait(lambda:player.skills['kinetic'] > value)
        if index == 2:
            assert player.skills['kinetic'] == starting[0]+3
            probe.save(connection,f's16-three-points-{width}')
    assert player.attributes['frame'] == starting[1]+1
    await key(connection,b'\x1b'); await wait(lambda:connection.session.id not in progression.menus)
    await key(connection,b'\x1b'); await wait(lambda:connection.session.id not in probe.game.screens)
    await probe.travel(connection,'core-plaza')
    await probe.travel(connection,'vatside-clinics')
    zone = probe.service.world.zones[connection.avatar.zone]
    counter = next(o for o in zone.objects.values() if o.spec.params.get('vendor') == 'sablier-clinic')
    await probe.walk(connection,counter.spec.tile)
    arm = loan(probe,connection,'imp_halvard_reflex_arm')
    probe.report(f'FIXTURE S16 {width}x{height}: owned Reflex Arm loan; Spire purchase deferred to S25')
    await clinic(probe,connection,'install:'+arm+':arms1')
    text = connection.caller.screen.screen_text()
    assert 'Failure 2%' in text and '2/4' in text
    probe.save(connection,f's16-surgery-bill-{width}')
    await key(connection,b'y')
    await wait(lambda:not probe.commerce.pending)
    await wait(lambda:not progression.clinics.menus[connection.session.id].confirm)
    assert player.implants.get('arms1') == arm, 'Natural 2% surgery failure; repeat with a fresh disclosed loan.'
    assert progression.modifiers(player).multiplier('weapon_cooldown_multiplier') == .9
    await key(connection,b'\x1b'); await wait(lambda:connection.session.id not in progression.clinics.menus)
    for _ in range(3):
        await use(probe,connection,loan(probe,connection,'drug_sable_redline'))
    assert any(d['template'] == 'drug_sable_redline' for d in player.dependencies)
    await clinic(probe,connection,'detox')
    assert 'TOTAL 400' in connection.caller.screen.screen_text()
    await key(connection,b'y')
    await wait(lambda:detox_until(player) > probe.service.clock.now_utc().timestamp())
    start,position,chits = time.monotonic(),connection.avatar.actor.position,player.chits_hand
    await key(connection,b'\x1b'); await key(connection,b'\x1b[A')
    await asyncio.sleep(.3)
    assert connection.avatar.actor.position == position
    probe.save(connection,f's16-detox-locked-{width}')
    probe.report(f'PASS S16 {width}x{height}: grade5,10 points/Frame+1,owned surgery .9 cooldown,three-dose dependency; real600s detox started')
    return connection,{'size':[width,height],'detox_start':start,'position':position,'chits':chits}


async def accept(root: Path, python: Path, show: bool) -> None:
    probe = NativeProbe(root,python,show)
    await probe.start()
    try:
        runs = [await prepare(probe,*size) for size in ((80,24),(132,50))]
        for connection,result in runs:
            player = probe.game.players[connection.session.player_id]
            await wait(lambda:not player.dependencies and not detox_until(player),620)
            elapsed = time.monotonic()-result.pop('detox_start')
            assert elapsed >= 599 and player.chits_hand == result['chits']
            assert connection.avatar.actor.position == tuple(result['position'])
            probe.save(connection,f's16-detox-complete-{result["size"][0]}')
            result['detox_real_seconds'] = elapsed
            probe.report(f'PASS S16 {result["size"]}: detox completed after {elapsed:.1f}s with one400-chit bill')
            await probe.leave(connection,f's16-return-{result["size"][0]}')
        assert not probe.errors and probe.service.failure is None
        (probe.root/'s16-results.json').write_text(json.dumps({'passed':True,
            'transport':'NetBBS Telnet -> native stdio','fixtures':['grade4','funding','owned implant','1HP NPC','drug loans'],
            'placement_fixture':False,'clock_fixture':False,'runs':[r for _,r in runs]},indent=2)+'\n',encoding='utf-8')
    except BaseException:
        (probe.root/'failure-trace.txt').write_text(traceback.format_exc(),encoding='utf-8')
        raise
    finally:
        await probe.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--door-python',type=Path,required=True)
    parser.add_argument('--show',action='store_true')
    args = parser.parse_args()
    asyncio.run(accept(args.root,args.door_python,args.show))
