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
        self.dirty_since: dict[tuple[str, str], int] = {}
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
        if kind not in {"players", "items", "meta", "identities"}:
            raise ValueError("unknown persistent entity kind")
        key = (kind, record_id)
        if value is ... and key not in self.dirty:
            raise ValueError("first dirty mark requires a state snapshot")
        if value is not ...:
            # Freeze the proposal; mutations after marking cannot change the write.
            self.dirty[key] = json.loads(self._json(value))
            self.dirty_since.setdefault(key, self.clock.now_tick())

    def persistence_lag(self) -> float:
        """Age of the oldest uncommitted proposal, zero when nothing is dirty."""
        oldest = min(self.dirty_since.values(), default=self.clock.now_tick())
        return (self.clock.now_tick() - oldest) / TICK_HZ

    def flush_due(self) -> None:
        tick = self.clock.now_tick()
        kinds: set[str] = set()
        if tick - self.last_players >= PLAYER_FLUSH_SECONDS * TICK_HZ:
            kinds.update({"players", "identities"})
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
        self._flush({"players", "items", "meta", "identities"})
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
                elif kind == "identities":
                    self.db.execute("INSERT OR REPLACE INTO identities(bbs_user_id,data) VALUES(?,?)",
                                    (record_id, self._json(value)))
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
            del self.dirty_since[key]

    def character_state(self) -> dict[str, Any]:
        """Load once in the I/O layer; the simulation owns pure copies."""
        json_columns = {"attributes", "skills", "standing", "tile", "implants", "equipment", "inventory", "rig",
                        "drugs_active", "dependencies", "settings", "stats", "progress"}
        players = []
        for row in self.db.execute("SELECT * FROM players WHERE archetype IS NOT NULL"):
            players.append({key: json.loads(value) if key in json_columns and value is not None else value
                            for key, value in dict(row).items()})
        return {"players": players, "identities": {row[0]: json.loads(row[1]) for row in self.db.execute("SELECT * FROM identities")},
                "serial": self.meta("player_serial") or 0, "cap": self.meta("character_cap"),
                "npcs": self.meta("npc_state") or {},
                "lattice": self.meta("lattice_state") or {},
                "interlock": self.meta("interlock_state") or {},
                "season": self.meta("season") or 0,
                "items": [json.loads(row[0]) for row in self.db.execute("SELECT data FROM items")],
                "commerce": {"item_serial": self.meta("item_serial") or 0,
                    "budgets": {row[0]: {"hour":row[1], "remaining":row[2]} for row in self.db.execute("SELECT * FROM vendor_budgets")},
                    "caches": {row[0]: json.loads(row[1]) for row in self.db.execute("SELECT * FROM caches")}}}

    def commerce_write(self, effect: dict[str, Any]) -> None:
        """Architecture 6.2: transfer, money, ownership and receipt are atomic."""
        player = effect["player"]
        with self.db:
            if "identity" in effect:
                self.db.execute("INSERT OR REPLACE INTO identities VALUES(?,?)", (effect["user"],self._json(effect["identity"])))
            for player_record in ([player] if player else [])+effect.get("players", []):
                player = player_record
                cols = list(player)
                if not set(cols) <= self.player_columns: raise ValueError("unknown player fields")
                quoted = ",".join(f'"{c}"' for c in cols)
                updates = ",".join(f'"{c}"=excluded."{c}"' for c in cols if c != "id")
                values = [self._json(player[c]) if isinstance(player[c], (dict,list,tuple)) else player[c] for c in cols]
                self.db.execute(f'INSERT INTO players ({quoted}) VALUES ({",".join("?" for _ in cols)}) ON CONFLICT(id) DO UPDATE SET {updates}', values)
            for item in effect["items"]:
                self.db.execute("INSERT OR REPLACE INTO items(id,authority,data) VALUES(?,?,?)", (item["id"],self.origin,self._json(item)))
            for iid in effect["delete_items"]:
                self.db.execute("DELETE FROM items WHERE id=?", (iid,))
            for key, budget in effect["budgets"].items():
                self.db.execute("INSERT OR REPLACE INTO vendor_budgets VALUES(?,?,?)", (key,budget["hour"],budget["remaining"]))
            self.db.execute("DELETE FROM caches")
            for key, cache in effect["caches"].items():
                self.db.execute("INSERT INTO caches VALUES(?,?)", (key,self._json(cache)))
            self.db.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('item_serial',?)", (self._json(effect["serial"]),))
            if "interlock_state" in effect:
                self.db.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('interlock_state',?)", (self._json(effect["interlock_state"]),))
            if "npc_state" in effect:
                self.db.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('npc_state',?)", (self._json(effect["npc_state"]),))
            if "lattice_state" in effect:
                self.db.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('lattice_state',?)", (self._json(effect["lattice_state"]),))
            self.db.execute("INSERT INTO audit(at,data) VALUES(?,?)", (self.clock.now_utc().isoformat(), self._json({"action":"item_transfer", "player":effect["player"]["id"] if effect["player"] else None})))
        # Never let an older write-behind snapshot overwrite this receipt.
        settled = {("items", item["id"]) for item in effect["items"]} | {("items", iid) for iid in effect["delete_items"]}
        if effect["player"]: settled.add(("players",effect["player"]["id"]))
        settled |= {("players", row["id"]) for row in effect.get("players", [])}
        if "interlock_state" in effect: settled.add(("meta", "interlock_state"))
        if "npc_state" in effect: settled.add(("meta", "npc_state"))
        if "lattice_state" in effect: settled.add(("meta", "lattice_state"))
        if "identity" in effect: settled.add(("identities",effect["user"]))
        for key in settled:
            self.dirty.pop(key,None); self.dirty_since.pop(key,None)

    def character_write(self, effect: dict[str, Any]) -> None:
        """Commit creation rewards/deletion before the simulation acknowledges."""
        action = effect["action"]
        if action == "delete":
            record_id = effect["player"]["id"]
            with self.db:
                owned = [row[0] for row in self.db.execute("SELECT id,data FROM items") if json.loads(row[1]).get("owner") == record_id]
                self.db.executemany("DELETE FROM items WHERE id=?", [(iid,) for iid in owned])
                self.db.execute("DELETE FROM players WHERE id=? AND origin=?", (record_id, self.origin))
                self.db.execute("INSERT OR REPLACE INTO identities(bbs_user_id,data) VALUES(?,?)",
                                (effect["user"], self._json(effect["identity"])))
            for key in tuple(self.dirty):
                if key in (("players", record_id), ("identities", effect["user"])) or (key[0] == "items" and self.dirty[key].get("owner") == record_id):
                    self.dirty.pop(key)
                    self.dirty_since.pop(key, None)
            return
        previous, ages = dict(self.dirty), dict(self.dirty_since)
        try:
            self.mark_dirty("identities", effect["user"], effect["identity"])
            if effect.get("player"):
                self.mark_dirty("players", effect["player"]["id"], effect["player"])
            for item in effect.get("items", []):
                self.mark_dirty("items", item["id"], item)
            if action == "create":
                self.mark_dirty("meta", "player_serial", effect["serial"])
            if action in ("create", "identity") or effect.get("immediate"):
                self.flush_now()
        except Exception:
            # Rejected creation must not leak into a later periodic flush.
            # Ordinary state retains its frozen snapshot for write-behind retry.
            if action == "create":
                self.dirty, self.dirty_since = previous, ages
            raise

    def banned(self, user_id: str) -> bool:
        row = self.db.execute("SELECT expires_at FROM bans WHERE bbs_user_id=?", (user_id,)).fetchone()
        return row is not None and (row[0] is None or row[0] > self.clock.now_utc().isoformat())

    def audit(self, row: dict[str, Any]) -> None:
        with self.db:
            self.db.execute("INSERT INTO audit(at,data) VALUES(?,?)", (self.clock.now_utc().isoformat(), self._json(row)))

    def report(self, row: dict[str, Any]) -> None:
        """Entity §2.10: report and audit receipt commit together."""
        with self.db:
            self.db.execute("INSERT INTO reports(at,data) VALUES(?,?)", (row["at"], self._json(row)))
            self.db.execute("INSERT INTO audit(at,data) VALUES(?,?)", (row["at"], self._json(row)))

    def close(self) -> None:
        try:
            self.flush_now()
        finally:
            self.db.close()
