"""Entry point for `python -m blacksite.bot`."""

import argparse
import asyncio
import sys
import time
from pathlib import Path

from blacksite.server.auth import load_secret, sign
from blacksite.server.protocol import Frame, encode, read_frame
from blacksite.server.transport import connect
from blacksite.version import PACKAGE_VERSION, PROTOCOL_MAJOR


async def run(install: Path, watch: bool, width: int, height: int) -> None:
    secret_path = install / "secrets" / "door.secret"
    if not secret_path.is_file():
        raise ValueError("service has no door secret; start the service first")
    secret = load_secret(secret_path)
    info = {"user_id": "smoke-bot", "handle": "Smoke", "node_name": "local"}
    reader, writer = await asyncio.wait_for(connect(install), 5)
    try:
        writer.write(encode(Frame("hello", {"proto": PROTOCOL_MAJOR, "door_info": info,
            "hmac": sign(info, secret), "client_version": PACKAGE_VERSION,
            "caps": {"width": width, "height": height, "tier": "256", "unicode": True}})))
        await writer.drain()
        welcome = await asyncio.wait_for(read_frame(reader, "server"), 5)
        if welcome.type != "welcome":
            raise ValueError(f"connection refused: {welcome.data.get('reason')}")
        began = time.perf_counter()
        writer.write(encode(Frame("ping", {"t": 0})))
        await writer.drain()
        pong = await asyncio.wait_for(read_frame(reader, "server"), 5)
        if pong.type != "pong":
            raise ValueError("expected pong")
        print(f"pong {(time.perf_counter() - began) * 1000:.3f} ms", flush=True)
        if watch:
            while True:
                frame = await read_frame(reader, "server")
                if frame.type == "bye":
                    print(f"bye {frame.data['reason']}", flush=True)
                    break
        else:
            writer.write(encode(Frame("bye", {"reason": "logout"})))
            await writer.drain()
    finally:
        writer.close()
        await writer.wait_closed()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="blacksite bot")
    parser.add_argument("--install-dir", type=Path, required=True)
    parser.add_argument("--watch", action="store_true", help="wait for the maintenance bye")
    parser.add_argument("--width", type=int, default=80)
    parser.add_argument("--height", type=int, default=24)
    args = parser.parse_args(argv)
    try:
        asyncio.run(run(args.install_dir, args.watch, args.width, args.height))
    except (OSError, ValueError, asyncio.TimeoutError, asyncio.IncompleteReadError) as exc:
        print(f"blacksite bot: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
