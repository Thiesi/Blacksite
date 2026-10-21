"""One authenticated local operator request, using the S03 wire contract."""

import asyncio
import json
from pathlib import Path
from typing import Any

from blacksite.server.auth import sign
from blacksite.server.protocol import Frame, encode, read_frame
from blacksite.server.transport import connect
from blacksite.version import PACKAGE_VERSION, PROTOCOL_MAJOR

NOT_RUNNING = "service not running; start it with `blacksite serve` or your rc.d script"


async def request(install: Path, command: str) -> Any:
    writer: asyncio.StreamWriter | None = None
    try:
        async with asyncio.timeout(5):
            # A client command never bootstraps credentials.
            try:
                secret = bytes.fromhex((install / "secrets" / "admin.secret").read_text(encoding="ascii").strip())
                reader, writer = await connect(install)
            except (FileNotFoundError, ConnectionRefusedError) as exc:
                raise RuntimeError(NOT_RUNNING) from exc
            if len(secret) != 32:
                raise ValueError("invalid admin secret")
            info = {"bbs_user_id": "operator", "handle": "operator"}
            writer.write(encode(Frame("hello", {"proto": PROTOCOL_MAJOR, "door_info": info,
                "hmac": sign(info, secret), "client_version": PACKAGE_VERSION,
                "caps": {"width": 80, "height": 24, "tier": "256", "unicode": True}})))
            await writer.drain()
            if (await read_frame(reader, "server")).type != "welcome":
                raise RuntimeError("operator authentication refused")
            writer.write(encode(Frame("admin." + command)))
            await writer.drain()
            while True:
                frame = await read_frame(reader, "server")
                if frame.type == "bye":
                    raise RuntimeError("operator request refused: " + frame.data["reason"])
                if frame.type == "view" and frame.data["body"].get("title") == "admin." + command:
                    return json.loads(frame.data["body"]["lines"][0])
    finally:
        if writer is not None:
            writer.close()
            try:
                await asyncio.wait_for(writer.wait_closed(), 1)
            except (OSError, asyncio.TimeoutError):
                pass
