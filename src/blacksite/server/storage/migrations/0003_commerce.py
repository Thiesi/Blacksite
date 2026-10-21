"""S12 per-counter hourly budgets and durable world-item caches."""

import sqlite3


def apply(db: sqlite3.Connection) -> None:
    db.execute("CREATE TABLE vendor_budgets (id TEXT PRIMARY KEY, hour INTEGER NOT NULL, remaining INTEGER NOT NULL)")
    db.execute("CREATE TABLE caches (id TEXT PRIMARY KEY, data TEXT NOT NULL)")
