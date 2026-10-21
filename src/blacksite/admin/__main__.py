"""Foreground service and local operator CLI (architecture section 2.3)."""

import argparse
import asyncio
import json
import os
import secrets
import sys
import tempfile
from pathlib import Path
from typing import Any

from blacksite import content
from blacksite.admin.client import request
from blacksite.content.loader import load_content
from blacksite.content.validate import validate
from blacksite.server.storage.lease import Lease
from blacksite.server.storage.db import Storage
from blacksite.server.clock import RealClock


def character_cap(install: Path, value: int) -> dict[str, int]:
    """Offline world setting; never edit a live world's database."""
    if value < 1:
        raise ValueError("character cap must be positive")
    install.mkdir(parents=True, exist_ok=True)
    lease = Lease(install / "world.db.sessions")
    lease.acquire()
    try:
        store = Storage(install / "world.db", RealClock())
        try:
            store.mark_dirty("meta", "character_cap", value)
            store.flush_now()
            store.audit({"operator": "offline", "command": "character_cap", "target": value, "outcome": "ok"})
        finally:
            store.close()
    finally:
        lease.release()
    return {"character_cap": value}


def rotate(install: Path) -> dict[str, bool]:
    """Rotate credentials while holding the server's exclusive lease."""
    install.mkdir(parents=True, exist_ok=True)
    lease = Lease(install / "world.db.sessions")
    lease.acquire()
    staged: list[tuple[Path, Path]] = []
    try:
        root = install / "secrets"
        root.mkdir(exist_ok=True, mode=0o700)
        for name in ("door.secret", "admin.secret"):
            fd, path = tempfile.mkstemp(prefix=".rotate-", dir=root)
            temporary = Path(path)
            staged.append((temporary, root / name))
            with os.fdopen(fd, "w", encoding="ascii") as stream:
                stream.write(secrets.token_hex(32) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
        for temporary, target in staged:
            os.replace(temporary, target)
        return {"rotated": True}
    finally:
        for temporary, _ in staged:
            temporary.unlink(missing_ok=True)
        lease.release()


def parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--install-dir", type=Path, default=argparse.SUPPRESS)
    common.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
    root = argparse.ArgumentParser(description="Blacksite service and operator tools", parents=[common])
    commands = root.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve", parents=[common], help="run the service in the foreground")
    serve.add_argument("--tcp", action="store_true")
    serve.add_argument("--spawn-zone", help="preview a supplied zone before character entry")
    serve.add_argument("--log-level", choices=("DEBUG", "INFO", "WARNING", "ERROR"), default="INFO")
    for name in ("status", "who", "stop", "validate"):
        commands.add_parser(name, parents=[common])
    secret = commands.add_parser("secrets", parents=[common])
    secret.add_subparsers(dest="secret_command", required=True).add_parser("rotate", parents=[common])
    cap = commands.add_parser("character-cap", parents=[common], help="set the offline per-identity character cap")
    cap.add_argument("value", type=int)
    return root


def emit(result: Any, machine: bool) -> None:
    if machine:
        print(json.dumps(result, ensure_ascii=True, allow_nan=False))
    elif isinstance(result, dict):
        for key, value in result.items():
            print(f"{key}: {json.dumps(value, ensure_ascii=True)}")
    else:
        for row in result:
            # Escape caller-controlled names in the operator's terminal too.
            print(json.dumps(row, ensure_ascii=True))


def main(argv: list[str] | None = None) -> int:
    cli = parser()
    args = cli.parse_args(argv)
    args.install_dir = getattr(args, "install_dir", os.environ.get("BLACKSITE_INSTALL_DIR"))
    args.json = getattr(args, "json", False)
    if args.install_dir is None:
        cli.error("--install-dir or BLACKSITE_INSTALL_DIR is required")
    install = Path(args.install_dir).resolve()
    try:
        if args.command == "serve":
            from blacksite.server.__main__ import main as serve
            flags = ["--install-dir", str(install), "--log-level", args.log_level]
            if args.spawn_zone:
                flags += ["--spawn-zone", args.spawn_zone]
            return serve(flags + (["--tcp"] if args.tcp else []))
        if args.command == "validate":
            source = install / "content"
            if not source.exists():
                source = Path(content.__file__).parent
            local = install / "content.local"
            tree = load_content(source, local if local.exists() else None)
            problems = validate(tree)
            emit({"ok": not problems, "content_hash": tree.hash,
                  "problems": [str(problem) for problem in problems]}, args.json)
            return int(bool(problems))
        result = character_cap(install, args.value) if args.command == "character-cap" else rotate(install) if args.command == "secrets" else asyncio.run(request(install, args.command))
        emit(result, args.json)
        return 0
    except (OSError, ValueError, RuntimeError, asyncio.TimeoutError, asyncio.IncompleteReadError) as exc:
        print("blacksite admin: " + (str(exc) or type(exc).__name__), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
