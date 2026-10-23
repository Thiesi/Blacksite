"""S06: two real NetBBS native doors, shared movement and wall occlusion.

Run with the local NetBBS venv (SSH/web extras), passing this checkout's
installed door interpreter. All accounts, listeners and worlds belong
to --root. --show forwards caller A's actual ANSI to a real terminal.
"""

import argparse
import asyncio
import json
import os
from pathlib import Path
import time
from collections.abc import Callable

import asyncssh

from accept_s04_netbbs import (Caller, Database, DatabaseLane, DoorProfile,
    FakeTerminal, REPO, SSHServer, TelnetServer, browse_doors, create_door, create_user)
from blacksite.admin.client import request
from blacksite.server.app import Server


class ZoneCaller(Caller):
    def __init__(self, read: object, write: object, width: int, height: int, show: bool = False) -> None:
        super().__init__(read, write)
        self.screen = FakeTerminal(width, height)
        self.show = show
        self.shown = 0
        self.display_write: Callable[[bytes], object] = lambda data: os.write(1, data)

    def replay(self) -> None:
        super().replay()
        if self.show and self.offset is not None:
            start = max(self.shown, self.output.find(b"\x1b[?1049h"))
            self.display_write(bytes(self.output[start:self.offset]))
            self.shown = self.offset

    async def until(self, condition: object, timeout: float = 5) -> None:
        async with asyncio.timeout(timeout):
            while not condition():
                chunk = await self.read()
                if not chunk:
                    raise AssertionError("door transport ended before the expected screen")
                self.output.extend(chunk)
                self.replay()


async def accept(root: Path, door_python: Path, show: bool) -> None:
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    service = Server(root / "world", tcp=True, spawn_zone="vatside-wake-hall")
    await service.start()
    db = Database(root / "node.db")
    lane = DatabaseLane(db.path)
    users: dict[str, object] = {}
    owner = create_user(db, "s06owner", password="LocalProbe-S06", user_level=10)
    create_door(db, "Blacksite", str(door_python.absolute()), args=("-m", "blacksite.door"), creator=owner,
        profile=DoorProfile(install_dir=str(REPO), encoding="utf-8", max_sessions=16,
            multinode_certified=True, time_limit=900,
            environment={"DOOR_BLACKSITE_INSTALL_DIR": str(service.install_dir)}).validate())
    failures: list[str] = []

    async def handler(session: object, key: str) -> None:
        try:
            await browse_doors(session, lane, users[key])
            await session.write_line("You return to the node.")
        except Exception as exc:
            failures.append(repr(exc))
            raise

    telnet = TelnetServer("127.0.0.1", 0, lambda session: handler(session, "a"), terminal_type_wait_seconds=.1)
    ssh = SSHServer(host="127.0.0.1", port=0, db=db, session_handler=lambda session: handler(session, "b"))
    results: list[dict[str, object]] = []
    try:
        await telnet.start()
        await ssh.start()
        for width, height in ((80, 24), (132, 50)):
            users["a"] = create_user(db, f"s06a{width}", password="LocalProbe-S06", user_level=10)
            users["b"] = create_user(db, f"s06b{width}", password="LocalProbe-S06", user_level=10)
            reader, writer = await asyncio.open_connection("127.0.0.1", telnet.port)
            try:
                writer.write(b"\xff\xfb\x1f\xff\xfa\x1f" + width.to_bytes(2, "big") + height.to_bytes(2, "big") + b"\xff\xf0")
                writer.write(b"\xff\xfb\x18\xff\xfa\x18\x00xterm-256color\xff\xf0")
                await writer.drain()

                async def send_a(data: bytes) -> None:
                    writer.write(data)
                    await writer.drain()

                a = ZoneCaller(lambda: reader.read(65536), send_a, width, height, show)
                await a.expect("Available doors")
                await send_a(b"\x1b[B\r")
                await a.expect("Wake Hall")
                async with asyncssh.connect("127.0.0.1", ssh.port, username=users["b"].username,
                        password="LocalProbe-S06", known_hosts=None) as connection:
                    async with connection.create_process(term_type="xterm-256color", term_size=(80, 24), encoding=None) as proc:
                        async def send_b(data: bytes) -> None:
                            proc.stdin.write(data)
                            await proc.stdin.drain()

                        b = ZoneCaller(lambda: proc.stdout.read(65536), send_b, 80, 24)
                        await b.expect("Available doors")
                        await send_b(b"\x1b[B\r")
                        await b.expect("Wake Hall")

                        def actor(key: str) -> object:
                            return next(value for value in service.core.world.actors.values()
                                        if value.handle == users[key].username)

                        async with asyncio.timeout(5):
                            while len(service.core.world.actors) < 2:
                                await asyncio.sleep(.01)
                        aa, bb = actor("a"), actor("b")

                        def at(caller: ZoneCaller, observer: object, target: object, glyph: str) -> bool:
                            avatar = next(value for value in service.core.simulation.avatars.values() if value.actor is observer)
                            view = avatar.perception.viewport
                            if view is None:
                                return False
                            x, y = 1 + target.x - view["x"], 1 + target.y - view["y"]
                            return 0 <= x < caller.screen.width and 0 <= y < caller.screen.height and caller.screen.cell(x, y) == glyph

                        await a.until(lambda: at(a, aa, bb, "☺"))
                        await b.until(lambda: at(b, bb, aa, "☺"))
                        before = aa.position
                        began = time.monotonic()
                        for _ in range(12):
                            await send_a(b"\x1b[B")
                            await asyncio.sleep(.1)
                        walked = aa.y - before[1]
                        wall = time.monotonic() - began
                        assert 5 <= walked <= 7, (walked, wall)
                        await asyncio.sleep(.2)  # Let the final walking cooldown expire.
                        before = aa.position
                        began = time.monotonic()
                        for _ in range(6):
                            await send_a(b"\x1b[1;2A")
                            await asyncio.sleep(.1)
                        sprinted = before[1] - aa.y
                        sprint_wall = time.monotonic() - began
                        assert sprinted >= 5 and aa.stamina < aa.stamina_max, (before, aa.position, sprinted, aa.stamina, aa.stamina_max, sprint_wall)
                        assert sprinted / sprint_wall > walked / wall
                        print(f"PASS speed {width}x{height}: walk {walked}/{wall:.2f}s, sprint {sprinted}/{sprint_wall:.2f}s, STA {aa.stamina}", flush=True)
                        await asyncio.sleep(.2)
                        await a.until(lambda: at(a, aa, aa, "@"))

                        async def drive(caller: ZoneCaller, moving: object, destination: tuple[int, int]) -> None:
                            # One key per observed server move; no client prediction.
                            for axis, target in (("y", destination[1]), ("x", destination[0])):
                                while getattr(moving, axis) != target:
                                    delta = 1 if getattr(moving, axis) < target else -1
                                    direction = (b"\x1b[B" if delta > 0 else b"\x1b[A") if axis == "y" else (b"\x1b[C" if delta > 0 else b"\x1b[D")
                                    wanted = getattr(moving, axis) + delta
                                    await caller.write(direction)
                                    try:
                                        async with asyncio.timeout(3):
                                            while getattr(moving, axis) != wanted:
                                                await asyncio.sleep(.01)
                                    except TimeoutError as exc:
                                        raise AssertionError((moving.position, destination, axis, wanted, moving.cooldowns)) from exc
                                    await caller.until(lambda: at(caller, moving, moving, "@"))
                                    await asyncio.sleep(.2)

                        await drive(a, aa, (18, 14))
                        await drive(b, bb, (17, 14))
                        await drive(a, aa, (22, 14))
                        await b.until(lambda: at(b, bb, aa, "☺"))
                        await drive(a, aa, (22, 13))
                        await b.until(lambda: "☺" not in b.screen.screen_text())
                        avatar_b = next(value for value in service.core.simulation.avatars.values() if value.actor is bb)
                        view = avatar_b.perception.viewport
                        assert avatar_b.perception.tiles[5 - view["y"]][7 - view["x"]] == -2
                        style = b.screen.styles[(8 - view["x"], 6 - view["y"])]
                        assert style.split(";")[1] == "2", style
                        idle_p99 = None
                        if width == 132:
                            # Sixty real seconds with both native door sessions attached.
                            # The acceptance budget is for idle work. Begin a fresh
                            # timing window after the deliberate movement workload.
                            print(f"Movement-phase tick p99: {service.core.loop.timing()['p99_ms']:.3f} ms", flush=True)
                            service.core.loop.timings.clear()
                            await asyncio.sleep(60)
                            status = await request(service.install_dir, "status")
                            idle_p99 = status["tick_p99_ms"]
                            assert idle_p99 < 5, status
                            print(f"PASS idle 60s: two-player tick p99 {idle_p99:.3f} ms", flush=True)
                        for caller in (a, b):
                            mark = len(caller.output)
                            await caller.write(b"\x18y")
                            await caller.expect("Karst keeps your place.", mark)
                            await caller.expect("Left Blacksite.", mark)
                            await caller.write(b" ")
                            await caller.expect("Available doors", mark)
                            await caller.write(b"b")
                            await caller.expect("You return to the node.")
                        for name, caller in (("telnet", a), ("ssh", b)):
                            (root / f"{name}-{width}x{height}.ans").write_bytes(caller.output)
                        results.append({"telnet": [width, height], "ssh": [80, 24], "walk_tiles": walked,
                            "walk_seconds": wall, "sprint_tiles": sprinted, "sprint_seconds": sprint_wall,
                            "wall_occlusion": True, "remembered_dimmed": True, "tick_p99_ms": idle_p99})
                        print(f"PASS shared zone {width}x{height} + SSH 80x24: movement, sprint, STA, wall, memory, clean exit", flush=True)
            finally:
                writer.close()
                await writer.wait_closed()
        assert not failures, failures
        (root / "result.json").write_text(json.dumps({"passed": True, "runs": results}, indent=2) + "\n")
    finally:
        await ssh.stop()
        await telnet.stop()
        lane.close()
        db.close()
        await service.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--door-python", type=Path, required=True)
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()
    asyncio.run(accept(args.root, args.door_python, args.show))
