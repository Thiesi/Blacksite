"""Entities 2.6: transactional market listings, bid history and bounties."""

import sqlite3


def apply(db: sqlite3.Connection) -> None:
    db.execute('CREATE TABLE market_listings (id TEXT PRIMARY KEY, data TEXT NOT NULL)')
    db.execute('CREATE TABLE market_bids (id TEXT PRIMARY KEY, data TEXT NOT NULL)')
    db.execute('CREATE TABLE bounties (id TEXT PRIMARY KEY, data TEXT NOT NULL)')
