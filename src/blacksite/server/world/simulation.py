"""Session-to-world adapter for the deterministic S03 tick loop."""

from dataclasses import dataclass, field
from typing import Any
from collections.abc import Callable

from blacksite.server.clock import Clock, TICK_HZ
from blacksite.server.loop import TickContext
from blacksite.server.protocol import Frame
from blacksite.server.sessions import Session, Sessions
from blacksite.server.views.delta import ViewStore
from blacksite.server.views.zone_view import Perception, build
from blacksite.server.world.actors import Actor
from blacksite.server.world.movement import move, regenerate
from blacksite.server.world.registry import World
from blacksite.server.world.exits import DepartureHolds, Travel, permitted, schedule
from blacksite.server.world.city import overview
from blacksite.server.wake import wrapped
from blacksite.content.schema import Exit

NIGHT_START_HOUR = 20  # Entity model 1.1: night lighting 20:00-06:00.
NIGHT_END_HOUR = 6
MENU_TIMEOUT_SECONDS = 60  # Terminal UI §4: contested/open menu timeout.


@dataclass
class Avatar:
    actor: Actor
    zone: str
    perception: Perception = field(default_factory=Perception)
    seen_zones: set[str] = field(default_factory=set)
    travel: Travel | None = None


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
        self.me_provider: Callable[[Session], dict[str, Any]] = lambda session: {}
        self.target_provider: Callable[[Actor], dict[str, Any] | None] | None = None
        self.access_provider: Callable[[Session], dict[str, Any]] = lambda session: {}
        self.maps: dict[str, tuple[int, int | None]] = {}
        self.map_opened: dict[str, int] = {}
        self.overlays: dict[str, object] = {}
        self.external_views: dict[str, tuple[str, dict[str, Any]]] = {}
        self.departures = DepartureHolds()
        self.locked_exits: set[tuple[str, str]] = set()  # S15-owned control state.
        self.arrival_hook: Callable[[Session, Avatar], None] = lambda session, avatar: None
        self.scout_provider: Callable[[Session], tuple[set[tuple[int,int]],set[str]]] = lambda session:(set(),set())
        self.crew_view: Callable[[Session, dict[str, Any]], None] = lambda session, body: None
        self.fare_menu: Callable[[Session, Any], bool] = lambda session, exit: False
        self.travel_refusal: Callable[[Session, Exit], str | None] = lambda session, exit: None

    def discover(self, session: Session, avatar: Avatar) -> None:
        if avatar.zone in avatar.seen_zones:
            return
        avatar.seen_zones.add(avatar.zone)
        for asset_id in self.world.zones[avatar.zone].template.meta.lore[:1]:
            asset = self.world.content.text.get(asset_id)
            if asset:
                session.send(Frame("toast", {"text": asset.body.splitlines()[0], "role": "ui_text", "seconds": 8}))

    def reset_view(self, session: Session, avatar: Avatar) -> None:
        avatar.perception.viewport = avatar.perception.grid_key = None
        self.views[session.id] = ViewStore()
        self.published.pop(session.id, None)
        self.overlays.pop(session.id, None)
        session.needs_full_view = True

    def log(self, session: Session, text: str) -> None:
        session.send(Frame("log", {"lines": [{"channel": "zone", "text": text, "role": "chan_zone",
                                                "at": self.clock.now_utc().isoformat()}]}))

    def transition(self, session: Session, avatar: Avatar, now: float, tick: int) -> None:
        travel = avatar.travel
        if travel is None:
            return
        if travel.exit.kind == "tram" and not travel.departed:
            self.departures.apply((avatar.zone, travel.exit.id), travel)
        if now >= travel.departure and not travel.departed:
            self.world.zones[avatar.zone].deactivate(session.id, tick)
            self.world.leave(avatar.actor)
            travel.departed = True
            if travel.exit.kind == "tram":
                self.log(session, "The tram hums.")
            self.reset_view(session, avatar)
        if travel.departed and now >= travel.arrival:
            target = travel.exit.target_zone
            try:
                tile = self.world.free_tile(target, travel.exit.target_tile)
            except ValueError:
                # A temporarily occupied arrival never crashes the tick or
                # drops the body. Retry while absent from both zones.
                return
            self.world.enter(avatar.actor, target, tile)
            avatar.zone = session.subscribed = target
            self.world.zones[target].activate(session.id, tick)
            avatar.travel = None
            self.reset_view(session, avatar)
            self.discover(session, avatar)
            self.arrival_hook(session, avatar)
            self.log(session, "You arrive at " + self.world.zones[target].template.meta.name + ".")

    def interact(self, session: Session, avatar: Avatar, tick: int, *, street: bool = False) -> None:
        zone = self.world.zones[avatar.zone]
        actor = avatar.actor
        adjacent = lambda tile: max(abs(tile[0] - actor.x), abs(tile[1] - actor.y)) <= 1
        candidates = [ex for ex in zone.template.meta.exits
                      if (not ex.hidden or not street and ex.tile == actor.position)
                      and (ex.tile == actor.position if street else adjacent(ex.tile))
                      and (not street or ex.kind == "street")]
        candidates.sort(key=lambda ex: (ex.tile != actor.position, ex.id))
        if candidates:
            ex = candidates[0]
            if ex.target_zone not in self.world.zones:
                self.log(session, "Construction blocks this route.")
            elif (zone.id, ex.id) in self.locked_exits or not permitted(ex, self.access_provider(session)):
                self.log(session, ex.locked_text or "You do not meet this exit's requirement.")
            elif reason := self.travel_refusal(session, ex):
                self.log(session, reason)
            elif self.fare_menu(session, ex):
                pass
            else:
                avatar.travel = schedule(ex, self.clock.now_utc().timestamp())
                self.reset_view(session, avatar)
                self.transition(session, avatar, self.clock.now_utc().timestamp(), tick)
            return
        if street:
            return
        objects = sorted((obj for obj in zone.objects.values() if adjacent(obj.spec.tile)),
                         key=lambda obj: (obj.spec.tile != actor.position, obj.spec.id))
        if objects:
            obj = objects[0]
            if obj.spec.params.get("unavailable_target"):
                self.log(session, "Construction blocks this route.")
            elif obj.spec.kind in ("door", "apartment_door", "gate", "shutter") and obj.spec.params.get("locked") and not obj.open:
                self.log(session, "The door is locked. Its core controls the latch.")
            elif obj.spec.kind in ("door", "apartment_door", "gate", "shutter"):
                zone.set_door(obj.spec.id, not obj.open)
            else:
                self.log(session, str(obj.spec.params.get("name", obj.spec.id)))

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
        self.discover(session, avatar)

    def disconnect(self, session: Session) -> None:
        self.views.pop(session.id, None)
        self.published.pop(session.id, None)
        self.maps.pop(session.id, None)
        self.map_opened.pop(session.id, None)
        self.overlays.pop(session.id, None)
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
        key = frame.data.get("k", "") if frame.type == "key" else ""
        if avatar.travel:
            leaving_platform = key in ("escape", "b", "B") or action in ("move", "sprint") or action.startswith(("move_", "sprint_"))
            if not avatar.travel.departed and leaving_platform:
                avatar.travel = None
                self.reset_view(session, avatar)
                if key in ("escape", "b", "B"):
                    return
            else:
                if key == "escape":
                    session.send(Frame("toast", {"text": "The log remains below. Your journey continues.", "role": "ui_text", "seconds": 8}))
                if action == "resync":
                    session.needs_full_view = True
                return
        if session.id in self.maps:
            cursor, page = self.maps[session.id]
            if action == "menu_close" or key in ("escape", "b", "B"):
                self.maps.pop(session.id, None)
                self.map_opened.pop(session.id, None)
                self.reset_view(session, avatar)
            elif action == "menu_cursor":
                rows = overview(self.world.content, avatar.zone, avatar.seen_zones, cursor, session.caps["width"])["rows"]
                self.maps[session.id] = (max(0, min(len(rows)-1, cursor + frame.data.get("args", {}).get("delta", 0))), None)
            elif action == "menu_select":
                self.maps[session.id] = (cursor, 0)
            elif page is not None and key:
                delta = -1 if key in ("pageup", "pgup", "up") else 1
                self.maps[session.id] = (cursor, max(0, page + delta))
            return
        if action == "map" or key in ("m", "M"):
            self.maps[session.id] = (0, None)
            self.map_opened[session.id] = tick
        elif action == "interact" or key in ("e", "E"):
            self.interact(session, avatar, tick)
        elif action == "resync":
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
                    if move(actor, self.world.zones[actor.zone], vector, tick, action == "sprint"):
                        self.interact(session, avatar, tick, street=True)

    def tick(self, ctx: TickContext) -> None:
        for session in tuple(self.sessions.active.values()):
            if session.closed:
                self.sessions.disconnect(session)
        live = {s.user_id for s in self.sessions.active.values() if s.role == "caller"}
        now = self.clock.now_utc().timestamp()
        for session in tuple(self.sessions.active.values()):
            avatar = self.avatars.get(session.user_id)
            if avatar and not session.closed:
                self.transition(session, avatar, now, ctx.tick)
                # UI §4: menus do not pause a body in dangerous streets.
                if (session.id in self.maps and ctx.tick - self.map_opened[session.id] >= MENU_TIMEOUT_SECONDS * TICK_HZ
                        and self.world.zones[avatar.zone].allows_hostile(avatar.actor.position)):
                    self.maps.pop(session.id)
                    self.map_opened.pop(session.id)
                    self.reset_view(session, avatar)
                    session.send(Frame("toast", {"text": "Your map closes. The street is not protected.",
                                                  "role": "ui_text", "seconds": 8}))
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
            overlay = None
            kind = "text"
            if session.id in self.external_views:
                kind, overlay = self.external_views[session.id]
            elif avatar.travel:
                ride = avatar.travel
                riding_text = "The tram hums." if ride.exit.kind == "tram" else "You travel between zones."
                overlay = {"title": "The tram hums." if ride.exit.kind == "tram" and ride.departed else "TRAVEL",
                           "lines": [riding_text if ride.departed else "You wait on the platform.",
                                     "Arrival follows departure." if ride.departed else f"Departure in {max(0, int(ride.departure - self.clock.now_utc().timestamp()))} s."],
                           "hint": "Esc shows the log. The journey continues. Ctrl-X leaves." if ride.departed
                                   else "Move or Esc/B cancels boarding. Ctrl-X leaves."}
            elif session.id in self.maps:
                cursor, page = self.maps[session.id]
                body = overview(self.world.content, avatar.zone, avatar.seen_zones, cursor, session.caps["width"])
                if page is None:
                    kind, overlay = "menu", body
                else:
                    lines = wrapped(body["detail"], session.caps["width"] - 28)
                    count = max(1, session.caps["height"] - 10)
                    pages = max(1, (len(lines) + count - 1) // count)
                    page = min(page, pages - 1)
                    self.maps[session.id] = cursor, page
                    overlay = {"title": body["title"], "lines": lines[page*count:(page+1)*count],
                               "page": page+1, "pages": pages, "hint": "PgUp/PgDn reads  Esc/B returns to the street"}
            if overlay is not None:
                if kind == "lattice":
                    if self.views[session.id].publish(session, overlay, ctx.tick, kind="lattice"):
                        self.overlays[session.id] = kind, overlay
                    continue
                if (kind, overlay) != self.overlays.get(session.id) or session.needs_full_view:
                    if session.publish_view(Frame("view", {"rev": session.view_revision+1, "kind": kind, "body": overlay}), None, ctx.tick):
                        self.overlays[session.id] = kind, overlay
                        # A later delta must use this displayed document as
                        # its base. Resume with a snapshot after any menu/text
                        # overlay, rather than patching stale zone/sector data.
                        self.views[session.id] = ViewStore()
                continue
            zone = self.world.zones[avatar.zone]
            local = self.clock.now_local(session.door_info.get("timezone")).strftime("%H:%M")
            stamp = (zone.id, zone.revision, local, night, session.caps["width"], session.caps["height"],
                     ctx.tick if zone.layers or avatar.actor.behaviour.get("channel") else None)
            if stamp == self.published.get(session.id) and not session.needs_full_view:
                continue
            scouted,scouted_actors = self.scout_provider(session)
            body = build(avatar.actor, zone, avatar.perception, self.world.content,
                         session.caps["width"], session.caps["height"], local, night, ctx.tick,
                         scouted,scouted_actors)
            body["me"].update(self.me_provider(session))
            if self.target_provider:
                body["target"] = self.target_provider(avatar.actor)
                body["hint"] = "Tab target  F fire  X weapon  1-5 quick  V abilities  E interact  I inventory  ? help"
                remaining = max(0,avatar.actor.cooldowns.get("weapon",0)-ctx.tick)/TICK_HZ
                if remaining: body["hint"] = f"Weapon {remaining:.1f}s  " + body["hint"]
            if channel := avatar.actor.behaviour.get("channel"):
                body["me"]["channel"] = dict(channel)
                body["hint"] = f"{channel['label']} {channel['remaining']:.1f}s  Stay still; Esc/B cancels."
            self.crew_view(session, body)
            if self.views[session.id].publish(session, body, ctx.tick):
                self.published[session.id] = stamp
            elif body == (self.views[session.id].previous or {}).get("body"):
                self.published[session.id] = stamp
