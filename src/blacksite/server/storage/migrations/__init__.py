"""Ordered transactional SQLite schema migrations."""

from importlib import import_module
from pathlib import Path
import sqlite3

from blacksite.version import WORLD_SCHEMA


def migrate(db: sqlite3.Connection) -> None:
    exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='meta'").fetchone()
    version = 0
    if exists:
        row = db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        if row is None:
            raise ValueError("database has no schema version")
        version = int(row[0])
    if version > WORLD_SCHEMA:
        raise ValueError("database schema is newer than this server")
    if version < 0:
        raise ValueError("invalid database schema")
    with db:
        if version < WORLD_SCHEMA:
            db.execute("BEGIN IMMEDIATE")
        for number in range(version + 1, WORLD_SCHEMA + 1):
            candidates = sorted(Path(__file__).parent.glob(f"{number:04d}_*.py"))
            if len(candidates) != 1:
                raise ValueError(f"expected exactly one migration for schema {number}")
            module = import_module(f"{__name__}.{candidates[0].stem}")
            module.apply(db)
            db.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version',?)", (str(number),))
