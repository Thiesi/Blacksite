"""Entry point for `python -m blacksite.bot`."""

import argparse
import asyncio
import random
import sys
import time
from pathlib import Path

from blacksite.server.auth import load_secret, sign
from blacksite.server.protocol import Frame, encode, read_frame
from blacksite.server.transport import connect
from blacksite.version import PACKAGE_VERSION, PROTOCOL_MAJOR


async def run(install: Path, watch: bool, width: int, height: int, steps: int = 0, seed: int = 0, fire_steps: int = 0) -> None:
    secret_path = install / "secrets" / "door.secret"
    if not secret_path.is_file():
        raise ValueError("service has no door secret; start the service first")
    secret = load_secret(secret_path)
    info = {"user_id": "smoke-bot", "handle": "Smoke", "node_name": "local"}
    reader, writer = await asyncio.wait_for(connect(install), 5)
    walker: asyncio.Task[None] | None = None
    fighter: asyncio.Task[None] | None = None
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
        async def next_frame() -> Frame:
            frame = await read_frame(reader, "server")
            if frame.type in ("view", "delta"):
                writer.write(encode(Frame("ack", {"rev": frame.data["rev"]})))
                await writer.drain()
            if fire_steps and frame.type == "prompt" and frame.data.get("kind") == "line" and str(frame.data.get("id","")).startswith("wake:"):
                writer.write(encode(Frame("line",{"id":frame.data["id"],"text":"Smoke"})))
                await writer.drain()
            if fire_steps and frame.type == "view" and frame.data.get("kind") == "wake":
                stage = frame.data["body"].get("stage")
                if stage == "archetype":
                    writer.write(encode(Frame("intent",{"name":"menu_select","args":{},"expected_revision":frame.data["rev"],"request_id":"bot-wake"})))
                elif stage == "briefing": writer.write(encode(Frame("key",{"k":"s","t":0})))
                elif stage == "card": writer.write(encode(Frame("intent",{"name":"menu_close","args":{}})))
                await writer.drain()
            return frame

        async with asyncio.timeout(5):
            while (await next_frame()).type != "pong":
                pass
        print(f"pong {(time.perf_counter() - began) * 1000:.3f} ms", flush=True)

        async def walk() -> None:
            rng = random.Random(seed)
            for index in range(steps):
                writer.write(encode(Frame("intent", {"name": "move", "args": {"dir": rng.choice(
                    ("up", "down", "left", "right", "up_left", "up_right", "down_left", "down_right"))}})))
                await writer.drain()
                await asyncio.sleep(.2)
            print(f"walk {steps} inputs", flush=True)
            if not watch and not fire_steps:
                writer.write(encode(Frame("bye", {"reason": "logout"})))
                await writer.drain()

        async def fight() -> None:
            for _ in range(fire_steps):
                for name in ("target_clear","target_next","fire"):
                    writer.write(encode(Frame("intent",{"name":name,"args":{}})))
                await writer.drain()
                await asyncio.sleep(.2)
            print(f"fire {fire_steps} attempts",flush=True)
            if not watch:
                writer.write(encode(Frame("bye",{"reason":"logout"})))
                await writer.drain()

        if steps:
            walker = asyncio.create_task(walk())
        fighter = asyncio.create_task(fight()) if fire_steps else None
        if watch or steps or fire_steps:
            while True:
                frame = await next_frame()
                if frame.type == "bye":
                    print(f"bye {frame.data['reason']}", flush=True)
                    break
        else:
            writer.write(encode(Frame("bye", {"reason": "logout"})))
            await writer.drain()
    finally:
        if fighter:
            fighter.cancel()
            await asyncio.gather(fighter,return_exceptions=True)
        if walker:
            walker.cancel()
            await asyncio.gather(walker, return_exceptions=True)
        writer.close()
        await writer.wait_closed()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="blacksite bot")
    parser.add_argument("--install-dir", type=Path, required=True)
    parser.add_argument("--watch", action="store_true", help="wait for the maintenance bye")
    parser.add_argument("--width", type=int, default=80)
    parser.add_argument("--height", type=int, default=24)
    parser.add_argument("--walk", type=int, default=0, metavar="STEPS", help="send a seeded random walk, then leave")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--fire",type=int,default=0,metavar="ATTEMPTS",help="target nearest and fire using server cooldowns")
    args = parser.parse_args(argv)
    try:
        if args.walk < 0 or args.fire < 0:
            parser.error("--walk and --fire must be nonnegative")
        asyncio.run(run(args.install_dir, args.watch, args.width, args.height, args.walk, args.seed,args.fire))
    except (OSError, ValueError, asyncio.TimeoutError, asyncio.IncompleteReadError) as exc:
        print(f"blacksite bot: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
