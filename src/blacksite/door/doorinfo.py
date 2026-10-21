"""Read only the native door drop-file and explicitly named environment."""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DoorInfo:
    path: Path
    install: Path
    raw: dict[str, Any]
    width: int
    height: int
    color_depth: str
    session_limit: int

    @property
    def handle(self) -> str:
        return self.raw["handle"]


def read(environment: Mapping[str, str]) -> DoorInfo:
    try:
        path = Path(environment["NETBBS_DOOR_INFO"]).resolve()
        configured_install = environment.get("DOOR_BLACKSITE_INSTALL_DIR", environment.get("BLACKSITE_INSTALL_DIR"))
        if not configured_install:
            raise ValueError("missing install directory")
        install = Path(configured_install).resolve()
        if path.stat().st_size > 256 * 1024:
            raise ValueError("door info is too large")
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or not isinstance(raw.get("handle"), str):
            raise ValueError("door info needs a handle")
        identity = raw.get("user_id")
        if not ((type(identity) is int and identity >= 0) or (isinstance(identity, str) and identity)):
            raise ValueError("door info needs a user_id")
        width, height = raw["terminal_width"], raw["terminal_height"]
        if type(width) is not int or type(height) is not int or not (1 <= width <= 1000 and 1 <= height <= 1000):
            raise ValueError("invalid terminal dimensions")
        depth = str(raw.get("color_depth", "256"))
        limit = int(environment.get("DOOR_BLACKSITE_SESSION_LIMIT", environment.get("BLACKSITE_SESSION_LIMIT", raw.get("session_limit_seconds", 3600))))
        if type(raw.get("session_limit_seconds", 3600)) is bool or limit < 1:
            raise ValueError("invalid session limit")
        if "session_limit_seconds" in raw:
            effective_limit = raw["session_limit_seconds"]
            if type(effective_limit) is not int or effective_limit < 1:
                raise ValueError("invalid effective session limit")
            limit = min(limit, effective_limit)
        # API 2+ may also carry scoped BBS outbound credentials. This game
        # needs metadata only; never copy those credentials across its link.
        allowed = {"handle", "user_id", "terminal_width", "terminal_height", "color_depth", "node_name",
                   "unicode_style", "timezone", "transport", "node_id", "door_api", "session_limit_seconds"}
        raw = {key: value for key, value in raw.items() if key in allowed}
        return DoorInfo(path, install, raw, width, height, depth, limit)
    except (OSError, KeyError, TypeError, ValueError, RecursionError) as exc:
        raise ValueError("invalid door configuration: NETBBS_DOOR_INFO and BLACKSITE_INSTALL_DIR are required") from exc
