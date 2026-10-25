"""Raw native stdio. All visible text is rendered through CellBuffer."""

import asyncio
import os
import sys
from typing import Any

ENTER = b"\x1b[?1049h\x1b[?25l\x1b[0m\x1b[2J\x1b[H"
LEAVE = b"\x1b[0m\x1b[?25h\x1b[?1049l\x1b[2J\x1b[H"


class Terminal:
    def __init__(self, local: bool = False) -> None:
        self.local = local
        self.input = sys.stdin.fileno()
        self.output = sys.stdout.fileno()
        self.saved: Any = None
        self.blocking: bool | None = None
        self.entered = False

    def write(self, data: bytes) -> None:
        while data:
            count = os.write(self.output, data)
            if count <= 0:
                raise BrokenPipeError
            data = data[count:]

    def enter(self) -> None:
        if os.name == "nt":
            import msvcrt
            msvcrt.setmode(self.input, os.O_BINARY)
            msvcrt.setmode(self.output, os.O_BINARY)
        elif os.isatty(self.input):
            import termios
            import tty
            self.saved = termios.tcgetattr(self.input)
            tty.setraw(self.input)
        if not (os.name == "nt" and self.local):
            self.blocking = os.get_blocking(self.input)
            os.set_blocking(self.input, False)
        self.entered = True
        self.write(ENTER)

    def read_pending(self) -> bytes | None:
        """Drain ready input before declaring an Escape deadline expired."""
        if os.name == "nt" and self.local:
            import msvcrt
            if not msvcrt.kbhit():
                return None
            char = msvcrt.getwch()
            if char in ("\x00", "\xe0"):
                code = msvcrt.getwch()
                return {"H": b"\x1b[A", "P": b"\x1b[B", "K": b"\x1b[D", "M": b"\x1b[C",
                        "G": b"\x1b[H", "O": b"\x1b[F", "I": b"\x1b[5~", "Q": b"\x1b[6~",
                        "?": b"\x1b[15~", "@": b"\x1b[17~", "A": b"\x1b[18~",
                        "B": b"\x1b[19~", "C": b"\x1b[20~", "D": b"\x1b[21~"}.get(code, b"\x00")
            return char.encode("utf-8", errors="replace")
        try:
            return os.read(self.input, 4096)
        except BlockingIOError:
            return None

    async def read(self) -> bytes:
        if os.name == "nt" and self.local:
            while (data := self.read_pending()) is None:
                await asyncio.sleep(0.025)
            return data
        if os.name == "nt":
            while True:
                try:
                    return os.read(self.input, 4096)
                except BlockingIOError:
                    await asyncio.sleep(0.025)
        loop = asyncio.get_running_loop()
        ready: asyncio.Future[None] = loop.create_future()

        def readable() -> None:
            if not ready.done():
                ready.set_result(None)

        loop.add_reader(self.input, readable)
        try:
            await ready
            try:
                return os.read(self.input, 4096)
            except BlockingIOError:
                return b"\x00"
        finally:
            loop.remove_reader(self.input)

    def leave(self, farewell: bytes) -> None:
        try:
            if self.entered:
                self.write(LEAVE + farewell + b"\r\n")
        finally:
            if self.saved is not None:
                import termios
                termios.tcsetattr(self.input, termios.TCSANOW, self.saved)
            if self.blocking is not None:
                os.set_blocking(self.input, self.blocking)
            self.entered = False
