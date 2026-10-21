"""Local listener and discovery files; no simulation dependencies."""

import asyncio
import errno
import os
import stat
from collections.abc import Callable
from pathlib import Path


class Listener:
    def __init__(self, run: Path, tcp: bool) -> None:
        self.run = run
        self.tcp = tcp or os.name == "nt"
        self.server: asyncio.Server | None = None
        self.owned: list[Path] = []

    async def start(self, connected: Callable[[asyncio.StreamReader, asyncio.StreamWriter], None]) -> None:
        if self.tcp:
            self.server = await asyncio.start_server(connected, "127.0.0.1", 0)
            port = self.run / "port"
            self.owned.append(port)
            port.write_text(str(self.server.sockets[0].getsockname()[1]), encoding="ascii")
        else:
            path = self.run / "blacksite.sock"
            if path.exists():
                if not stat.S_ISSOCK(path.stat().st_mode):
                    raise RuntimeError("socket path is not a socket")
                try:
                    _, writer = await asyncio.wait_for(asyncio.open_unix_connection(path), 1)
                except OSError as exc:
                    if exc.errno not in (errno.ECONNREFUSED, errno.ENOENT):
                        raise
                    path.unlink(missing_ok=True)
                else:
                    writer.close()
                    await writer.wait_closed()
                    raise RuntimeError("socket already has a live listener")
            self.server = await asyncio.start_unix_server(connected, path=path)
            self.owned.append(path)
            path.chmod(0o600)
        pid = self.run / "blacksite.pid"
        self.owned.append(pid)
        pid.write_text(str(os.getpid()), encoding="ascii")
        if os.name != "nt":
            for path in self.owned:
                path.chmod(0o600)

    async def stop_accepting(self) -> None:
        if self.server is not None:
            self.server.close()

    async def wait_closed(self) -> None:
        # Python 3.12+ also waits for existing clients here. Drain them first.
        if self.server is not None:
            await self.server.wait_closed()
            self.server = None

    def cleanup(self) -> None:
        for path in self.owned:
            path.unlink(missing_ok=True)
        self.owned.clear()


async def connect(install: Path) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
    port = install / "run" / "port"
    if port.exists():
        return await asyncio.open_connection("127.0.0.1", int(port.read_text(encoding="ascii")))
    if os.name == "nt":
        raise ConnectionRefusedError("service not running: no local TCP port file")
    return await asyncio.open_unix_connection(install / "run" / "blacksite.sock")
