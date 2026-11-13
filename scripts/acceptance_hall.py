"""S48c1a character creation through the Wake Hall, with ordinary keys.

Shared by the acceptance drivers that launch the door themselves. The
caller wakes in the hall with an unread body. Optionally they take a card
at the table, open the decant record with E beside the street door,
choose a template and a name, and walk back to the arrival tile, so a
script carries on from the same place as under the old Wake screens.
"""

from __future__ import annotations

import asyncio
from collections import deque
import time
from typing import Any, Awaitable, Callable

KEYS = {(1, 0): b"\x1b[C", (-1, 0): b"\x1b[D", (0, 1): b"\x1b[B", (0, -1): b"\x1b[A"}
CARDS_TILE = (8, 9)   # Beside the recruiter cards (8, 10).
DOOR_TILE = (37, 16)  # Beside the street door: E opens the record.


async def until(condition: Callable[[], bool], timeout: float = 10) -> None:
    async with asyncio.timeout(timeout):
        while not condition():
            await asyncio.sleep(.02)


async def walk(service: Any, avatar: Any, write: Callable[[bytes], Awaitable[None]],
               target: tuple[int, int], timeout: float = 120) -> None:
    """Walk with arrow keys along a shortest free path, replanning around traffic."""
    zone = service.world.zones[avatar.zone]
    deadline = time.monotonic() + timeout
    while avatar.actor.position != target:
        assert time.monotonic() < deadline, ("walk timeout", zone.id, avatar.actor.position, target)
        start = avatar.actor.position
        occupied = {a.position for a in zone.actors.values() if a is not avatar.actor
                    and not (a.behaviour.get("training") and a.owner != avatar.actor.id)}
        exits = {e.tile for e in zone.template.meta.exits if e.kind == "street"}
        pending, previous = deque([start]), {start: None}
        while pending and target not in previous:
            x, y = pending.popleft()
            for tile in ((x+1, y), (x, y+1), (x-1, y), (x, y-1)):
                if tile not in previous and tile not in occupied and zone.passable(tile) and tile not in exits:
                    previous[tile] = (x, y)
                    pending.append(tile)
        if target not in previous:
            await asyncio.sleep(.2)
            continue
        step = target
        while previous[step] != start:
            step = previous[step]
        await until(lambda: service.clock.now_tick() >= max(avatar.actor.cooldowns.get("move", 0),
                                                            avatar.actor.cooldowns.get("knockdown", 0)))
        await write(KEYS[step[0]-start[0], step[1]-start[1]])
        try:
            await until(lambda: avatar.actor.position != start, .6)
        except TimeoutError:
            pass  # Traffic took the tile first; replan from where the body is.


async def create(service: Any, session: Any, write: Callable[[bytes], Awaitable[None]], *,
                 archetype: int = 0, name: str = "", card: str | None = None, home: bool = True) -> Any:
    """Create a character the S48 way; returns the promoted player."""
    manager = service.core.characters
    avatar = manager.sim.avatars[session.user_id]
    wake = manager.wakes[session.id]
    start = avatar.actor.position

    def settled() -> bool:
        return session.ack_revision == session.view_revision

    if card is not None:
        await walk(service, avatar, write, CARDS_TILE)
        await until(settled)
        await write(b"e")
        await until(lambda: manager.screens.get(session.id, ("", 0))[0] == "cards" and settled())
        for index in range([*manager.content.wake_cards, "none"].index(card)):
            await write(b"\x1b[B")
            await until(lambda: manager.screens.get(session.id, ("", 0))[1] == index+1)
        await until(settled)
        await write(b"\r")
        await until(lambda: session.id not in manager.screens and settled())
    await walk(service, avatar, write, DOOR_TILE)
    await until(settled)
    await write(b"e")
    await until(lambda: wake.stage == "record" and settled())
    for index in range(archetype):
        await write(b"\x1b[B")
        await until(lambda: wake.cursor == index+1)
    await until(settled)
    await write(b"\r")
    await until(lambda: wake.stage == "name" and settled())
    await write(name.encode()+b"\r")
    await until(lambda: session.player_id in manager.players and not manager.unread(session.player_id))
    if home:
        await walk(service, avatar, write, start)
    return manager.players[session.player_id]


async def create_reading(caller: Any, service: Any, session: Any, **options: Any) -> Any:
    """`create` for a caller with no output pump of its own: read the
    stream into the caller's screen while creating, then hand it back."""
    async def pump() -> None:
        while chunk := await caller.read():
            caller.output.extend(chunk)
            caller.replay()
    task = asyncio.create_task(pump())
    try:
        return await create(service, session, caller.write, **options)
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
