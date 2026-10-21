"""Product-impact scenarios from the S03 automatic review."""

import argparse
import asyncio
import signal
import sqlite3
import sys
from pathlib import Path

import pytest

from blacksite.content.loader import ContentTree
from blacksite.server import __main__ as entry
from blacksite.server.app import Server
from blacksite.server.clock import ManualClock
from blacksite.server.protocol import Decoder, encode
from blacksite.server.storage import migrations
from blacksite.server.storage.db import Storage
from tests.harness import HeadlessServer, hello


def test_upgrade_discovers_second_migration_by_numeric_prefix(
    scratch_dir: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = scratch_dir / "world.db"
    Storage(path, ManualClock()).close()
    package = scratch_dir / "migrations"
    package.mkdir()
    name = "0003_add_upgrade_marker"
    (package / f"{name}.py").write_text(
        "def apply(db):\n"
        "    db.execute(\"INSERT INTO meta(key,value) VALUES('upgraded', 'true')\")\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(migrations, "__file__", str(package / "__init__.py"))
    monkeypatch.setattr(migrations, "__path__", [str(package)])
    monkeypatch.setattr(migrations, "WORLD_SCHEMA", 3)
    try:
        store = Storage(path, ManualClock())
        assert store.meta("schema_version") == 3
        assert store.meta("upgraded") is True
        store.close()
    finally:
        sys.modules.pop(f"{migrations.__name__}.{name}", None)


def test_missing_upgrade_keeps_original_schema(scratch_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = scratch_dir / "world.db"
    Storage(path, ManualClock()).close()
    monkeypatch.setattr(migrations, "WORLD_SCHEMA", 3)
    with pytest.raises(ValueError, match="exactly one migration"):
        Storage(path, ManualClock())
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0] == "2"


def test_sigterm_during_bootstrap_is_honored_after_start(
    scratch_dir: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = Server(scratch_dir, tcp=True)
    handlers = {}
    original_content = server._content

    def install(sig: signal.Signals, handler: object) -> object:
        previous = handlers.get(sig, signal.SIG_DFL)
        handlers[sig] = handler
        return previous

    def content_with_signal() -> ContentTree:
        assert server.core is None
        handlers[signal.SIGTERM](signal.SIGTERM, None)
        return original_content()

    monkeypatch.setattr(entry, "Server", lambda *args, **kwargs: server)
    monkeypatch.setattr(entry.signal, "signal", install)
    monkeypatch.setattr(server, "_content", content_with_signal)
    args = argparse.Namespace(install_dir=scratch_dir, tcp=True, log_level="INFO", spawn_zone=None)

    async def scenario() -> None:
        await asyncio.wait_for(entry.run(args), 2)
        assert server.stop_requested and server.core.stop_requested
        assert server.stopped.is_set()
        assert not server.connections and not server.tasks
        assert list((scratch_dir / "run").iterdir()) == []
    asyncio.run(scenario())


@pytest.mark.parametrize("failure", ["copy", "load"])
def test_interrupted_content_bootstrap_can_retry_without_manual_cleanup(
    scratch_dir: Path, monkeypatch: pytest.MonkeyPatch, failure: str,
) -> None:
    from blacksite.server import app

    async def scenario() -> None:
        local = scratch_dir / "content.local" / "text"
        local.mkdir(parents=True)
        override = local / "motd.txt"
        override.write_text("You wait.\n", encoding="utf-8")
        original = app.shutil.copyfile
        copies = 0

        def fail_copy(source: Path, destination: Path) -> None:
            nonlocal copies
            original(source, destination)
            copies += 1
            if copies == 2:
                raise OSError("disk full")

        def fail_load(*args: object) -> None:
            raise OSError("read failed")

        with monkeypatch.context() as patch:
            if failure == "copy":
                patch.setattr(app.shutil, "copyfile", fail_copy)
            else:
                patch.setattr(app, "load_content", fail_load)
            with pytest.raises(OSError):
                await Server(scratch_dir, tcp=True).start()
        assert not (scratch_dir / "content.next").exists()
        assert override.read_text(encoding="utf-8") == "You wait.\n"
        server = Server(scratch_dir, tcp=True)
        await server.start()
        assert server.core.motd == "You wait."
        await server.stop()
    asyncio.run(scenario())


def test_slow_writer_closes_without_claiming_credentials_are_wrong(scratch_dir: Path) -> None:
    class StalledWriter:
        def __init__(self) -> None:
            self.frames = []
            self.closed = False

        def write(self, data: bytes) -> None:
            self.frames.extend(Decoder().feed(data))

        async def drain(self) -> None:
            raise asyncio.TimeoutError

        def close(self) -> None:
            self.closed = True

        async def wait_closed(self) -> None:
            pass

    async def scenario() -> None:
        server = Server(scratch_dir, tcp=True)
        server.core = HeadlessServer().core
        reader = asyncio.StreamReader()
        reader.feed_data(encode(hello()))
        writer = StalledWriter()
        await server._client(reader, writer)
        assert writer.closed
        assert [frame.type for frame in writer.frames] == ["welcome"]
        assert not server.core.sessions.active
    asyncio.run(scenario())


def test_persistence_lag_tracks_unsaved_state_instead_of_world_flush(
    scratch_dir: Path,
) -> None:
    clock = ManualClock()
    store = Storage(scratch_dir / "world.db", clock)
    try:
        clock.advance(250)
        row = {"origin": store.origin, "bbs_user_id": "1", "health": 100}
        store.mark_dirty("players", "p1", row)
        assert store.persistence_lag() == 0
        clock.advance(10)
        store.mark_dirty("players", "p1", {**row, "health": 80})
        assert store.persistence_lag() == 1
        store.flush_due()
        assert store.persistence_lag() == 0
        store.mark_dirty("meta", "balance", 1)
        clock.advance(10)
        store.mark_dirty("players", "p1", row)
        assert store.persistence_lag() == 1
        store.flush_now()
        assert store.persistence_lag() == 0
    finally:
        store.close()
