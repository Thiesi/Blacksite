"""Entry point for `python -m karst41.door`, the NetBBS native stdio door.

NetBBS launches this with an argv list, never a shell, so it must work
without the console script (02-architecture.md section 8.1).
"""

import os

from karst41.door.windows_env import restore_system_root

restore_system_root()  # Winsock must initialize before importing asyncio.

import argparse
import asyncio
import sys

from karst41.door.client import run
from karst41.door.doorinfo import read
from karst41.door.cells import CellBuffer
from karst41.door.terminal import Terminal


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Karst 41 native door")
    parser.add_argument("--local", action="store_true", help="use Windows console input for development")
    args = parser.parse_args(argv)
    try:
        info = read(os.environ)
    except ValueError as exc:
        print(f"karst41 door: {exc}")
        return 2
    if info.width < 80 or info.height < 24:
        buffer = CellBuffer(info.width, info.height)
        buffer.put(0, 0, "Karst 41 requires 80x24.")
        buffer.put(0, 1, "ANSI colour and UTF-8.")
        Terminal(args.local).write(buffer.full() + b"\r\n")
        return 0
    try:
        asyncio.run(run(info, Terminal(args.local)))
    except (OSError, ValueError, KeyboardInterrupt):
        pass  # User-facing ends return to NetBBS with terminal cleanup.
    return 0


if __name__ == "__main__":
    sys.exit(main())
