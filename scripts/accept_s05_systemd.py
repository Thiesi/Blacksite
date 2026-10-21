"""S05 acceptance on an isolated Linux systemd host with local NetBBS.

The unit must already point at an installed Blacksite wheel and a fresh
service directory owned by the current non-root account. Only the named
test unit is started/stopped; existing nodes are never opened.
"""

import argparse
import asyncio
import json
import os
from pathlib import Path

from accept_s04_netbbs import (Caller, Database, DatabaseLane, DoorProfile,
    FakeTerminal, TelnetServer, browse_doors, create_door, create_user)


async def command(*args: str) -> str:
    child = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE,
                                                stderr=asyncio.subprocess.PIPE)
    output, errors = await asyncio.wait_for(child.communicate(), 20)
    if child.returncode:
        raise AssertionError(f"command failed ({child.returncode}): {args!r}: {errors.decode()}")
    return output.decode()


async def accept(root: Path, install: Path, python: Path, unit: str) -> None:
    assert os.getuid() != 0, "acceptance and the service must use a non-root account"
    root.mkdir(parents=True)
    db = Database(root / "node.db")
    lane = DatabaseLane(db.path)
    user = create_user(db, "s05caller", password="LocalProbe-S05", user_level=10)
    create_door(db, "Blacksite", str(python), args=("-m", "blacksite.door"), creator=user,
        profile=DoorProfile(install_dir=str(root), encoding="utf-8", max_sessions=16,
            multinode_certified=True, time_limit=300,
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

    async def admin(verb: str) -> object:
        return json.loads(await command(str(python), "-m", "blacksite", "admin", "--install-dir", str(install), verb, "--json"))

    try:
        await node.start()
        for width, height in ((80, 24), (132, 50)):
            await command("sudo", "systemctl", "start", unit)
            async with asyncio.timeout(10):
                while not (install / "run/blacksite.pid").exists():
                    await asyncio.sleep(.05)
            status = await admin("status")
            assert status["players"] == 0
            pid = int((install / "run/blacksite.pid").read_text())
            reader, writer = await asyncio.open_connection("127.0.0.1", node.port)
            try:
                writer.write(b"\xff\xfb\x1f\xff\xfa\x1f" + width.to_bytes(2, "big") + height.to_bytes(2, "big") + b"\xff\xf0")
                writer.write(b"\xff\xfb\x18\xff\xfa\x18\x00xterm-256color\xff\xf0")
                await writer.drain()

                async def send(data: bytes) -> None:
                    writer.write(data)
                    await writer.drain()

                caller = Caller(lambda: reader.read(65536), send)
                caller.screen = FakeTerminal(width, height)
                await caller.expect("Available doors")
                await send(b"\x1b[B\r")
                await caller.expect("BLACKSITE")
                # The title precedes hello; wait for the actual login in who.
                async with asyncio.timeout(10):
                    while not (rows := await admin("who")):
                        await asyncio.sleep(.05)
                assert rows[0]["handle"] == "s05caller" and rows[0]["player_name"] is None
                assert (await admin("status"))["players"] == 1
                mark = len(caller.output)
                assert await admin("stop") == {"ok": True}
                await caller.expect("The city is dark right now.", mark)
                async with asyncio.timeout(12):
                    while (install / "run/blacksite.pid").exists():
                        await asyncio.sleep(.05)
                assert list((install / "run").iterdir()) == []
                async with asyncio.timeout(5):
                    while True:
                        try:
                            os.kill(pid, 0)
                        except ProcessLookupError:
                            break
                        await asyncio.sleep(.05)
                await send(b"\x18y")
                await caller.expect("Karst keeps your place.", mark)
                await caller.expect("Left Blacksite.", mark)
                await send(b" ")
                await caller.expect("Available doors", mark)
                await send(b"b")
                await caller.expect("You return to the node.")
                (root / f"netbbs-{width}x{height}.ans").write_bytes(caller.output)
            finally:
                writer.close()
                await writer.wait_closed()
            await command("sudo", "systemctl", "restart", unit)
            async with asyncio.timeout(10):
                while not (install / "run/blacksite.pid").exists():
                    await asyncio.sleep(.05)
            assert (await admin("status"))["players"] == 0
            await command("sudo", "systemctl", "stop", unit)
            print(f"PASS Linux systemd + NetBBS {width}x{height}: status, who, maintenance stop, cleanup, restart", flush=True)
        assert not failures, failures
        assert (await command("systemctl", "is-enabled", unit)).strip() == "enabled"
        (root / "result.json").write_text(json.dumps({"host": "Linux systemd", "sizes": [[80, 24], [132, 50]],
            "wheel_installed": True, "non_root": True, "passed": True}, indent=2) + "\n")
    finally:
        await command("sudo", "systemctl", "stop", unit)
        await node.stop()
        lane.close()
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--install-dir", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--unit", required=True)
    args = parser.parse_args()
    # Resolving a venv's Python symlink would launch the base interpreter.
    asyncio.run(accept(args.root.resolve(), args.install_dir.resolve(), args.python.absolute(), args.unit))
