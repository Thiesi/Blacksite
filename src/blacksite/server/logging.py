"""Instance-owned JSONL sinks; no root logger or terminal output."""

import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from blacksite.server.clock import Clock


class Logs:
    def __init__(self, root: Path, clock: Clock, level: str = "INFO") -> None:
        self.clock = clock
        self.level = getattr(logging, level)
        self.server = RotatingFileHandler(root / "server.log", maxBytes=2 * 1024 * 1024,
                                         backupCount=3, encoding="utf-8")
        self.audit_file = (root / "audit.log").open("a", encoding="utf-8")

    def event(self, message: str, level: str = "INFO", **fields: Any) -> None:
        number = getattr(logging, level)
        if number < self.level:
            return
        payload = json.dumps({"at": self.clock.now_utc().isoformat(), "level": level,
                              "message": message, **fields}, ensure_ascii=False)
        self.server.emit(logging.LogRecord("blacksite", number, "", 0, payload, (), None))

    def audit(self, row: dict[str, Any]) -> None:
        self.audit_file.write(json.dumps({"at": self.clock.now_utc().isoformat(), **row}, ensure_ascii=False) + "\n")
        self.audit_file.flush()

    def close(self) -> None:
        self.server.close()
        self.audit_file.close()
