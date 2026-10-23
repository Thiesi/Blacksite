"""Two I/O pumps around the pure display model."""

import asyncio
import signal
import time
import uuid

from blacksite.door import doorinfo
from blacksite.door.cells import CellBuffer
from blacksite.door.connection import Connection, Reconnect
from blacksite.door.doorinfo import DoorInfo
from blacksite.door.keys import KeyDecoder, ESCAPE_TIMEOUT_SECONDS
from blacksite.door.model import Display
from blacksite.door.terminal import Terminal
from blacksite.server.protocol import Frame, ProtocolError, read_frame


async def read_input(terminal: Terminal, decoder: KeyDecoder) -> bytes | None:
    """Give queued continuation bytes priority over an expired timer."""
    if decoder.buffer != b"\x1b" or decoder.escape_at is None:
        return await terminal.read()
    try:
        return await asyncio.wait_for(terminal.read(), max(
            0.001, decoder.escape_at + ESCAPE_TIMEOUT_SECONDS - time.monotonic()))
    except asyncio.TimeoutError:
        # Rendering or pipe backpressure can delay both the read coroutine
        # and its timer. Cancellation must not split bytes already in stdin.
        return terminal.read_pending()


async def run(info: DoorInfo, terminal: Terminal) -> None:
    model = Display(info, uuid.uuid4().hex)
    connection = Connection()
    decoder = KeyDecoder()
    changed = asyncio.Event()
    retry = Reconnect()
    started = time.monotonic()
    blocked = False
    old_signal: object = None
    resize_requested = False

    def resize(signum: int, frame: object) -> None:
        nonlocal resize_requested
        resize_requested = True
        changed.set()

    if hasattr(signal, "SIGUSR1"):
        old_signal = signal.signal(signal.SIGUSR1, resize)

    async def send(frames: list[Frame]) -> None:
        for frame in frames:
            try:
                await connection.send(frame)
            except (OSError, asyncio.TimeoutError):
                model.connected = False
                changed.set()
                break

    async def input_pump() -> None:
        while not model.leaving:
            data = await read_input(terminal, decoder)
            if data == b"":
                model.leaving = True
                changed.set()
                return
            now = time.monotonic()
            keys = decoder.feed(data, now) if data else []
            keys += decoder.flush(now)
            for key in keys:
                if blocked:
                    model.leaving = True
                else:
                    await send(model.key(key, now))
            if keys:
                changed.set()

    async def output_pump() -> None:
        nonlocal info, blocked, resize_requested
        dial: asyncio.Task[Frame] | None = None
        incoming: asyncio.Task[Frame] | None = None
        last_ping = started
        countdown = -1

        async def disconnected(now: float) -> None:
            nonlocal incoming
            model.connected = False
            if incoming:
                incoming.cancel()
                await asyncio.gather(incoming, return_exceptions=True)
                incoming = None
            await connection.close()
            retry.failed(now)

        try:
            while not model.leaving:
                changed.clear()
                now = time.monotonic()
                if resize_requested:
                    resize_requested = False
                    try:
                        import os
                        info = doorinfo.read(os.environ)
                        model.resize(info)
                        if model.connected:
                            await send([Frame("resize", {"width": info.width, "height": info.height})])
                    except ValueError:
                        model.leaving = True
                        continue
                if not model.connected and not blocked:
                    if retry.started is not None and retry.remaining(now) <= 0:
                        model.leaving = True
                        continue
                    if dial is None and now >= retry.next_at:
                        if retry.started is None:
                            retry.started = now
                        timeout = min(5, max(0.01, retry.started + 60 - now)) if retry.started is not None else 5
                        dial = asyncio.create_task(connection.open(info, timeout))
                        dial.add_done_callback(lambda task: changed.set())
                    if retry.started is not None:
                        remaining = retry.remaining(now)
                        if remaining != countdown:
                            countdown = remaining
                            model.kind, model.body = "text", {"title": "DISCONNECTED", "lines": ["The city is dark right now.", f"You try again for {remaining} seconds.", "Ctrl-X leaves."], "page": 1, "pages": 1}
                            model.local = None
                            model.dirty = model.force_full = True
                if dial is not None and dial.done():
                    try:
                        frame = dial.result()
                        if frame.type == "bye":
                            reason = frame.data["reason"]
                            blocked = reason in ("banned", "auth", "forbidden", "protocol")
                            if blocked:
                                model.refused(reason)
                                await connection.close()
                            else:
                                await disconnected(now)
                        else:
                            model.receive(frame, now)
                            retry.reset()
                            countdown = -1
                            last_ping = now
                    except (OSError, ValueError, asyncio.TimeoutError, asyncio.IncompleteReadError):
                        await disconnected(now)
                    dial = None
                if incoming is not None and incoming.done():
                    try:
                        frame = incoming.result()
                        incoming = None
                        await send(model.receive(frame, now))
                        if frame.type == "bye":
                            if frame.data["reason"] in ("banned", "auth", "forbidden", "protocol"):
                                blocked = True
                                model.refused(frame.data["reason"])
                                await connection.close()
                            elif frame.data["reason"] in ("replaced", "logout"):
                                model.leaving = True
                            else:
                                await disconnected(now)
                    except (OSError, ValueError, asyncio.TimeoutError, asyncio.IncompleteReadError):
                        await disconnected(now)
                if not model.connected and connection.writer is not None and dial is None:
                    await disconnected(now)
                if model.connected and not model.leaving and incoming is None:
                    # Keep a read armed before the idle wait. Otherwise a
                    # rendered frame leaves no reader to wake us for the next
                    # one, accumulating a second of lag per social/view frame.
                    assert connection.reader is not None
                    incoming = asyncio.create_task(read_frame(connection.reader, "server"))
                    incoming.add_done_callback(lambda task: changed.set())
                if model.connected and now - last_ping >= 10:
                    await send([Frame("ping", {"t": int((now - started) * 1000)})])
                    last_ping = now
                model.update(now - started, now)
                output, ack = model.render(now)
                if output:
                    terminal.write(output)
                    if ack:
                        await send([ack])
                # Data and keys wake immediately; idle rendering stays asleep.
                delay = max(0.001, min(1.0, model.last_render + 0.1 - now)) if model.dirty else 1.0
                try:
                    await asyncio.wait_for(changed.wait(), delay)
                except asyncio.TimeoutError:
                    pass
        finally:
            for task in (dial, incoming):
                if task:
                    task.cancel()
            await asyncio.gather(*(task for task in (dial, incoming) if task), return_exceptions=True)

    tasks: list[asyncio.Task[None]] = []
    try:
        terminal.enter()
        # Title appears before the handshake, even when the service is absent.
        initial, _ = model.render(started)
        terminal.write(initial)
        tasks = [asyncio.create_task(input_pump()), asyncio.create_task(output_pump())]
        _, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        model.leaving = True
        for task in pending:
            task.cancel()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, BaseException) and not isinstance(result, (asyncio.CancelledError, OSError, ValueError, ProtocolError)):
                raise result
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await connection.close()
        farewell = CellBuffer(info.width, 2)
        farewell.put(0, 0, "Karst keeps your place.")
        terminal.leave(farewell.full())
        if hasattr(signal, "SIGUSR1") and old_signal is not None:
            signal.signal(signal.SIGUSR1, old_signal)
