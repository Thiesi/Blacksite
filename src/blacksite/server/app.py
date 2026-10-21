"""Service lifecycle and asyncio I/O. Game state lives in the pure core."""

import asyncio
import os
import random
import shutil
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from blacksite import content as content_package
from blacksite.content.loader import ContentTree, content_files, load_content
from blacksite.content.validate import validate
from blacksite.server.auth import Authenticator, load_secret
from blacksite.server.clock import Clock, RealClock, TICK_HZ
from blacksite.server.core import Core
from blacksite.server.logging import Logs
from blacksite.server.protocol import Frame, ProtocolError, encode, read_frame
from blacksite.server.sessions import Session
from blacksite.server.world.registry import World
from blacksite.server.storage.db import Storage
from blacksite.server.storage.lease import Lease
from blacksite.server.transport import Listener
from blacksite.version import PACKAGE_VERSION

STOP_SECONDS = 10  # Architecture §3.4.
HELLO_SECONDS = 5  # Local transport policy, not a gameplay timer.


class Server:
    def __init__(self, install_dir: Path, tcp: bool = False, log_level: str = "INFO",
                 clock: Clock | None = None, spawn_zone: str | None = None) -> None:
        self.install_dir = install_dir.resolve()
        self.clock = clock or RealClock()
        self.log_level = log_level
        self.lease = Lease(self.install_dir / "world.db.sessions")
        self.listener = Listener(self.install_dir / "run", tcp)
        self.storage: Storage | None = None
        self.logs: Logs | None = None
        self.core: Core | None = None
        self.tasks: set[asyncio.Task[None]] = set()
        self.connections: set[asyncio.Task[None]] = set()
        self.stopped = asyncio.Event()
        self.stopping = False
        self.stop_requested = False
        self.spawn_zone = spawn_zone
        self.world: World | None = None
        self.failure: BaseException | None = None

    def _content(self) -> ContentTree:
        assert self.storage is not None
        target = self.install_dir / "content"
        if not target.is_dir() or self.storage.meta("content_package_version") != PACKAGE_VERSION:
            source = Path(content_package.__file__).parent
            staging = self.install_dir / "content.next"
            if staging.exists():
                raise RuntimeError("content.next exists; inspect interrupted content bootstrap")
            staging.mkdir()
            try:
                for path in content_files(source):
                    destination = staging / path.relative_to(source)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(path, destination)
                tree = load_content(staging, self.install_dir / "content.local")
                problems = validate(tree)
                if problems:
                    raise ValueError("invalid content: " + "; ".join(str(p) for p in problems))
            except BaseException:
                # Only remove the unpublished tree created by this attempt.
                shutil.rmtree(staging)
                raise
            previous = self.install_dir / "content.previous"
            if previous.exists():
                raise RuntimeError("content.previous exists; inspect interrupted content bootstrap")
            if target.exists():
                target.rename(previous)
            try:
                staging.rename(target)
            except BaseException:
                if previous.exists():
                    previous.rename(target)
                raise
            if previous.exists():
                shutil.rmtree(previous)
            self.storage.mark_dirty("meta", "content_package_version", PACKAGE_VERSION)
            self.storage.flush_now()
        tree = load_content(target, self.install_dir / "content.local")
        problems = validate(tree)
        if problems:
            raise ValueError("invalid content: " + "; ".join(str(p) for p in problems))
        return tree

    def rebuild(self, content: ContentTree) -> None:
        """Build pure zone state from content and durable per-zone seeds."""
        assert self.storage is not None
        seeds = self.storage.meta("rng_seeds")
        if not isinstance(seeds, dict):
            raise ValueError("invalid stored zone seeds")
        changed = False
        for zone_id in sorted(content.zones):
            if zone_id not in seeds:
                seeds[zone_id] = random.SystemRandom().getrandbits(64)
                changed = True
            if type(seeds[zone_id]) is not int:
                raise ValueError("invalid stored zone seed")
        if changed:
            self.storage.mark_dirty("meta", "rng_seeds", seeds)
            self.storage.flush_now()
        self.world = World(content, seeds)

    async def start(self) -> None:
        self.install_dir.mkdir(parents=True, exist_ok=True)
        self.lease.acquire()
        try:
            for name in ("run", "secrets", "logs", "backups", "content.local"):
                path = self.install_dir / name
                path.mkdir(exist_ok=True, mode=0o700)
                if os.name != "nt" and name in {"run", "secrets"}:
                    path.chmod(0o700)
            self.logs = Logs(self.install_dir / "logs", self.clock, self.log_level)
            self.storage = Storage(self.install_dir / "world.db", self.clock)
            content = self._content()
            self.rebuild(content)
            auth = Authenticator(load_secret(self.install_dir / "secrets" / "door.secret"),
                                 load_secret(self.install_dir / "secrets" / "admin.secret"), self.storage.banned)
            motd = content.text.get("motd")
            lines = motd.body.splitlines() if motd else []
            self.core = Core(self.clock, self.storage.origin, auth,
                asdict(content.keymaps) if content.keymaps else {},
                asdict(content.palette) if content.palette else {},
                random.SystemRandom().choice(lines) if lines else "", content,
                world=self.world if self.spawn_zone else None, spawn_zone=self.spawn_zone)
            self.core.audit = self._audit
            self.core.status_provider = self.status
            if self.stop_requested:
                self.core.request_stop()
                return
            await self.listener.start(self._connected)
            self._task(self._ticks())
            self._task(self._writer())
            self.logs.event("world open", content_hash=content.hash, season=self.storage.meta("season"))
        except BaseException:
            await self.stop()
            raise

    def status(self) -> dict[str, Any]:
        assert self.core is not None and self.storage is not None
        result = self.core.status()
        result["persistence_lag"] = self.storage.persistence_lag()
        result.update(uptime_s=result["uptime"], tick_p50_ms=result["tick"]["p50_ms"],
                      tick_p99_ms=result["tick"]["p99_ms"], persist_lag_s=result["persistence_lag"],
                      content_hash=self.core.loop.content.hash, season=self.storage.meta("season"))
        return result

    def _audit(self, row: dict[str, Any]) -> None:
        assert self.storage is not None and self.logs is not None
        self.storage.audit(row)
        self.logs.audit(row)

    def _task(self, coroutine: Any, connections: bool = False) -> None:
        task = asyncio.create_task(coroutine)
        group = self.connections if connections else self.tasks
        group.add(task)

        def done(finished: asyncio.Task[None]) -> None:
            group.discard(finished)
            if not finished.cancelled() and finished.exception() is not None:
                if self.logs:
                    self.logs.event("task failed", level="ERROR", error=type(finished.exception()).__name__)
                if not connections and self.core:
                    self.failure = finished.exception()
                    self.core.request_stop()

        task.add_done_callback(done)

    def _connected(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        if self.stopping:
            writer.close()
            return
        self._task(self._client(reader, writer), connections=True)

    async def _client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        assert self.core is not None
        session: Session | None = None
        receiver: asyncio.Task[None] | None = None
        wakeup: asyncio.Task[bool] | None = None
        try:
            hello = await asyncio.wait_for(read_frame(reader, "client"), HELLO_SECONDS)
            if self.stopping:
                raise ConnectionRefusedError("service is stopping")
            session = self.core.connect(hello)
            available = asyncio.Event()
            session.notify = available.set

            async def receive() -> None:
                assert session is not None and self.core is not None
                while not session.closed:
                    frame = await read_frame(reader, "client")
                    self.core.receive(session, frame)

            receiver = asyncio.create_task(receive())
            while True:
                while session.send_queue:
                    frame = session.send_queue.popleft()
                    writer.write(encode(frame))
                    await asyncio.wait_for(writer.drain(), 1)
                if session.closed:
                    break
                if receiver.done():
                    await receiver
                    break
                available.clear()
                wakeup = asyncio.create_task(available.wait())
                await asyncio.wait({receiver, wakeup}, return_when=asyncio.FIRST_COMPLETED)
                wakeup.cancel()
                await asyncio.gather(wakeup, return_exceptions=True)
                wakeup = None
        except asyncio.TimeoutError:
            # Before hello this is an idle handshake; afterwards the writer
            # is stalled. Neither condition says the credential was wrong.
            if session is None:
                writer.write(encode(Frame("bye", {"reason": "timeout", "text": "Connection timed out."})))
                try:
                    await asyncio.wait_for(writer.drain(), 1)
                except (OSError, asyncio.TimeoutError):
                    pass
        except (ValueError, TypeError, UnicodeError) as exc:
            reason = "banned" if str(exc) == "banned" else "protocol" if isinstance(exc, ProtocolError) else "auth"
            writer.write(encode(Frame("bye", {"reason": reason, "text": "Connection refused."})))
            try:
                await asyncio.wait_for(writer.drain(), 1)
            except (OSError, asyncio.TimeoutError):
                pass
        except (OSError, asyncio.IncompleteReadError):
            pass
        finally:
            if wakeup:
                wakeup.cancel()
                await asyncio.gather(wakeup, return_exceptions=True)
            if receiver:
                receiver.cancel()
                await asyncio.gather(receiver, return_exceptions=True)
            if session is not None:
                self.core.sessions.disconnect(session)
            writer.close()
            try:
                await asyncio.wait_for(writer.wait_closed(), 1)
            except (OSError, asyncio.TimeoutError):
                pass

    async def _ticks(self) -> None:
        assert self.core is not None
        while not self.core.stop_requested:
            if self.clock.now_tick() > self.core.loop.last_tick:
                began = time.perf_counter()
                self.core.loop.step()
                self.core.loop.record_timing(time.perf_counter() - began)
            await asyncio.sleep(1 / TICK_HZ / 2)

    async def _writer(self) -> None:
        assert self.storage is not None
        while True:
            await asyncio.sleep(1 / TICK_HZ)
            self.storage.flush_due()

    async def run(self) -> None:
        await self.start()
        try:
            assert self.core is not None
            while not self.core.stop_requested:
                await asyncio.sleep(0.05)
            if self.failure:
                raise RuntimeError("service task failed; see logs/server.log") from self.failure
        finally:
            await self.stop()

    def request_stop(self) -> None:
        """Latch OS stop requests even before the core has been built."""
        self.stop_requested = True
        if self.core:
            self.core.request_stop()

    async def stop(self) -> None:
        if self.stopping:
            await self.stopped.wait()
            return
        self.stopping = True
        try:
            async with asyncio.timeout(STOP_SECONDS):
                await self.listener.stop_accepting()
                if self.core:
                    self.core.shutdown()
                for task in self.tasks:
                    task.cancel()
                await asyncio.gather(*self.tasks, return_exceptions=True)
                if self.connections:
                    _, pending = await asyncio.wait(tuple(self.connections), timeout=2)
                    for task in pending:
                        task.cancel()
                    await asyncio.gather(*pending, return_exceptions=True)
                await self.listener.wait_closed()
        finally:
            try:
                if self.storage:
                    self.storage.close()
                    self.storage = None
            finally:
                try:
                    self.listener.cleanup()
                    if self.logs:
                        try:
                            self.logs.event("world closed")
                        finally:
                            self.logs.close()
                            self.logs = None
                finally:
                    self.lease.release()
                    self.stopped.set()
