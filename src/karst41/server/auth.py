"""Filesystem trust and canonical door_info signatures (architecture §4)."""

import hashlib
import hmac
import json
import os
import secrets
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

Role = Literal["caller", "operator", "peer"]


def door_info_bytes(info: dict[str, Any]) -> bytes:
    """Wire contract: sorted compact UTF-8 JSON, before identity normalization."""
    return json.dumps(info, sort_keys=True, ensure_ascii=False, allow_nan=False,
                      separators=(",", ":")).encode("utf-8")


def sign(info: dict[str, Any], secret: bytes) -> str:
    return hmac.new(secret, door_info_bytes(info), hashlib.sha256).hexdigest()


def load_secret(path: Path) -> bytes:
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        pass
    else:
        with os.fdopen(fd, "w", encoding="ascii") as stream:
            stream.write(secrets.token_hex(32) + "\n")
    if os.name != "nt":
        path.chmod(0o600)
    value = bytes.fromhex(path.read_text(encoding="ascii").strip())
    if len(value) != 32:
        raise ValueError(f"invalid secret: {path.name}")
    return value


def identity(info: dict[str, Any]) -> str:
    return str(info.get("bbs_user_id", info.get("user_id")))


class Authenticator:
    def __init__(self, door: bytes, admin: bytes,
                 banned: Callable[[str], bool] = lambda _: False) -> None:
        self.door = door
        self.admin = admin
        self.banned = banned

    def authenticate(self, info: dict[str, Any], signature: str) -> Role:
        # Evaluate both compares; client-supplied role is never trusted.
        caller = hmac.compare_digest(sign(info, self.door), signature)
        operator = hmac.compare_digest(sign(info, self.admin), signature)
        if operator:
            return "operator"
        if not caller:
            raise ValueError("authentication failed")
        if self.banned(identity(info)):
            raise ValueError("banned")
        return "caller"
