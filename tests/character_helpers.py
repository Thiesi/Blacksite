"""Deterministic inputs through the production character core."""

from copy import deepcopy
from typing import Any
from blacksite.server.protocol import Frame
from tests.harness import FakeClient, HeadlessServer


def act(game: HeadlessServer, client: FakeClient, frame: Frame) -> None:
    if frame.type == "intent" and frame.data.get("name") == "menu_select":
        frame = Frame("intent", {"request_id": f"test-{game.clock.now_tick()}", "expected_revision": client.session.view_revision, **frame.data})
    client.send(frame)
    game.step(2)


def create(game: HeadlessServer, client: FakeClient, archetype: int = 1, name: str = "", card: str = "unmoored", commit: bool = True) -> list[dict[str, Any]]:
    game.step()
    for _ in range(archetype):
        act(game, client, Frame("intent", {"name": "menu_cursor", "args": {"delta": 1}}))
    act(game, client, Frame("intent", {"name": "menu_select", "args": {}}))
    wake = game.core.characters.wakes[client.session.id]
    act(game, client, Frame("line", {"id": wake.prompt_id, "text": name}))
    act(game, client, Frame("key", {"k": "s", "t": 0}))
    choices = [*game.core.loop.content.wake_cards, "none"]
    wake.cursor = choices.index(card)
    act(game, client, Frame("intent", {"name": "menu_select", "args": {}}))
    if not commit:
        return []
    effects = game.commit_characters()
    game.step()
    game.commit_characters()
    return effects


def state(game: HeadlessServer) -> dict[str, Any]:
    manager = game.core.characters
    return deepcopy({"players": [p.record() for p in manager.players.values()], "identities": manager.identities,
                     "serial": manager.serial, "cap": manager.cap,
                     "items": [item.record() for item in manager.items.values()]})


def place(game: HeadlessServer, client: FakeClient, zone_id: str, tile: tuple[int, int]) -> None:
    manager = game.core.characters
    avatar = manager.sim.avatars[client.session.user_id]
    if avatar.actor.zone:
        game.core.world.zones[avatar.actor.zone].deactivate(client.session.id, game.clock.now_tick())
    game.core.world.enter(avatar.actor, zone_id, tile)
    avatar.zone = client.session.subscribed = zone_id
    game.core.world.zones[zone_id].activate(client.session.id, game.clock.now_tick())
    game.step()
