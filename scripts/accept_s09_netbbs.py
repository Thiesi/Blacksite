"""S09: two real NetBBS native stdio callers, social routing and log UI.

Private node/world; explicit Plaza scenario placement, not a travel claim.
Run with NetBBS's venv (SSH/web extras), --show in a 132x50 parent terminal.
"""

import argparse
import asyncio
import json
from pathlib import Path
import re

from accept_s04_netbbs import Database, DatabaseLane, DoorProfile, REPO, TelnetServer, browse_doors, create_door, create_user
from accept_s06_netbbs import ZoneCaller
from blacksite.server.app import Server


async def wait(condition: object, timeout: float = 10) -> None:
    async with asyncio.timeout(timeout):
        while not condition():
            await asyncio.sleep(.02)


async def accept(root: Path, door_python: Path, show: bool) -> None:
    root=root.resolve();root.mkdir(parents=True,exist_ok=True)
    service=Server(root/'world',tcp=True)
    await service.start()
    db=Database(root/'node.db');lane=DatabaseLane(db.path)
    users=[create_user(db,f'{label}{width}',password='LocalProbe-S09',user_level=10)
           for width in (80,132) for label in ('Caller','Peer')]
    create_door(db,'Blacksite',str(door_python.absolute()),args=('-m','blacksite.door'),creator=users[0],
        profile=DoorProfile(install_dir=str(REPO),encoding='utf-8',max_sessions=16,multinode_certified=True,
                           time_limit=900,environment={'DOOR_BLACKSITE_INSTALL_DIR':str(service.install_dir)}).validate())
    next_user=0
    failures=[]
    async def handler(session: object) -> None:
        nonlocal next_user
        user=users[next_user];next_user+=1
        try:
            await browse_doors(session,lane,user)
            await session.write_line('You return to the node.')
        except Exception as exc:
            failures.append(repr(exc));raise
    node=TelnetServer('127.0.0.1',0,handler,terminal_type_wait_seconds=.1)
    await node.start()
    connections=[];results=[]
    manager=service.core.characters

    def report(text: str) -> None:
        print(text,flush=True)
        with (root/'progress.log').open('a',encoding='utf-8') as stream:stream.write(text+'\n')

    async def open_caller(width: int,height: int,name: str,visible: bool) -> tuple:
        reader,writer=await asyncio.open_connection('127.0.0.1',node.port)
        async def send(data: bytes) -> None:
            writer.write(data);await writer.drain()
        writer.write(b'\xff\xfb\x1f\xff\xfa\x1f'+width.to_bytes(2,'big')+height.to_bytes(2,'big')+b'\xff\xf0')
        writer.write(b'\xff\xfb\x18\xff\xfa\x18\x00xterm-256color\xff\xf0')
        await writer.drain()
        caller=ZoneCaller(lambda:reader.read(65536),send,width,height,visible)
        await caller.expect('Available doors');await caller.write(b'\x1b[B\r')
        await caller.until(lambda:'THE WAKE' in caller.screen.screen_text())
        async def pump() -> None:
            while chunk:=await reader.read(65536):
                caller.output.extend(chunk);caller.replay()
        task=asyncio.create_task(pump())
        session=next(s for s in manager.sessions.active.values() if s.id in manager.wakes)
        wake=manager.wakes[session.id]
        await caller.write(b'\r');await wait(lambda:'Name (Enter keeps default):' in caller.screen.screen_text())
        await caller.write(name.encode()+b'\r');await wait(lambda:wake.stage=='briefing')
        await wait(lambda:'Briefing' in caller.screen.screen_text())
        await caller.write(b's');await wait(lambda:'Recruiter cards' in caller.screen.screen_text())
        await caller.write(b'\r');await wait(lambda:session.player_id in manager.players)
        await wait(lambda:'Wake Hall' in caller.screen.screen_text())
        av=manager.sim.avatars[session.user_id]
        service.world.zones[av.zone].deactivate(session.id,service.clock.now_tick())
        tile=(10,5) if name.startswith('Alpha') else (15,5)
        service.world.enter(av.actor,'core-plaza',tile)
        av.zone=session.subscribed='core-plaza'
        service.world.zones[av.zone].activate(session.id,service.clock.now_tick())
        manager.sim.reset_view(session,av)
        await wait(lambda:'Meridian Plaza' in caller.screen.screen_text())
        result=caller,writer,task,session,av
        connections.append(result)
        return result

    def text(connection: tuple) -> str:
        return connection[0].screen.screen_text()

    async def say(connection: tuple,message: str,key: bytes = b'\r') -> None:
        caller,_,_,session,_=connection
        await caller.write(key)
        await wait(lambda:'chat' in session.pending_prompts)
        pid=session.pending_prompts['chat']['id']
        label='Whisper (name: text)' if key==b'`' else 'Say:'
        await wait(lambda:label in text(connection))
        await caller.write(message.encode('utf-8')+b'\r')
        await wait(lambda:session.pending_prompts.get('chat',{}).get('id')!=pid)
        await wait(lambda:label not in text(connection))

    async def leave(connection: tuple,label: str) -> None:
        caller,writer,task,_,_=connection
        mark=len(caller.output)
        await caller.write(b'\x18y')
        await wait(lambda:b'Left Blacksite.' in caller.output[mark:])
        await caller.write(b' ')
        await wait(lambda:b'Available doors' in re.sub(rb'\x1b\[[0-?]*[ -/]*[@-~]',b'',bytes(caller.output[mark:])))
        await caller.write(b'b');await wait(lambda:b'You return to the node.' in caller.output[mark:])
        (root/(label+'.ans')).write_bytes(caller.output)
        writer.close();await writer.wait_closed();await task
        connections.remove(connection)

    try:
        for width,height in ((80,24),(132,50)):
            a=await open_caller(width,height,f'Alpha界{width}',show)
            b=await open_caller(width,height,f'Beta界{width}',False)
            await say(a,'hello')
            await wait(lambda:f'[say] Alpha界{width}: hello' in text(a) and f'[say] Alpha界{width}: hello' in text(b))
            for _ in range(25):
                before=b[4].actor.position
                async with asyncio.timeout(5):
                    while b[4].actor.position==before:
                        await b[0].write(b'\x1b[C')
                        await asyncio.sleep(.22)
            mark=len(b[0].output)
            await say(a,'far say')
            assert b'far say' not in b[0].output[mark:]
            await say(a,'/shout all here')
            await wait(lambda:'all here' in text(b))
            await say(a,f'Peer{width}: private hello',b'`')
            await wait(lambda:'private hello' in text(b))
            await say(b,f'Caller{width}: private reply',b'`')
            await wait(lambda:'private reply' in text(a))
            assert f'Caller{width}' in text(a) and f'Peer{width}' in text(a) and '界' in text(a)
            await asyncio.sleep(5.1)
            await say(a,'/me waves');await wait(lambda:f'Alpha界{width} waves' in text(b))
            await say(a,f'/wave Beta界{width}');await wait(lambda:'waves at you.' in text(b))
            for connection in (a,b):
                await connection[0].write(b'W');await wait(lambda:'SITREP' in text(connection))
            assert 'Meridian Plaza' in text(a)
            await b[0].write(b'h')
            await wait(lambda:manager.players[b[3].player_id].settings.get('sitrep_hidden') is True)
            await wait(lambda:'hidden' in text(a) and 'Meridian Plaza' not in text(b))
            for connection in (a,b):
                await connection[0].write(b'\x1b');await wait(lambda:'SITREP' not in text(connection))
            await asyncio.sleep(5.1)
            start=len(a[3].log_ring)
            for i in range(6):await say(a,f'burst-{i}')
            burst=[line for line in list(a[3].log_ring)[start:] if 'burst-' in line['text']]
            assert len(burst)==4,burst
            await wait(lambda:'four lines every five seconds' in text(a))
            await b[0].write(b'\x10');await wait(lambda:'SCROLLBACK' in text(b))
            await b[0].write(b'\x1b[6~');await asyncio.sleep(.2)
            await b[0].write(b'\x1b');await wait(lambda:'SCROLLBACK' not in text(b))
            await asyncio.sleep(5.1)
            await say(b,f'/ignore Alpha界{width}')
            mark=len(b[0].output)
            await say(a,'/shout ignored-message')
            assert b'ignored-message' not in b[0].output[mark:]
            await say(b,f'/report Alpha界{width}: acceptance report')
            await wait(lambda:'Reported.' in text(b))
            audit=[json.loads(line) for line in (service.install_dir/'logs/audit.log').read_text(encoding='utf-8').splitlines()]
            assert any(row.get('action')=='report' and row.get('reporter')==b[3].player_id for row in audit)
            await say(b,f'/unignore Alpha界{width}')
            await leave(a,f'chat-a-{width}x{height}');await leave(b,f'chat-b-{width}x{height}')
            results.append({'size':[width,height],'say_radius':True,'shout':True,'whisper_wide_names':True,
                            'emotes':True,'symmetric_privacy':True,'four_of_six':True,'scrollback':True,'ignore_report':True})
            report(f'PASS social {width}x{height}: say/shout/whisper, wide names, emotes, sitrep privacy, rate limit, scrollback, ignore/report, clean exits')
        assert not failures,failures
        (root/'result.json').write_text(json.dumps({'passed':True,'transport':'NetBBS Telnet native stdio','scenario_placement':True,'runs':results},indent=2))
    finally:
        for _,writer,task,_,_ in connections:
            writer.close();task.cancel()
        await node.stop();lane.close();db.close();await service.stop()


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--door-python',type=Path,required=True)
    parser.add_argument('--show',action='store_true')
    args=parser.parse_args()
    asyncio.run(accept(args.root,args.door_python,args.show))
