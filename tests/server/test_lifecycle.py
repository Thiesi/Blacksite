"""Local transport integration only; multiplayer rules use the harness."""

import asyncio
import json
import os
from pathlib import Path

import pytest

from blacksite.server.app import Server
from blacksite.server.auth import load_secret
from blacksite.server.protocol import Frame, encode, read_frame
from blacksite.server.transport import connect
from blacksite.version import PACKAGE_VERSION
from tests.harness import hello


async def login(root: Path, admin: bool = False) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
    secret = load_secret(root / "secrets" / ("admin.secret" if admin else "door.secret"))
    reader, writer = await connect(root)
    writer.write(encode(hello(secret=secret)))
    await writer.drain()
    assert (await asyncio.wait_for(read_frame(reader, "server"), 2)).type == "welcome"
    return reader, writer


def test_second_server_refused_by_lease(scratch_dir: Path) -> None:
    async def scenario() -> None:
        first = Server(scratch_dir, tcp=True, characters=False)
        await first.start()
        try:
            with pytest.raises(RuntimeError, match="lease"):
                await Server(scratch_dir, tcp=True, characters=False).start()
            assert (scratch_dir / "run" / "port").exists()
        finally:
            await first.stop()
    asyncio.run(scenario())


def test_stop_sends_bye_and_removes_run_files(scratch_dir: Path) -> None:
    async def scenario() -> None:
        server = Server(scratch_dir, tcp=True, characters=False)
        await server.start()
        reader, writer = await login(scratch_dir)
        try:
            writer.write(encode(Frame("ping", {"t": 123})))
            await writer.drain()
            assert (await read_frame(reader)).data["t"] == 123
            await server.stop()
            assert (await read_frame(reader)).data["reason"] == "maintenance"
            assert list((scratch_dir / "run").iterdir()) == []
            assert not server.connections and not server.tasks
        finally:
            await server.stop()
            writer.close()
            await writer.wait_closed()
    asyncio.run(scenario())


def test_content_copied_on_first_start(scratch_dir: Path) -> None:
    async def scenario() -> None:
        server = Server(scratch_dir, tcp=True, characters=False)
        await server.start()
        try:
            assert (scratch_dir / "content" / "tiles.json").is_file()
            assert not list((scratch_dir / "content").rglob("*.py"))
            assert server.storage.meta("content_package_version") == PACKAGE_VERSION
            rows = [json.loads(row) for row in (scratch_dir / "logs" / "server.log").read_text(encoding="utf-8").splitlines()]
            assert rows[0]["message"] == "world open"
            assert len(rows[0]["content_hash"]) == 64
        finally:
            await server.stop()
    asyncio.run(scenario())


def test_local_content_untouched(scratch_dir: Path) -> None:
    local = scratch_dir / "content.local"
    local.mkdir()
    marker = local / "text" / "motd.txt"
    marker.parent.mkdir()
    marker.write_text("You wait by the door.\n", encoding="utf-8")

    async def scenario() -> None:
        for _ in range(2):
            server = Server(scratch_dir, tcp=True, characters=False)
            await server.start()
            try:
                assert server.core.motd == "You wait by the door."
            finally:
                await server.stop()
        assert marker.read_text(encoding="utf-8") == "You wait by the door.\n"
    asyncio.run(scenario())


def test_operator_stop_and_audit(scratch_dir: Path) -> None:
    async def scenario() -> None:
        server = Server(scratch_dir, tcp=True, characters=False)
        await server.start()
        reader, writer = await login(scratch_dir, admin=True)
        try:
            writer.write(encode(Frame("admin.stop")))
            await writer.drain()
            assert (await asyncio.wait_for(read_frame(reader), 2)).type == "view"
            assert server.core.stop_requested
            rows = (scratch_dir / "logs" / "audit.log").read_text(encoding="utf-8").splitlines()
            assert json.loads(rows[0])["command"] == "admin.stop"
            assert server.storage.db.execute("SELECT count(*) FROM audit").fetchone()[0] == 1
        finally:
            await server.stop()
            writer.close()
            await writer.wait_closed()
    asyncio.run(scenario())


def test_failed_start_releases_lease_and_partial_hello_stops(scratch_dir: Path) -> None:
    async def scenario() -> None:
        local = scratch_dir / "content.local"
        local.mkdir()
        bad = local / "tiles.json"
        bad.write_text("not JSON", encoding="utf-8")
        with pytest.raises(ValueError, match="invalid content"):
            await Server(scratch_dir, tcp=True, characters=False).start()
        bad.unlink()
        # Bootstrap's failed temporary tree must not prevent a corrected retry.
        server = Server(scratch_dir, tcp=True, characters=False)
        await server.start()
        reader, writer = await connect(scratch_dir)
        writer.write(b"\x00")
        await writer.drain()
        await server.stop()
        writer.close()
        await writer.wait_closed()
        assert list((scratch_dir / "run").iterdir()) == []
    asyncio.run(scenario())


@pytest.mark.skipif(os.name == "nt", reason="asyncio Unix sockets unavailable on Windows")
def test_unix_socket_permissions_and_stale_probe(scratch_dir: Path) -> None:
    import socket

    async def scenario() -> None:
        run = scratch_dir / "run"
        run.mkdir()
        stale = socket.socket(socket.AF_UNIX)
        stale.bind(str(run / "blacksite.sock"))
        stale.close()
        server = Server(scratch_dir)
        await server.start()
        try:
            assert (run / "blacksite.sock").stat().st_mode & 0o777 == 0o600
            reader, writer = await login(scratch_dir)
            writer.close()
            await writer.wait_closed()
        finally:
            await server.stop()
    asyncio.run(scenario())
