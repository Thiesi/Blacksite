"""Versioned local protocol I/O; no game rules or service spawning."""

import asyncio
from dataclasses import dataclass

from blacksite.door.doorinfo import DoorInfo
from blacksite.door.palette import resolve_tier
from blacksite.server.auth import sign
from blacksite.server.protocol import Frame, ProtocolError, encode, read_frame
from blacksite.server.transport import connect
from blacksite.version import PACKAGE_VERSION, PROTOCOL_MAJOR


@dataclass
class Reconnect:
    started: float | None = None
    next_at: float = 0
    attempt: int = 0

    def failed(self, now: float) -> None:
        if self.started is None:
            self.started = now
        delays = (1, 2, 4, 8, 16, 30)  # Architecture §2.2/§8.2 and S04.
        self.next_at = min(self.started + 60, now + delays[min(self.attempt, len(delays) - 1)])
        self.attempt += 1

    def remaining(self, now: float) -> int:
        return max(0, int(60 - (now - self.started) + 0.999)) if self.started is not None else 60

    def reset(self) -> None:
        self.started = None
        self.next_at = 0
        self.attempt = 0


class Connection:
    def __init__(self) -> None:
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None
        self.lock = asyncio.Lock()

    async def open(self, info: DoorInfo, timeout: float = 5) -> Frame:
        try:
            async with asyncio.timeout(timeout):
                # Read only: a client never creates or rotates service secrets.
                secret = bytes.fromhex((info.install / "secrets" / "door.secret").read_text(encoding="ascii").strip())
                if len(secret) != 32:
                    raise ValueError("invalid door secret")
                self.reader, self.writer = await connect(info.install)
                await self.send(Frame("hello", {"proto": PROTOCOL_MAJOR, "door_info": info.raw,
                    "hmac": sign(info.raw, secret), "client_version": PACKAGE_VERSION,
                    "caps": {"width": info.width, "height": info.height,
                             "tier": resolve_tier(info.color_depth), "unicode": True}}))
                frame = await read_frame(self.reader, "server")
                if frame.type not in ("welcome", "bye"):
                    raise ProtocolError("expected welcome")
                return frame
        except BaseException:
            await self.close()
            raise

    async def send(self, frame: Frame) -> None:
        if self.writer is None:
            raise ConnectionError("disconnected")
        async with self.lock:
            async with asyncio.timeout(1):
                self.writer.write(encode(frame))
                await self.writer.drain()

    async def close(self) -> None:
        writer, self.writer = self.writer, None
        self.reader = None
        if writer is not None:
            writer.close()
            try:
                await asyncio.wait_for(writer.wait_closed(), 1)
            except (OSError, asyncio.TimeoutError):
                pass
