"""Single event-loop owner, transactional write-behind and durable flush.

Only the I/O layer calls this module. No awaits occur inside a transaction.
The server's writer task owns periodic flushes; flush_now is synchronous
so later actions can commit before publishing success (architecture §15.2).
"""

import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from blacksite.server.clock import Clock, TICK_HZ
from blacksite.server.storage.migrations import migrate

PLAYER_FLUSH_SECONDS = 5  # Architecture §6.2.
WORLD_FLUSH_SECONDS = 30
IMMEDIATE_REASONS = frozenset({
    "death", "trade", "market", "item_transfer", "relay_change", "contract_change",
    "season_change", "logout", "evidence_publication", "work_order_allocation",
    "contribution", "ballot", "settlement", "event_plan_commitment",
})


class Storage:
    def __init__(self, path: Path, clock: Clock) -> None:
        self.clock = clock
        self.db = sqlite3.connect(path, timeout=1.0)
        self.db.row_factory = sqlite3.Row
        self.dirty: dict[tuple[str, str], dict[str, Any] | Any] = {}
        self.last_players = self.last_world = clock.now_tick()
        try:
            self.db.execute("PRAGMA journal_mode=WAL")
            self.db.execute("PRAGMA synchronous=FULL")
            self.db.execute("PRAGMA foreign_keys=ON")
            migrate(self.db)
            with self.db:
                defaults = {"origin": uuid.uuid4().hex, "created_at": clock.now_utc().isoformat(),
                    "season": 1, "event_cooldowns": {}, "rng_seeds": {}, "balance": 0,
                    "committed_event_plans": [], "next_event_roll_at": None, "season_modifiers": []}
                for key, value in defaults.items():
                    self.db.execute("INSERT OR IGNORE INTO meta(key,value) VALUES(?,?)", (key, self._json(value)))
            self.player_columns = {row[1] for row in self.db.execute("PRAGMA table_info(players)")}
        except BaseException:
            self.db.close()
            raise

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)

    def meta(self, key: str) -> Any:
        row = self.db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else None

    @property
    def origin(self) -> str:
        return self.meta("origin")

    def mark_dirty(self, kind: str, record_id: str, value: Any = ...) -> None:
        if kind not in {"players", "items", "meta"}:
            raise ValueError("unknown persistent entity kind")
        key = (kind, record_id)
        if value is ... and key not in self.dirty:
            raise ValueError("first dirty mark requires a state snapshot")
        if value is not ...:
            # Freeze the proposal; mutations after marking cannot change the write.
            self.dirty[key] = json.loads(self._json(value))

    def flush_due(self) -> None:
        tick = self.clock.now_tick()
        kinds: set[str] = set()
        if tick - self.last_players >= PLAYER_FLUSH_SECONDS * TICK_HZ:
            kinds.add("players")
        if tick - self.last_world >= WORLD_FLUSH_SECONDS * TICK_HZ:
            kinds.update({"meta", "items"})
        self._flush(kinds)
        if "players" in kinds:
            self.last_players = tick
        if "meta" in kinds:
            self.last_world = tick

    def flush_now(self, reason: str | None = None) -> None:
        if reason is not None and reason not in IMMEDIATE_REASONS:
            raise ValueError("unknown immediate persistence reason")
        self._flush({"players", "items", "meta"})
        self.last_players = self.last_world = self.clock.now_tick()

    def _flush(self, kinds: set[str]) -> None:
        pending = {key: value for key, value in self.dirty.items() if key[0] in kinds}
        with self.db:
            for (kind, record_id), value in pending.items():
                if kind == "meta":
                    self.db.execute("INSERT OR REPLACE INTO meta(key,value) VALUES(?,?)", (record_id, self._json(value)))
                elif kind == "items":
                    self.db.execute("INSERT OR REPLACE INTO items(id,authority,data) VALUES(?,?,?)",
                                    (record_id, self.origin, self._json(value)))
                else:
                    row = {**value, "id": record_id}
                    if not set(row) <= self.player_columns:
                        raise ValueError("unknown player fields")
                    cols = list(row)
                    encoded = [self._json(row[c]) if isinstance(row[c], (dict, list, tuple)) else row[c] for c in cols]
                    updates = ",".join(f'"{c}"=excluded."{c}"' for c in cols if c != "id")
                    quoted = ",".join(f'"{c}"' for c in cols)
                    placeholders = ",".join("?" for _ in cols)
                    self.db.execute(f'INSERT INTO players ({quoted}) VALUES ({placeholders}) ON CONFLICT(id) DO UPDATE SET {updates}', encoded)
        # Preserve dirty marks on transaction failure, for a safe retry.
        for key in pending:
            del self.dirty[key]

    def banned(self, user_id: str) -> bool:
        row = self.db.execute("SELECT expires_at FROM bans WHERE bbs_user_id=?", (user_id,)).fetchone()
        return row is not None and (row[0] is None or row[0] > self.clock.now_utc().isoformat())

    def audit(self, row: dict[str, Any]) -> None:
        with self.db:
            self.db.execute("INSERT INTO audit(at,data) VALUES(?,?)", (self.clock.now_utc().isoformat(), self._json(row)))

    def close(self) -> None:
        try:
            self.flush_now()
        finally:
            self.db.close()
