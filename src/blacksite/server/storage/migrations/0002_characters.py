"""S07: character progress, Unicode name keys and durable BBS identities."""

import sqlite3


def apply(db: sqlite3.Connection) -> None:
    db.execute("ALTER TABLE players ADD COLUMN progress TEXT")
    db.execute("ALTER TABLE players ADD COLUMN name_key TEXT")
    db.execute("CREATE UNIQUE INDEX player_names ON players(origin, name_key)")
    db.execute("CREATE TABLE identities (bbs_user_id TEXT PRIMARY KEY, data TEXT NOT NULL)")
    db.execute("INSERT INTO meta(key,value) VALUES('character_cap','1')")
