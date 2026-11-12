"""S44: the Row's truce, persisted beside marked_until (game design 5.5, 7.3).

`truce_marked_until` is the expiry of a Mark earned by breaking a truce
(the Tin Halo reads it; Vesper reads `marked_until`). `keeper_answer` is
the keeper's stored answer, JSON {keeper, zone, until}: the one record
behind `hunted`, which survives a restart.
"""

import sqlite3


def apply(db: sqlite3.Connection) -> None:
    db.execute("ALTER TABLE players ADD COLUMN truce_marked_until TEXT")
    db.execute("ALTER TABLE players ADD COLUMN keeper_answer TEXT")
