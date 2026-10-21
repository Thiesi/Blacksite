"""S05 operator contracts, real local CLI and shutdown behavior."""

import asyncio
import json
import os
from pathlib import Path
import sys

import pytest

from blacksite.admin.__main__ import main, rotate
from blacksite.admin.client import request
from blacksite.server.app import Server
from blacksite.server.protocol import Frame, encode, read_frame
from tests.harness import HeadlessServer


def test_who_lists_sessions_and_connected_time() -> None:
    server = HeadlessServer()
    caller = server.connect()
    from blacksite.server.admin_endpoint import dispatch
    from tests.harness import ADMIN_SECRET, hello
    operator = server.connect(frame=hello(secret=ADMIN_SECRET))
    server.frames_for(operator)
    server.clock.advance(35)
    dispatch(operator.session, Frame("admin.who"), server.core.sessions,
             server.core.status, server.core.request_stop, lambda row: None)
    rows = json.loads(server.frames_for(operator)[0].data["body"]["lines"][0])
    assert rows == [{"handle": caller.session.door_info["handle"], "player_name": None,
                     "zone": None, "connected_s": 3.5}]


def test_status_json_shape_and_stop_sends_bye_then_exits(scratch_dir: Path) -> None:
    async def scenario() -> None:
        server = Server(scratch_dir, tcp=True)
        await server.start()
        # Use a real caller and the real foreground lifecycle after bootstrap.
        from blacksite.server.auth import sign
        info = {"user_id": 42, "handle": "Caller界"}
        secret = bytes.fromhex((scratch_dir / "secrets/door.secret").read_text().strip())
        from blacksite.server.transport import connect
        reader, writer = await connect(scratch_dir)
        writer.write(encode(Frame("hello", {"proto": 1, "door_info": info, "hmac": sign(info, secret),
            "client_version": "test", "caps": {"width": 80, "height": 24, "tier": "256", "unicode": True}})))
        await writer.drain()
        assert (await read_frame(reader)).type == "welcome"
        try:
            result = await request(scratch_dir, "status")
            assert {"uptime_s", "players", "active_zones", "tick_p50_ms", "tick_p99_ms",
                    "persist_lag_s", "content_hash", "season"} <= result.keys()
            assert result["players"] == 1 and len(result["content_hash"]) == 64
            assert (await request(scratch_dir, "who"))[0]["handle"] == "Caller界"
            pidfile = scratch_dir / "run/blacksite.pid"
            assert int(pidfile.read_text()) == os.getpid()
            with pytest.raises(RuntimeError):
                rotate(scratch_dir)
            assert await request(scratch_dir, "stop") == {"ok": True}
            assert server.core.stop_requested
            await server.stop()
            assert (await read_frame(reader)).data["reason"] == "maintenance"
            assert list((scratch_dir / "run").iterdir()) == []
        finally:
            writer.close()
            await writer.wait_closed()
            await server.stop()
    asyncio.run(scenario())


def test_missing_socket_message_exit_1(scratch_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["status", "--install-dir", str(scratch_dir)]) == 1
    error = capsys.readouterr().err
    assert "service not running; start it with" in error and len(error.splitlines()) == 1
    assert not (scratch_dir / "secrets").exists()


def test_validate_runs_validator_and_offline_rotation(scratch_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--install-dir", str(scratch_dir), "validate", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["ok"]
    override = scratch_dir / "content.local" / "items.json"
    override.parent.mkdir()
    override.write_text("not JSON", encoding="utf-8")
    assert main(["validate", "--json", "--install-dir", str(scratch_dir)]) == 1
    assert json.loads(capsys.readouterr().out)["problems"]
    assert main(["--install-dir", str(scratch_dir), "secrets", "rotate", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == {"rotated": True}
    first = (scratch_dir / "secrets/admin.secret").read_text()
    rotate(scratch_dir)
    assert (scratch_dir / "secrets/admin.secret").read_text() != first
    assert len(bytes.fromhex(first.strip())) == 32


def test_real_console_alias_serve_status_stop(scratch_dir: Path) -> None:
    async def scenario() -> None:
        env = {**os.environ, "BLACKSITE_INSTALL_DIR": str(scratch_dir)}
        process = await asyncio.create_subprocess_exec(sys.executable, "-m", "blacksite", "serve", "--tcp",
            env=env, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        try:
            async with asyncio.timeout(10):
                while not (scratch_dir / "run/blacksite.pid").exists():
                    if process.returncode is not None:
                        raise AssertionError((await process.stderr.read()).decode())
                    await asyncio.sleep(.05)
            client = await asyncio.create_subprocess_exec(sys.executable, "-m", "blacksite", "admin", "status", "--json",
                env=env, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            output, errors = await asyncio.wait_for(client.communicate(), 10)
            assert client.returncode == 0 and not errors
            assert json.loads(output)["players"] == 0
            assert await request(scratch_dir, "stop") == {"ok": True}
            output, errors = await asyncio.wait_for(process.communicate(), 10)
            assert process.returncode == 0 and not errors
            assert list((scratch_dir / "run").iterdir()) == []
        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()
    asyncio.run(scenario())
