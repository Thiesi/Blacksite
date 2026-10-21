"""Entry point for `python -m blacksite.server --install-dir DIR`."""

import argparse
import asyncio
import signal
import sqlite3
import sys
from pathlib import Path

from blacksite.server.app import Server


async def run(args: argparse.Namespace) -> None:
    server = Server(args.install_dir, args.tcp, args.log_level, spawn_zone=args.spawn_zone)
    previous: dict[signal.Signals, object] = {}

    def stop(signum: int, frame: object) -> None:
        server.request_stop()

    signals = [signal.SIGINT, signal.SIGTERM]
    if hasattr(signal, "SIGBREAK"):
        signals.append(signal.SIGBREAK)
    for sig in signals:
        previous[sig] = signal.signal(sig, stop)
    try:
        await server.run()
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="blacksite server")
    parser.add_argument("--install-dir", type=Path, required=True)
    parser.add_argument("--tcp", action="store_true")
    parser.add_argument("--spawn-zone", help="preview a supplied zone before character entry")
    parser.add_argument("--log-level", choices=("DEBUG", "INFO", "WARNING", "ERROR"), default="INFO")
    args = parser.parse_args(argv)
    try:
        asyncio.run(run(args))
    except (OSError, ValueError, RuntimeError, sqlite3.Error) as exc:
        print(f"blacksite server: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
