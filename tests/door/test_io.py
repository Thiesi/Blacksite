"""Local service integration, reconnect policy and terminal lifecycle."""

import asyncio
import json
import os
import sys
from pathlib import Path

import pytest

from blacksite.door.client import run
from blacksite.door.connection import Connection, Reconnect
from blacksite.door.doorinfo import DoorInfo
from blacksite.door.terminal import ENTER, LEAVE
from blacksite.server.app import Server
from blacksite.server.protocol import Frame
from tests.fake_terminal import FakeTerminal


def test_reconnect_backoff_then_dark() -> None:
    retry = Reconnect(started=0)
    now = 0
    attempts = []
    while retry.remaining(now) > 0:
        retry.failed(now)
        attempts.append(retry.next_at - now)
        now = retry.next_at
    assert attempts == [1, 2, 4, 8, 16, 29]
    assert now == 60
    retry.reset()
    assert retry.started is None and retry.attempt == 0


def test_two_pumps_connect_help_exit_and_restore_terminal(info: DoorInfo) -> None:
    class MemoryIO(FakeTerminal):
        def __init__(self) -> None:
            super().__init__()
            self.inputs: asyncio.Queue[bytes] = asyncio.Queue()
            self.welcome = asyncio.Event()
            self.help = asyncio.Event()
            self.closed = False

        def enter(self) -> None:
            self.write(ENTER)

        def write(self, data: bytes) -> None:
            super().write(data)
            text = self.screen_text()
            if "You hear the vents" in text or "You watch the rain" in text:
                self.welcome.set()
            if "HELP" in text:
                self.help.set()

        async def read(self) -> bytes:
            return await self.inputs.get()

        def leave(self, farewell: bytes) -> None:
            self.write(LEAVE + farewell + b"\r\n")
            self.closed = True

    async def scenario() -> None:
        server = Server(info.install, tcp=True)
        await server.start()
        terminal = MemoryIO()
        task = asyncio.create_task(run(info, terminal))
        try:
            await asyncio.wait_for(terminal.welcome.wait(), 3)
            assert len(server.core.sessions.active) == 1
            terminal.inputs.put_nowait(b"?")
            await asyncio.wait_for(terminal.help.wait(), 2)
            terminal.inputs.put_nowait(b"\x1b[6~")
            terminal.inputs.put_nowait(b"\x1b")
            terminal.inputs.put_nowait(b"\x18y")
            await asyncio.wait_for(task, 2)
            assert terminal.closed and terminal.cursor_visible
            assert "Karst keeps your place." in terminal.screen_text()
            assert b"\x07" not in terminal.written
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            await server.stop()
    asyncio.run(scenario())


def test_connection_uses_server_hmac_and_rejects_missing_secrets(info: DoorInfo) -> None:
    async def scenario() -> None:
        connection = Connection()
        with pytest.raises(OSError):
            await connection.open(info)
        assert not (info.install / "secrets").exists()
        server = Server(info.install, tcp=True)
        await server.start()
        try:
            assert (await connection.open(info)).type == "welcome"
            await connection.send(Frame("ping", {"t": 42}))
            from blacksite.server.protocol import read_frame
            assert (await read_frame(connection.reader)).data["t"] == 42
        finally:
            await connection.close()
            await server.stop()
        with pytest.raises(OSError):
            await connection.open(info)
    asyncio.run(scenario())


def test_entry_configuration_error_and_small_terminal(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    from blacksite.door import __main__ as entry
    monkeypatch.delenv("NETBBS_DOOR_INFO", raising=False)
    monkeypatch.delenv("BLACKSITE_INSTALL_DIR", raising=False)
    assert entry.main([]) == 2
    assert len(capsys.readouterr().out.splitlines()) == 1


def test_refuse_below_80x24_without_entering_terminal(info: DoorInfo, monkeypatch: pytest.MonkeyPatch) -> None:
    from dataclasses import replace
    from blacksite.door import __main__ as entry
    terminal = FakeTerminal(40, 10)
    monkeypatch.setattr(entry, "read", lambda env: replace(info, width=40, height=10))
    monkeypatch.setattr(entry, "Terminal", lambda local: terminal)
    assert entry.main([]) == 0
    assert b"1049h" not in terminal.written
    assert "80x24" in terminal.screen_text()


@pytest.mark.parametrize("minimal_environment", [False, True])
def test_real_module_uses_native_stdio_pipes(info: DoorInfo, minimal_environment: bool) -> None:
    async def scenario() -> None:
        info.path.write_text(json.dumps({**info.raw, "terminal_width": 80, "terminal_height": 24, "color_depth": "256"}), encoding="utf-8")
        server = Server(info.install, tcp=True)
        await server.start()
        env = {} if minimal_environment else dict(os.environ)
        if os.name == "nt" and "USERPROFILE" in os.environ:
            env["USERPROFILE"] = os.environ["USERPROFILE"]
        env.update(NETBBS_DOOR_INFO=str(info.path), DOOR_BLACKSITE_INSTALL_DIR=str(info.install))
        process = await asyncio.create_subprocess_exec(sys.executable, "-m", "blacksite.door", env=env,
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        terminal = FakeTerminal()

        async def expect(text: str) -> None:
            async with asyncio.timeout(5):
                while text not in terminal.screen_text():
                    data = await process.stdout.read(65536)
                    if not data:
                        raise AssertionError((await process.stderr.read()).decode())
                    terminal.write(data)
        try:
            await expect("BLACKSITE")
            process.stdin.write(b"?")
            await process.stdin.drain()
            await expect("HELP")
            process.stdin.write(b"\x1b\x18y")
            await process.stdin.drain()
            await expect("Karst keeps your place.")
            assert await asyncio.wait_for(process.wait(), 5) == 0
            assert await process.stderr.read() == b""
        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()
            await server.stop()
    asyncio.run(scenario())
