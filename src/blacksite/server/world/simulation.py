"""Session-to-world adapter for the deterministic S03 tick loop."""

from dataclasses import dataclass, field
from typing import Any

from blacksite.server.clock import Clock
from blacksite.server.loop import TickContext
from blacksite.server.protocol import Frame
from blacksite.server.sessions import Session, Sessions
from blacksite.server.views.delta import ViewStore
from blacksite.server.views.zone_view import Perception, build
from blacksite.server.world.actors import Actor
from blacksite.server.world.movement import move, regenerate
from blacksite.server.world.registry import World

NIGHT_START_HOUR = 20  # Entity model 1.1: night lighting 20:00-06:00.
NIGHT_END_HOUR = 6


@dataclass
class Avatar:
    actor: Actor
    zone: str
    perception: Perception = field(default_factory=Perception)
    seen_zones: set[str] = field(default_factory=set)


class ZoneSimulation:
    def __init__(self, world: World, sessions: Sessions, clock: Clock, spawn_zone: str,
                 keymap: dict[str, Any]) -> None:
        if spawn_zone not in world.zones or world.zones[spawn_zone].template.meta.spawn is None:
            raise ValueError("spawn zone must exist and declare a passable spawn tile")
        self.world, self.sessions, self.clock = world, sessions, clock
        self.spawn_zone = spawn_zone
        self.keymap = keymap
        self.avatars: dict[str, Avatar] = {}
        self.views: dict[str, ViewStore] = {}
        self.published: dict[str, tuple[object, ...]] = {}
        self.serial = 0

    def connect(self, session: Session) -> None:
        if session.role != "caller":
            return
        avatar = self.avatars.get(session.user_id)
        if avatar is not None and session.player_id != avatar.actor.id:
            avatar = None
        if avatar is None:
            self.serial += 1
            avatar = Avatar(Actor(f"{self.sessions.origin}:actor:{self.serial}", session.door_info["handle"],
                                  session.door_info["handle"]), self.spawn_zone)
            self.avatars[session.user_id] = avatar
            tile = self.world.zones[avatar.zone].template.meta.spawn
        else:
            tile = avatar.actor.position
            avatar.actor.name = avatar.actor.handle = session.door_info["handle"]
        self.world.enter(avatar.actor, avatar.zone, self.world.free_tile(avatar.zone, tile))
        session.player_id = avatar.actor.id
        session.subscribed = avatar.zone
        self.world.zones[avatar.zone].activate(session.id, self.clock.now_tick())
        # A new terminal needs a full view, while sight memory belongs to the
        # short-lived reconnect avatar (persistent character memory is S07).
        avatar.perception.viewport = None
        self.views[session.id] = ViewStore()
        if avatar.zone not in avatar.seen_zones:
            for asset_id in self.world.zones[avatar.zone].template.meta.lore[:1]:
                asset = self.world.content.text.get(asset_id)
                if asset:
                    session.send(Frame("toast", {"text": asset.body.splitlines()[0], "role": "ui_text", "seconds": 8}))
            avatar.seen_zones.add(avatar.zone)

    def disconnect(self, session: Session) -> None:
        self.views.pop(session.id, None)
        self.published.pop(session.id, None)
        avatar = self.avatars.get(session.user_id)
        if session.role != "caller" or avatar is None or avatar.actor.id != session.player_id:
            return
        if avatar.actor.zone is not None:
            avatar.zone = avatar.actor.zone
            self.world.zones[avatar.zone].deactivate(session.id, self.clock.now_tick())
            self.world.leave(avatar.actor)

    def input(self, session: Session, frame: Frame, tick: int) -> None:
        avatar = self.avatars.get(session.user_id)
        if session.role != "caller" or avatar is None:
            return
        action = frame.data.get("name", "") if frame.type == "intent" else ""
        if frame.type == "key":
            selected = session.keymap_id
            table = next((item for item in self.keymap.get("keymaps", []) if item["id"] == selected), None)
            if table is not None:
                action = next((name for name, keys in table["bindings"].items() if frame.data["k"] in keys), "")
        if action == "resync":
            session.needs_full_view = True
        else:
            vector = frame.data.get("args", {}).get("dir")
            if action.startswith("move_"):
                vector, action = action[5:], "move"
            elif action.startswith("sprint_"):
                vector, action = action[7:], "sprint"
            if action in ("move", "sprint") and isinstance(vector, str):
                actor = avatar.actor
                if actor.zone in self.world.zones:
                    move(actor, self.world.zones[actor.zone], vector, tick, action == "sprint")

    def tick(self, ctx: TickContext) -> None:
        for session in tuple(self.sessions.active.values()):
            if session.closed:
                self.sessions.disconnect(session)
        live = {s.user_id for s in self.sessions.active.values() if s.role == "caller"}
        for user_id in set(self.avatars) - live - self.sessions.retired.keys():
            del self.avatars[user_id]
        for zone in self.world.zones.values():
            if zone.dormant:
                continue
            elapsed = zone.wake(ctx.tick)
            zone.compose(ctx.tick)
            for actor in zone.actors.values():
                if regenerate(actor, elapsed, ctx.tick):
                    zone.revision += 1

    def publish(self, ctx: TickContext) -> None:
        node_time = self.clock.now_local()
        night = node_time.hour >= NIGHT_START_HOUR or node_time.hour < NIGHT_END_HOUR
        for session in ctx.sessions:
            if session.id not in self.views or session.closed:
                continue
            avatar = self.avatars[session.user_id]
            zone = self.world.zones[avatar.zone]
            local = self.clock.now_local(session.door_info.get("timezone")).strftime("%H:%M")
            stamp = (zone.revision, local, night, session.caps["width"], session.caps["height"],
                     ctx.tick if zone.layers else None)
            if stamp == self.published.get(session.id) and not session.needs_full_view:
                continue
            body = build(avatar.actor, zone, avatar.perception, self.world.content,
                         session.caps["width"], session.caps["height"], local, night, ctx.tick)
            if self.views[session.id].publish(session, body, ctx.tick):
                self.published[session.id] = stamp
            elif body == (self.views[session.id].previous or {}).get("body"):
                self.published[session.id] = stamp
