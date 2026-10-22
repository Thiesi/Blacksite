"""S12: real two-caller hub commerce through NetBBS native stdio.

Private node/world, real walking, no teleports or extra chits. Use the
NetBBS venv with --show in a real terminal; both sizes are negotiated.
The S25 spec owns the deferred real Tramyard rifle-purchase check.
"""

import argparse
import asyncio
from collections import deque
import json
from pathlib import Path
import re
import time
from typing import Any

from accept_s04_netbbs import Database, DatabaseLane, DoorProfile, REPO, TelnetServer, browse_doors, create_door, create_user
from accept_s06_netbbs import ZoneCaller
from blacksite.server.app import Server


async def wait(condition: Any, timeout: float = 10) -> None:
    async with asyncio.timeout(timeout):
        while not condition(): await asyncio.sleep(.02)


async def accept(root: Path, door_python: Path, show: bool) -> None:
    root=root.resolve(); root.mkdir(parents=True,exist_ok=True)
    service=Server(root/"world",tcp=True)
    await service.start()
    db=Database(root/"node.db"); lane=DatabaseLane(db.path)
    users=[create_user(db,f"S12{label}{width}",password="LocalProbe-S12",user_level=10)
           for width in (80,132) for label in ("Caller","Peer")]
    create_door(db,"Blacksite",str(door_python.absolute()),args=("-m","blacksite.door"),creator=users[0],
        profile=DoorProfile(install_dir=str(REPO),encoding="utf-8",max_sessions=16,multinode_certified=True,time_limit=900,
                           environment={"DOOR_BLACKSITE_INSTALL_DIR":str(service.install_dir)}).validate())
    next_user=0
    failures=[]
    async def handler(session: Any) -> None:
        nonlocal next_user
        user=users[next_user]; next_user+=1
        try:
            await browse_doors(session,lane,user)
            await session.write_line("You return to the node.")
        except Exception as exc:
            failures.append(repr(exc)); raise
    node=TelnetServer("127.0.0.1",0,handler,terminal_type_wait_seconds=.1)
    await node.start()
    connections=[]; results=[]
    game=service.core.characters
    commerce=service.core.commerce

    def report(message: str) -> None:
        print(message,flush=True)
        with (root/"progress.log").open("a",encoding="utf-8") as stream: stream.write(message+"\n")

    async def open_caller(width: int,height: int,name: str,visible: bool) -> tuple:
        reader,writer=await asyncio.open_connection("127.0.0.1",node.port)
        async def send(data: bytes) -> None:
            writer.write(data); await writer.drain()
        writer.write(b"\xff\xfb\x1f\xff\xfa\x1f"+width.to_bytes(2,"big")+height.to_bytes(2,"big")+b"\xff\xf0")
        writer.write(b"\xff\xfb\x18\xff\xfa\x18\x00xterm-256color\xff\xf0"); await writer.drain()
        caller=ZoneCaller(lambda:reader.read(65536),send,width,height,visible)
        await caller.expect("Available doors"); await caller.write(b"\x1b[B\r")
        await caller.until(lambda:"THE WAKE" in caller.screen.screen_text())
        async def pump() -> None:
            while chunk:=await reader.read(65536):
                caller.output.extend(chunk); caller.replay()
        task=asyncio.create_task(pump())
        session=next(s for s in game.sessions.active.values() if s.id in game.wakes)
        wake=game.wakes[session.id]
        await caller.write(b"\r"); await wait(lambda:"Name (Enter keeps default):" in caller.screen.screen_text())
        await caller.write(name.encode()+b"\r"); await wait(lambda:"Briefing" in caller.screen.screen_text())
        await caller.write(b"s"); await wait(lambda:"Recruiter cards" in caller.screen.screen_text())
        await caller.write(b"\r"); await wait(lambda:session.player_id in game.players)
        await wait(lambda:"Wake Hall" in caller.screen.screen_text().splitlines()[0])
        connection=caller,writer,task,session,game.sim.avatars[session.user_id]
        connections.append(connection)
        return connection

    async def walk(connection: tuple,target: tuple[int,int]) -> None:
        caller,_,_,_,av=connection
        zone=service.world.zones[av.zone]
        deadline=time.monotonic()+120
        while av.actor.position!=target:
            assert time.monotonic()<deadline, ("walk timeout", zone.id, av.actor.position, target)
            start=av.actor.position
            blocked={a.position for a in zone.actors.values() if a is not av.actor
                and not (a.behaviour.get("training") and a.owner!=av.actor.id)}
            pending,previous=deque([start]),{start:None}
            exits={e.tile for e in zone.template.meta.exits if e.kind=="street"}
            while pending and target not in previous:
                x,y=pending.popleft()
                for tile in ((x+1,y),(x,y+1),(x-1,y),(x,y-1)):
                    if tile not in previous and tile not in blocked and zone.passable(tile) and (tile not in exits or tile==target):
                        previous[tile]=(x,y); pending.append(tile)
            if target not in previous:
                await asyncio.sleep(.2)
                continue
            step=target
            while previous[step]!=start: step=previous[step]
            vector=step[0]-start[0],step[1]-start[1]
            await caller.write({(1,0):b"\x1b[C",(-1,0):b"\x1b[D",(0,1):b"\x1b[B",(0,-1):b"\x1b[A"}[vector])
            try:
                await wait(lambda:av.actor.position!=start or av.zone!=zone.id,.6)
            except TimeoutError:
                continue  # Moving NPC traffic can take the planned tile.
            await asyncio.sleep(.21)
            if av.zone!=zone.id: break

    async def acknowledge(connection: tuple) -> None:
        session=connection[3]
        await wait(lambda:session.ack_revision==session.view_revision)

    async def open_menu(connection: tuple,key: bytes,kind: str) -> None:
        await connection[0].write(key)
        sid=connection[3].id
        await wait(lambda:sid in commerce.menus and commerce.menus[sid].kind==kind)
        await wait(lambda:game.sim.overlays.get(sid,(None,{}))[0]=="menu")
        await acknowledge(connection)

    async def choose(connection: tuple,row: str,key: bytes = b"\r") -> None:
        session=connection[3]
        screen=commerce.menus[session.id]
        rows=commerce.body(session,screen)["rows"]
        cursor=next(i for i,r in enumerate(rows) if r["id"]==row)
        while screen.cursor!=cursor:
            old=screen.cursor
            await connection[0].write(b"\x1b[B" if old<cursor else b"\x1b[A")
            await wait(lambda:screen.cursor!=old)
        await wait(lambda:game.sim.overlays.get(session.id,(None,{}))[1].get("cursor")==cursor)
        await acknowledge(connection)
        await connection[0].write(key)

    async def close_menu(connection: tuple) -> None:
        await connection[0].write(b"\x1b")
        await wait(lambda:connection[3].id not in commerce.menus)
        await wait(lambda:service.world.zones[connection[4].zone].template.meta.name in connection[0].screen.screen_text().splitlines()[0])

    async def trade_ready(connection: tuple) -> None:
        history=connection[3].rate_counters.get("trade",[])
        if history: await wait(lambda:service.clock.now_tick()>=history[-1]+10)

    def carried(connection: tuple,template: str) -> str:
        player=game.players[connection[3].player_id]
        return next(i for i in player.inventory if commerce.items[i].template==template)

    async def leave(connection: tuple,label: str) -> None:
        caller,writer,task,_,_=connection
        mark=len(caller.output)
        await caller.write(b"\x18y"); await wait(lambda:b"Left Blacksite." in caller.output[mark:])
        await caller.write(b" ")
        await wait(lambda:b"Available doors" in re.sub(rb"\x1b\[[0-?]*[ -/]*[@-~]",b"",bytes(caller.output[mark:])))
        await caller.write(b"b"); await wait(lambda:b"You return to the node." in caller.output[mark:])
        (root/(label+".ans")).write_bytes(caller.output)
        writer.close(); await writer.wait_closed(); await task
        connections.remove(connection)

    try:
        for width,height in ((80,24),(132,50)):
            a=await open_caller(width,height,f"Alpha界{width}",show)
            b=await open_caller(width,height,f"Beta界{width}",False)
            player=game.players[a[3].player_id]
            assert player.chits_hand==200
            await walk(a,(34,15))
            await open_menu(a,b"e","vendor")
            await a[0].write(b"t"); await wait(lambda:commerce.menus[a[3].id].sell)
            await wait(lambda:game.sim.overlays.get(a[3].id,(None,{}))[1].get("title","").endswith("SELL")); await acknowledge(a)
            pistol=carried(a,"wpn_kestrel_sidearm")
            await choose(a,pistol); await wait(lambda:player.chits_hand==248)
            await a[0].write(b"t"); await wait(lambda:not commerce.menus[a[3].id].sell)
            await wait(lambda:game.sim.overlays.get(a[3].id,(None,{}))[1].get("title","").endswith("BUY")); await acknowledge(a)
            await trade_ready(a); await choose(a,"wpn_kestrel_sidearm"); await wait(lambda:player.chits_hand==128)
            await trade_ready(a); await choose(a,"ammo_9x"); await wait(lambda:player.chits_hand==103)
            await close_menu(a); await open_menu(a,b"i","inventory")
            pistol=carried(a,"wpn_kestrel_sidearm")
            await choose(a,pistol,b"q"); await wait(lambda:player.equipment.get("weapon_main")==pistol)
            await close_menu(a)
            await wait(lambda:"Kestrel Issue Sidearm" in a[0].screen.screen_text())
            await open_menu(a,b"e","vendor")
            await a[0].write(b"t"); await wait(lambda:commerce.menus[a[3].id].sell)
            await wait(lambda:game.sim.overlays.get(a[3].id,(None,{}))[1].get("title","").endswith("SELL")); await acknowledge(a)
            await trade_ready(a)
            before_budget=commerce.budgets["vatside-wake-hall:wake-outfitter"]
            before_remaining,before_hour=before_budget.remaining,before_budget.hour
            await choose(a,carried(a,"wpn_kestrel_baton")); await wait(lambda:player.chits_hand==119)
            budget=commerce.budgets["vatside-wake-hall:wake-outfitter"].remaining
            assert budget==(before_remaining if before_hour==commerce.budgets["vatside-wake-hall:wake-outfitter"].hour else 2000)-16
            await close_menu(a)
            # The outfitter can anchor anywhere in x33..35/y14..16.
            # Park both callers outside that live NPC spawn region.
            await walk(b,(32,16))
            await open_menu(a,b"i","inventory")
            patch=carried(a,"con_sablier_patch")
            await choose(a,patch,b"d"); await wait(lambda:patch not in player.inventory)
            await close_menu(a); await walk(a,(32,15)); await walk(b,(34,15))
            await open_menu(b,b"e","cache"); await choose(b,patch)
            await wait(lambda:patch in game.players[b[3].player_id].inventory)
            await close_menu(b)
            for target in ("vatside-clinics","core-plaza","core-tram-hub"):
                origin=a[4].zone
                ex=next(e for e in service.world.zones[a[4].zone].template.meta.exits if e.target_zone==target)
                await walk(a,ex.tile)
                if a[4].zone==origin: await a[0].write(b"e")
                await wait(lambda:a[4].zone==target)
                await wait(lambda:service.world.zones[target].template.meta.name in a[0].screen.screen_text().splitlines()[0])
            await walk(a,(12,7)); await open_menu(a,b"e","bank")
            await choose(a,"deposit"); await wait(lambda:"Chits:" in a[0].screen.screen_text())
            await a[0].write(b"100\r"); await wait(lambda:player.chits_bank==100 and player.chits_hand==19)
            await close_menu(a)
            # Cancellation of the amount prompt has no side effect.
            await open_menu(a,b"e","bank"); await choose(a,"withdraw")
            await wait(lambda:"Chits:" in a[0].screen.screen_text())
            await a[0].write(b"\x1b"); await wait(lambda:a[3].id not in commerce.prompts)
            assert player.chits_bank==100; await close_menu(a)
            await a[0].write(b"p"); await wait(lambda:"CHARACTER" in a[0].screen.screen_text())
            rows=game.progression.sheet(player)["rows"]
            bank_row=next(i for i,row in enumerate(rows) if row["id"]=="bank")
            while game.screens[a[3].id][1]!=bank_row:
                old=game.screens[a[3].id][1]
                await a[0].write(b"\x1b[B" if old<bank_row else b"\x1b[A")
                await wait(lambda:game.screens[a[3].id][1]!=old)
            await wait(lambda:"Bank chits" in a[0].screen.screen_text())
            await a[0].write(b"\x1b"); await wait(lambda:a[3].id not in game.screens)
            persisted=next(p for p in service.storage.character_state()["players"] if p["id"]==player.id)
            assert persisted["chits_bank"]==100 and persisted["chits_hand"]==19
            assert persisted["equipment"]["weapon_main"]==pistol and patch not in persisted["inventory"]
            await leave(a,f"commerce-a-{width}x{height}"); await leave(b,f"commerce-b-{width}x{height}")
            results.append({"size":[width,height],"walked":True,"buy_equip_sell":True,"cache_exchange":True,"bank_cancel":True,"durable":True,"hand":19,"bank":100})
            report(f"PASS commerce {width}x{height}: real hub walking, buy/equip/sell, two-caller cache, bank 100, cancel, durable state, clean exits")
        assert not failures,failures
        (root/"result.json").write_text(json.dumps({"passed":True,"transport":"NetBBS Telnet native stdio","scenario_funding":False,"teleports":False,"runs":results},indent=2))
    finally:
        for index,(caller,writer,task,_,_) in enumerate(connections):
            (root/f"unfinished-{index}.ans").write_bytes(caller.output)
            (root/f"unfinished-{index}.txt").write_text(caller.screen.screen_text(),encoding="utf-8")
            writer.close(); task.cancel()
        await node.stop(); lane.close(); await service.stop(); db.close()


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--root",type=Path,required=True)
    parser.add_argument("--door-python",type=Path,required=True)
    parser.add_argument("--show",action="store_true")
    args=parser.parse_args()
    asyncio.run(accept(args.root,args.door_python,args.show))
