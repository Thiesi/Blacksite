"""S07: real NetBBS Wake, saved character/restart and 120s sleeper recovery.

Run with NetBBS's venv (SSH/web extras). --show emits caller ANSI into
the running terminal. Every account, listener and world is private.
"""

import argparse
import asyncio
import json
from pathlib import Path
import time

from accept_s04_netbbs import Database, DatabaseLane, DoorProfile, REPO, TelnetServer, browse_doors, create_door, create_user
from accept_s06_netbbs import ZoneCaller
from blacksite.admin.client import request
from blacksite.server.app import Server


async def accept(root: Path, door_python: Path, show: bool) -> None:
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    install = root / "world"
    service = Server(install, tcp=True)
    await service.start()
    db = Database(root / "node.db")
    lane = DatabaseLane(db.path)
    user = create_user(db, "s07caller", password="LocalProbe-S07", user_level=10)
    create_door(db, "Blacksite", str(door_python.absolute()), args=("-m", "blacksite.door"), creator=user,
                profile=DoorProfile(install_dir=str(REPO), encoding="utf-8", max_sessions=16,
                    multinode_certified=True, time_limit=900,
                    environment={"DOOR_BLACKSITE_INSTALL_DIR": str(install)}).validate())
    failures: list[str] = []

    async def handler(session: object) -> None:
        try:
            await browse_doors(session, lane, user)
            await session.write_line("You return to the node.")
        except Exception as exc:
            failures.append(repr(exc))
            raise

    node = TelnetServer("127.0.0.1", 0, handler, terminal_type_wait_seconds=.1)
    await node.start()
    runs: list[dict[str, object]] = []

    async def open_caller(width: int, height: int) -> tuple[ZoneCaller, asyncio.StreamWriter]:
        reader, writer = await asyncio.open_connection("127.0.0.1", node.port)
        async def send(data: bytes) -> None:
            writer.write(data)
            await writer.drain()
        writer.write(b"\xff\xfb\x1f\xff\xfa\x1f" + width.to_bytes(2,"big") + height.to_bytes(2,"big") + b"\xff\xf0")
        writer.write(b"\xff\xfb\x18\xff\xfa\x18\x00xterm-256color\xff\xf0")
        await writer.drain()
        caller = ZoneCaller(lambda: reader.read(65536), send, width, height, show)
        await caller.expect("Available doors")
        await caller.write(b"\x1b[B\r")
        return caller, writer

    async def leave(caller: ZoneCaller, writer: asyncio.StreamWriter, name: str) -> None:
        mark = len(caller.output)
        await caller.write(b"\x18y")
        await caller.expect("Karst keeps your place.", mark)
        await caller.expect("Left Blacksite.", mark)
        await caller.write(b" ")
        await caller.expect("Available doors", mark)
        await caller.write(b"b")
        await caller.expect("You return to the node.")
        (root / f"{name}.ans").write_bytes(caller.output)
        writer.close()
        await writer.wait_closed()
        async with asyncio.timeout(5):
            while any(s.role == "caller" for s in service.core.sessions.active.values()):
                await asyncio.sleep(.01)

    def manager() -> object:
        return service.core.characters

    def wake() -> object:
        return next(iter(manager().wakes.values()))

    def avatar() -> object:
        return next(iter(manager().sim.avatars.values()))

    try:
        caller, writer = await open_caller(80,24)
        began = time.monotonic()
        await caller.until(lambda: "Choose your archetype" in caller.screen.screen_text())
        await caller.write(b"\x1b[B")
        await caller.until(lambda: "native rig" in caller.screen.screen_text())
        await caller.write(b"\r")
        await caller.until(lambda: "Name (Enter keeps default):" in caller.screen.screen_text())
        await caller.write(b"\r")
        await caller.until(lambda: "VANTONGEREN" in caller.screen.screen_text())
        while wake().stage == "briefing":
            current = wake().screen, wake().page
            await caller.write(b" ")
            async with asyncio.timeout(3):
                while wake().stage == "briefing" and (wake().screen,wake().page) == current:
                    await asyncio.sleep(.01)
            if wake().stage == "briefing":
                marker = f"Briefing {wake().screen}/3 ({wake().page + 1}/"
                await caller.until(lambda: marker in caller.screen.screen_text())
            else:
                await caller.until(lambda: "Recruiter cards" in caller.screen.screen_text())
        # None is the default; two Up keys reach Unmoored, at 80x24.
        for _ in range(2):
            cursor = wake().cursor
            await caller.write(b"\x1b[A")
            async with asyncio.timeout(3):
                while wake().cursor == cursor:
                    await asyncio.sleep(.01)
            await asyncio.sleep(.12)
        await caller.until(lambda: "Here's your lease." in caller.screen.screen_text())
        await caller.write(b"\r")
        await caller.until(lambda: "Chits 200" in caller.screen.screen_text())
        elapsed = time.monotonic() - began
        assert elapsed < 300, elapsed
        player = next(iter(manager().players.values()))
        assert player.archetype == "ghost" and player.standing == {"unmoored":10}
        assert player.health == 90 and player.stamina == 77
        await caller.write(b"P")
        await caller.until(lambda: "CHARACTER" in caller.screen.screen_text() and "Ghost" in caller.screen.screen_text())
        await caller.write(b"\x1b")
        await caller.until(lambda: "Wake Hall" in caller.screen.screen_text() and "Chits 200" in caller.screen.screen_text())
        before = avatar().actor.position
        await caller.write(b"\x1b[B")
        async with asyncio.timeout(3):
            while avatar().actor.position == before:
                await asyncio.sleep(.01)
        tile, pid = avatar().actor.position, player.id
        await leave(caller,writer,"wake-80x24")
        print(f"PASS Wake Telnet 80x24: Ghost, handle, three briefings, Unmoored, kit/200 chits, P, {elapsed:.2f}s",flush=True)
        runs.append({"size":[80,24],"wake_seconds":elapsed,"saved_tile":tile})

        for width,height,restart in ((80,24,False),(132,50,True)):
            if restart:
                await service.stop()
                service = Server(install,tcp=True)
                await service.start()
            caller,writer = await open_caller(width,height)
            await caller.until(lambda: "Chits 200" in caller.screen.screen_text())
            assert avatar().actor.id == pid and avatar().actor.position == tile
            assert not manager().wakes
            rows = await request(install,"who")
            assert rows[0]["player_name"] == user.username
            await caller.write(b"P")
            await caller.until(lambda: "Ghost" in caller.screen.screen_text())
            await caller.write(b"\x1b")
            await caller.until(lambda: "Chits 200" in caller.screen.screen_text())
            if restart:
                # S08 has not landed: server-side scenario setup, not a travel
                # claim. Place the actual physical body in contested Clinic Row.
                av = avatar();session = next(s for s in service.core.sessions.active.values() if s.role == "caller")
                service.core.world.zones[av.zone].deactivate(session.id,service.clock.now_tick())
                service.core.world.enter(av.actor,"vatside-clinics",(30,18))
                av.zone = session.subscribed = "vatside-clinics"
                service.core.world.zones[av.zone].activate(session.id,service.clock.now_tick())
                await caller.until(lambda: "Clinic Row" in caller.screen.screen_text())
            await leave(caller,writer,f"return-{width}x{height}")
            print(f"PASS saved return {width}x{height}: same tile/numbers, skip Wake, restart={restart}",flush=True)
            runs.append({"size":[width,height],"restart":restart,"same_character":True})

        assert service.core.world.actors[pid].stance == "sleeper"
        # Real elapsed time, not an accelerated simulation clock.
        await asyncio.sleep(120)
        caller,writer = await open_caller(132,50)
        await caller.until(lambda: "Wake Hall" in caller.screen.screen_text() and "Chits 200" in caller.screen.screen_text())
        player = manager().players[pid]
        assert player.zone == "vatside-wake-hall" and player.clone_debt == 0
        await leave(caller,writer,"recovered-132x50")
        print("PASS contested logout: actual 120s, Wake Hall recovery, no combat debt",flush=True)
        assert not failures, failures
        (root/"result.json").write_text(json.dumps({"passed":True,"runs":runs,"sleeper_wait_seconds":120,"scenario_placement":"server setup; S08 travel absent"},indent=2)+"\n")
    finally:
        await node.stop()
        lane.close();db.close()
        await service.stop()


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",type=Path,required=True)
    parser.add_argument("--door-python",type=Path,required=True)
    parser.add_argument("--show",action="store_true")
    args=parser.parse_args()
    asyncio.run(accept(args.root,args.door_python,args.show))
