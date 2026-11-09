"""Initial world schema, entity contract §2.1 and §2.11."""

import sqlite3


def apply(db: sqlite3.Connection) -> None:
    db.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    db.execute("""CREATE TABLE players (
        id TEXT PRIMARY KEY, origin TEXT NOT NULL, bbs_user_id TEXT NOT NULL,
        bbs_handle TEXT, name TEXT, archetype TEXT, attributes TEXT, skills TEXT,
        grade INTEGER, xp INTEGER, health INTEGER, stamina INTEGER, shock INTEGER,
        chits_hand INTEGER, chits_bank INTEGER, faction TEXT, standing TEXT,
        marked_until TEXT, warden_heat_until TEXT, zone TEXT, tile TEXT, facing TEXT,
        implants TEXT, equipment TEXT, inventory TEXT, rig TEXT, drugs_active TEXT,
        dependencies TEXT, apartment_id TEXT, settings TEXT, stats TEXT,
        clone_debt INTEGER, recovery_kit_id TEXT, listened_enabled INTEGER,
        created_at TEXT, last_seen_at TEXT, legal_at TEXT,
        UNIQUE(origin, bbs_user_id, name))""")
    # Multiple characters per BBS identity are intentional (S07).
    db.execute("CREATE TABLE items (id TEXT PRIMARY KEY, authority TEXT NOT NULL, data TEXT NOT NULL)")
    db.execute("CREATE TABLE audit (id INTEGER PRIMARY KEY, at TEXT NOT NULL, data TEXT NOT NULL)")
    db.execute("CREATE TABLE bans (bbs_user_id TEXT PRIMARY KEY, expires_at TEXT, reason TEXT NOT NULL)")
    db.execute("CREATE TABLE mutes (bbs_user_id TEXT PRIMARY KEY, expires_at TEXT, reason TEXT NOT NULL)")
    db.execute("CREATE TABLE reports (id INTEGER PRIMARY KEY, at TEXT NOT NULL, data TEXT NOT NULL)")
