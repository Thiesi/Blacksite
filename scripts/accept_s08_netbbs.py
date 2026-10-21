"""S08 real Telnet/native stdio walking, scheduled tram and map acceptance.

Uses private worlds/accounts. Run with NetBBS's venv and --show in a real
132x50 terminal; both negotiated sizes are exercised. No scenario teleport.
"""

import argparse
import asyncio
from collections import deque
import json
from pathlib import Path
import re
import time

from accept_s04_netbbs import Database, DatabaseLane, DoorProfile, REPO, TelnetServer, browse_doors, create_door, create_user
from accept_s06_netbbs import ZoneCaller
from blacksite.server.app import Server


async def wait(condition: object, timeout: float = 10) -> None:
    async with asyncio.timeout(timeout):
        while not condition():
            await asyncio.sleep(.02)


async def accept(root: Path, door_python: Path, show: bool) -> None:
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    service = Server(root/"world", tcp=True)
    await service.start()
    db = Database(root/"node.db")
    lane = DatabaseLane(db.path)
    users = [create_user(db, f"s08{label}", password="LocalProbe-S08", user_level=10) for label in ("walker","observer")]
    create_door(db,"Blacksite",str(door_python.absolute()),args=("-m","blacksite.door"),creator=users[0],
        profile=DoorProfile(install_dir=str(REPO),encoding="utf-8",max_sessions=16,multinode_certified=True,
                           time_limit=900,environment={"DOOR_BLACKSITE_INSTALL_DIR":str(service.install_dir)}).validate())
    failures: list[str] = []
    next_user = 0
    async def handler(session: object) -> None:
        nonlocal next_user
        user = users[next_user % 2]
        next_user += 1
        try:
            await browse_doors(session,lane,user)
            await session.write_line("You return to the node.")
        except Exception as exc:
            failures.append(repr(exc))
            raise
    node = TelnetServer("127.0.0.1",0,handler,terminal_type_wait_seconds=.1)
    await node.start()
    connections: list[tuple] = []
    results: list[dict] = []
    manager = service.core.characters

    def report(text: str) -> None:
        print(text,flush=True)
        with (root/"progress.log").open("a",encoding="utf-8") as stream:
            stream.write(text+"\n")

    async def open_caller(width: int,height: int, first: bool, visible: bool) -> tuple:
        reader,writer = await asyncio.open_connection("127.0.0.1",node.port)
        async def send(data: bytes) -> None:
            writer.write(data)
            await writer.drain()
        writer.write(b"\xff\xfb\x1f\xff\xfa\x1f"+width.to_bytes(2,"big")+height.to_bytes(2,"big")+b"\xff\xf0")
        writer.write(b"\xff\xfb\x18\xff\xfa\x18\x00xterm-256color\xff\xf0")
        await writer.drain()
        caller = ZoneCaller(lambda:reader.read(65536),send,width,height,visible)
        await caller.expect("Available doors")
        await caller.write(b"\x1b[B\r")
        await caller.until(lambda: "THE WAKE" in caller.screen.screen_text() or "Wake Hall" in caller.screen.screen_text())
        async def pump() -> None:
            while chunk := await reader.read(65536):
                caller.output.extend(chunk)
                caller.replay()
        task = asyncio.create_task(pump())
        if first:
            session = next(s for s in manager.sessions.active.values() if s.id in manager.wakes)
            wake = manager.wakes[session.id]
            await caller.write(b"\r")
            await wait(lambda:wake.stage=="name")
            await asyncio.sleep(.2)
            await caller.write(b"\r")
            await wait(lambda:wake.stage=="briefing")
            await caller.write(b"s")
            await wait(lambda:wake.stage=="card")
            await asyncio.sleep(.2)
            await caller.write(b"\r")
            await wait(lambda:session.player_id in manager.players)
        else:
            session = next(s for s in manager.sessions.active.values() if s.role=="caller" and s.id not in {c[3].id for c in connections})
        await wait(lambda:"Wake Hall" in caller.screen.screen_text())
        connection = caller,writer,task,session
        connections.append(connection)
        return connection

    def avatar(connection: tuple) -> object:
        return manager.sim.avatars[connection[3].user_id]

    async def walk(connection: tuple, target: tuple[int,int]) -> None:
        caller,_,_,session = connection
        av = avatar(connection)
        zone = service.world.zones[av.zone]
        # Cardinal BFS avoids corner cutting; recompute around live bodies.
        while av.actor.position != target:
            start = av.actor.position
            blocked = {a.position for a in zone.actors.values() if a is not av.actor}
            pending,previous = deque([start]),{start:None}
            exits = {e.tile for e in zone.template.meta.exits if e.kind=="street"}
            while pending and target not in previous:
                x,y = pending.popleft()
                for tile in ((x+1,y),(x,y+1),(x-1,y),(x,y-1)):
                    if tile not in previous and tile not in blocked and zone.passable(tile) and (tile not in exits or tile==target):
                        previous[tile]=(x,y)
                        pending.append(tile)
            assert target in previous,(zone.id,start,target)
            step = target
            while previous[step] != start:
                step = previous[step]
            dx,dy=step[0]-start[0],step[1]-start[1]
            key = {(1,0):b"\x1b[C",(-1,0):b"\x1b[D",(0,1):b"\x1b[B",(0,-1):b"\x1b[A"}[dx,dy]
            await caller.write(key)
            await wait(lambda:av.actor.position != start or av.zone != zone.id)
            await asyncio.sleep(.21)  # Real 200ms walk cooldown, no accelerated clock.
            if av.zone != zone.id:
                break

    async def travel(connection: tuple,target: str) -> None:
        av = avatar(connection)
        origin = av.zone
        ex = next(e for e in service.world.zones[origin].template.meta.exits if e.target_zone==target)
        await walk(connection,ex.tile)
        if av.zone==origin:
            await connection[0].write(b"e")
        if ex.kind=="tram":
            await wait(lambda:av.travel is not None)
            started = time.monotonic()
            await wait(lambda:av.travel is not None and av.travel.departed,95)
            await wait(lambda:"The tram hums." in connection[0].screen.screen_text())
            assert av.actor.id not in service.world.actors
            await connection[0].write(b"\x1b")
            await wait(lambda:"SCROLLBACK" in connection[0].screen.screen_text())
            await connection[0].write(b"\x1b")
            await wait(lambda:av.zone==target,15)
            report(f"PASS real scheduled tram: {time.monotonic()-started:.1f}s boarding+ride")
        else:
            await wait(lambda:av.zone==target)
        # Arrival logs may name the destination before its ZoneView is drawn.
        # Wait for the actual header so safety assertions inspect that view.
        await wait(lambda:service.world.zones[target].template.meta.name in connection[0].screen.screen_text().splitlines()[0])
        assert av.actor.zone==target

    async def leave(connection: tuple,label: str) -> None:
        caller,writer,task,session=connection
        mark=len(caller.output)
        await caller.write(b"\x18y")
        await wait(lambda:b"Left Blacksite." in caller.output)
        await caller.write(b" ")
        await wait(lambda:b"Available doors" in re.sub(rb"\x1b\[[0-?]*[ -/]*[@-~]",b"",bytes(caller.output[mark:])))
        await caller.write(b"b")
        await wait(lambda:b"You return to the node." in caller.output)
        (root/(label+".ans")).write_bytes(caller.output)
        writer.close()
        await writer.wait_closed()
        await task
        connections.remove(connection)

    try:
        # A real second caller reaches the plaza through the same authored exits.
        a = await open_caller(80,24,True,show)
        b = await open_caller(132,50,True,False)
        await travel(b,"vatside-clinics")
        await travel(b,"core-plaza")
        await walk(b,(85,3))
        for width,height in ((80,24),(132,50)):
            if width==132:
                # Handler alternates account IDs: the observer stays connected.
                next_user=0
                a=await open_caller(width,height,False,show)
            await travel(a,"vatside-clinics")
            assert "CONTESTED" in a[0].screen.screen_text()
            await travel(a,"core-plaza")
            assert "SAFE" in a[0].screen.screen_text()
            await wait(lambda:any(o["id"]==avatar(a).actor.id for o in manager.sim.views[b[3].id].previous["body"]["actors"]))
            report(f"PASS {width}x{height}: Hall -> Clinic Row -> Plaza, observer sees arrival")
            await travel(a,"core-tram-hub")
            await travel(a,"vatside-clinics")
            await travel(a,"core-plaza")
            await travel(a,"sodium-row")
            await travel(a,"sodium-tin-halo")
            assert "POCKET" in a[0].screen.screen_text()
            await a[0].write(b"m")
            await wait(lambda:"CITY MAP" in a[0].screen.screen_text())
            await a[0].write(b"\r")
            await wait(lambda:"KNOWN EXITS" in a[0].screen.screen_text())
            await a[0].write(b"\x1b")
            await wait(lambda:"The Tin Halo" in a[0].screen.screen_text())
            results.append({"size":[width,height],"walked":True,"scheduled_tram":True,"observer":True,"map":True})
            report(f"PASS {width}x{height}: Neon Stair -> Tin Halo pocket, visited map overview")
            # Return the same character to the Hall for the next terminal size.
            if width==80:
                for target in ("sodium-row","core-plaza","vatside-clinics","vatside-wake-hall"):
                    await travel(a,target)
            await leave(a,f"city-{width}x{height}")
        await leave(b,"observer-132x50")
        assert not failures,failures
        (root/"result.json").write_text(json.dumps({"passed":True,"transport":"NetBBS Telnet native stdio","runs":results},indent=2))
    finally:
        for _,writer,task,_ in connections:
            writer.close()
            task.cancel()
        await node.stop()
        lane.close()
        await service.stop()
        db.close()


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--root",type=Path,required=True)
    parser.add_argument("--door-python",type=Path,required=True)
    parser.add_argument("--show",action="store_true")
    args=parser.parse_args()
    asyncio.run(accept(args.root,args.door_python,args.show))
