"""Run the registered door through NetBBS's real picker and three transports.

Use the local NetBBS checkout's venv (with its SSH/web extras), passing
Blacksite's venv interpreter as --door-python. All databases, profiles
and listeners are private to --root. No existing node is modified.
"""

import argparse
import asyncio
import base64
import json
from pathlib import Path
import re
import sys
import time

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO))

import aiohttp
import asyncssh
from netbbs.auth.users import create_user
from netbbs.doors.profiles import DoorProfile
from netbbs.doors.registry import create_door
from netbbs.net.door_flow import browse_doors
from netbbs.net.ssh import SSHServer
from netbbs.net.telnet import TelnetServer
from netbbs.net.web import WebServer
from netbbs.storage.database import Database
from netbbs.storage.execution import DatabaseLane

from blacksite.server.app import Server
from tests.fake_terminal import FakeTerminal


class Caller:
    def __init__(self, read: object, write: object) -> None:
        self.read = read
        self.write = write
        self.output = bytearray()
        self.screen: FakeTerminal | None = None
        self.offset: int | None = None
        self.screen_done = False

    def replay(self) -> None:
        if self.screen is None or self.screen_done:
            return
        if self.offset is None:
            start = self.output.find(b"\x1b[?1049h")
            if start < 0:
                return
            self.offset = start
        end = self.output.find(b"\x1b[?1049l", self.offset)
        finish = self.output.find(b"\r\n", end) if end >= 0 else -1
        until = finish + 2 if finish >= 0 else len(self.output)
        self.screen.write(bytes(self.output[self.offset:until]))
        self.offset = until
        self.screen_done = finish >= 0

    async def expect(self, text: str, after: int = 0, timeout: float = 10) -> None:
        try:
            async with asyncio.timeout(timeout):
                while True:
                    plain = re.sub(rb"\x1b\[[0-?]*[ -/]*[@-~]", b"", bytes(self.output[after:]))
                    if text.encode() in plain:
                        return
                    if self.screen is not None and len(self.output) > after and text in self.screen.screen_text():
                        return
                    chunk = await self.read()
                    if not chunk:
                        raise AssertionError(f"connection ended before {text!r}: {plain[-1200:]!r}")
                    self.output.extend(chunk)
                    self.replay()
        except asyncio.TimeoutError as exc:
            raise AssertionError(f"timed out before {text!r}: {plain[-2000:]!r}") from exc

    async def play(self, name: str, width: int, height: int, root: Path, service: Server | None = None) -> None:
        self.screen = FakeTerminal(width, height)
        await self.expect("Available doors")
        mark = len(self.output)
        await self.write(b"\x1b[B\r")
        await self.expect("BLACKSITE", mark)
        # Any first frame can beat the handshake. Help must survive welcome.
        mark = len(self.output)
        await self.write(b"?")
        await self.expect("HELP", mark)
        mark = len(self.output)
        await self.write(b"\x1b[6~")
        await self.expect("Page 2/", mark)
        mark = len(self.output)
        await self.write(b"\x1b\x0c")
        await self.expect("BLACKSITE", mark)
        mark = len(self.output)
        if service is not None:
            started = time.monotonic()
            await service.stop()
            await self.expect("The city is dark right now.", mark)
            await self.expect("Karst keeps your place.", mark, timeout=65)
            elapsed = time.monotonic() - started
            assert 59 <= elapsed < 65, elapsed
            print(f"PASS service loss: countdown then clean exit after {elapsed:.3f}s", flush=True)
        else:
            await self.write(b"\x18y")
            await self.expect("Karst keeps your place.", mark)
        await self.expect("Left Blacksite.", mark)
        mark = len(self.output)
        await self.write(b" ")
        await self.expect("Available doors", mark)
        await self.write(b"b")
        await self.expect("You return to the node.")
        (root / f"{name}-{width}x{height}.ans").write_bytes(self.output)
        print(f"PASS {name} {width}x{height}: picker, title, help paging, Esc, clean exit, picker redraw", flush=True)


async def accept(root: Path, door_python: Path) -> None:
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    service = Server(root / "world", tcp=True)
    await service.start()
    db = Database(root / "node.db")
    lane = DatabaseLane(db.path)
    user = create_user(db, "s04caller", password="LocalProbe-S04", user_level=10)
    create_door(db, "Blacksite", str(door_python.resolve()), args=("-m", "blacksite.door"), creator=user,
        profile=DoorProfile(install_dir=str(REPO), encoding="utf-8",
            max_sessions=16, multinode_certified=True, time_limit=900,
            environment={"DOOR_BLACKSITE_INSTALL_DIR": str(service.install_dir)}).validate())
    failures = []

    async def handler(session: object) -> None:
        session.node_display_name = "S04 acceptance"
        try:
            await browse_doors(session, lane, user)
            await session.write_line("You return to the node.")
        except Exception as exc:
            failures.append(repr(exc))
            raise

    telnet = TelnetServer("127.0.0.1", 0, handler, terminal_type_wait_seconds=.1)
    ssh = SSHServer(host="127.0.0.1", port=0, db=db, session_handler=handler)
    web = WebServer(host="127.0.0.1", port=0, session_handler=handler)
    try:
        await telnet.start()
        await ssh.start()
        await web.start()
        for width, height in ((80, 24), (132, 50)):
            reader, writer = await asyncio.open_connection("127.0.0.1", telnet.port)
            try:
                writer.write(b"\xff\xfb\x1f\xff\xfa\x1f" + width.to_bytes(2, "big") + height.to_bytes(2, "big") + b"\xff\xf0")
                writer.write(b"\xff\xfb\x18\xff\xfa\x18\x00xterm-256color\xff\xf0")
                await writer.drain()

                async def send(data: bytes) -> None:
                    writer.write(data)
                    await writer.drain()

                await Caller(lambda: reader.read(65536), send).play("telnet", width, height, root)
            finally:
                writer.close()
                await writer.wait_closed()
            async with asyncssh.connect("127.0.0.1", ssh.port, username=user.username,
                    password="LocalProbe-S04", known_hosts=None) as connection:
                async with connection.create_process(term_type="xterm-256color", term_size=(width, height), encoding=None) as proc:
                    async def send_ssh(data: bytes) -> None:
                        proc.stdin.write(data)
                        await proc.stdin.drain()

                    await Caller(lambda: proc.stdout.read(65536), send_ssh).play("ssh", width, height, root)
            async with aiohttp.ClientSession() as client:
                async with client.ws_connect(f"http://127.0.0.1:{web.port}/ws") as ws:
                    door_stream: int | None = None
                    await ws.send_json({"type": "resize", "cols": width, "rows": height})

                    async def read_web() -> bytes:
                        nonlocal door_stream
                        while True:
                            message = await ws.receive_json()
                            if message.get("type") == "door_mode":
                                door_stream = message.get("stream") if message.get("active") else None
                            if message.get("type") == "door_output":
                                door_stream = message["stream"]
                                return base64.b64decode(message["data"])
                            if message.get("type") == "output":
                                return message["data"].encode("utf-8")

                    async def send_web(data: bytes) -> None:
                        if door_stream is not None:
                            await ws.send_json({"type": "door_key", "stream": door_stream,
                                                "data": data.decode("utf-8")})
                        else:
                            await ws.send_json({"type": "key", "data": data.decode("utf-8")})

                    await Caller(read_web, send_web).play("web", width, height, root, service if width == 132 else None)
        assert not failures, failures
        (root / "result.json").write_text(json.dumps({"transports": ["telnet", "ssh", "web"],
            "sizes": [[80, 24], [132, 50]], "passed": True}, indent=2) + "\n", encoding="utf-8")
    finally:
        await web.stop()
        await ssh.stop()
        await telnet.stop()
        lane.close()
        db.close()
        await service.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--door-python", type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(accept(args.root, args.door_python))
