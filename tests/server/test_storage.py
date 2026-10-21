"""Architecture §6.2: durable writes, rollback and schema/origin safety."""

import sqlite3
from pathlib import Path

import pytest

from blacksite.server.clock import ManualClock
from blacksite.server.storage.db import Storage
from blacksite.version import WORLD_SCHEMA


def test_migrate_from_empty(scratch_dir: Path) -> None:
    store = Storage(scratch_dir / "world.db", ManualClock())
    try:
        assert store.meta("schema_version") == WORLD_SCHEMA
        assert store.db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        tables = {row[0] for row in store.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"meta", "players", "items", "audit", "bans", "mutes", "reports"} <= tables
    finally:
        store.close()


def test_refuse_newer_schema(scratch_dir: Path) -> None:
    path = scratch_dir / "world.db"
    store = Storage(path, ManualClock())
    store.mark_dirty("meta", "schema_version", WORLD_SCHEMA + 1)
    store.close()
    with pytest.raises(ValueError, match="newer"):
        Storage(path, ManualClock())


def test_flush_cadence_players_5s(scratch_dir: Path) -> None:
    clock = ManualClock()
    store = Storage(scratch_dir / "world.db", clock)
    try:
        store.mark_dirty("players", "p1", {"origin": store.origin, "bbs_user_id": "1", "health": 100})
        store.mark_dirty("meta", "balance", 2)
        clock.advance(49)
        store.flush_due()
        assert store.db.execute("SELECT count(*) FROM players").fetchone()[0] == 0
        clock.advance()
        store.flush_due()
        assert store.db.execute("SELECT health FROM players").fetchone()[0] == 100
        assert store.meta("balance") == 0
        clock.advance(250)
        store.flush_due()
        assert store.meta("balance") == 2
    finally:
        store.close()


def test_flush_now_immediate(scratch_dir: Path) -> None:
    store = Storage(scratch_dir / "world.db", ManualClock())
    store.mark_dirty("meta", "balance", 1)
    store.flush_now("trade")
    assert store.meta("balance") == 1
    assert not store.dirty
    store.close()


def test_origin_id_created_once(scratch_dir: Path) -> None:
    path = scratch_dir / "world.db"
    store = Storage(path, ManualClock())
    origin = store.origin
    assert len(origin) == 32
    store.close()
    other = Storage(path, ManualClock())
    assert other.origin == origin
    other.close()


def test_failed_flush_rolls_back_every_row_and_can_retry(scratch_dir: Path) -> None:
    store = Storage(scratch_dir / "world.db", ManualClock())
    store.mark_dirty("meta", "balance", 3)
    store.mark_dirty("players", "p1", {"health": 100})  # Missing identity: reject transaction.
    with pytest.raises(sqlite3.IntegrityError):
        store.flush_now("trade")
    assert store.meta("balance") == 0
    assert len(store.dirty) == 2
    store.mark_dirty("players", "p1", {"origin": store.origin, "bbs_user_id": "1", "health": 100})
    store.flush_now("trade")
    assert store.meta("balance") == 3
    store.mark_dirty("players", "p1", {"origin": store.origin, "bbs_user_id": "1", "health": 80})
    store.close()


def test_migration_ddl_rolls_back_on_failure(scratch_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from blacksite.server.storage import migrations

    class BrokenMigration:
        @staticmethod
        def apply(db: sqlite3.Connection) -> None:
            db.execute("CREATE TABLE meta(key TEXT, value TEXT)")
            raise RuntimeError("injected failure")

    path = scratch_dir / "broken.db"
    monkeypatch.setattr(migrations, "import_module", lambda name: BrokenMigration)
    with pytest.raises(RuntimeError, match="injected"):
        Storage(path, ManualClock())
    with sqlite3.connect(path) as db:
        assert not db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()


def test_dirty_snapshot_does_not_alias_mutable_input(scratch_dir: Path) -> None:
    store = Storage(scratch_dir / "world.db", ManualClock())
    seeds = {"zone": 1}
    store.mark_dirty("meta", "rng_seeds", seeds)
    seeds["zone"] = 2
    store.flush_now()
    assert store.meta("rng_seeds") == {"zone": 1}
    store.close()


def test_nullable_world_meta_can_be_reset(scratch_dir: Path) -> None:
    store = Storage(scratch_dir / "world.db", ManualClock())
    store.mark_dirty("meta", "next_event_roll_at", "later")
    store.flush_now()
    store.mark_dirty("meta", "next_event_roll_at", None)
    store.flush_now()
    assert store.meta("next_event_roll_at") is None
    store.close()
