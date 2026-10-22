"""Shared socket-free protocol application for real and headless clients."""

from collections.abc import Callable
from typing import Any

from blacksite.server import admin_endpoint
from blacksite.server.auth import Authenticator
from blacksite.server.bus import Event, EventBus
from blacksite.server.clock import Clock, TICK_HZ
from blacksite.server.loop import TickLoop
from blacksite.server.protocol import Frame, ProtocolError, validate
from blacksite.server.sessions import INPUTS_PER_SECOND, Session, Sessions
from blacksite.server.world.registry import World
from blacksite.server.world.simulation import ZoneSimulation
from blacksite.server.characters import Characters
from blacksite.server.chat import Chat
from blacksite.server.commerce import Commerce
from blacksite.server.combat.engine import Combat
from blacksite.server.npcs.engine import Npcs
from blacksite.server.lattice.engine import Lattice
from blacksite.version import PACKAGE_VERSION, PROTOCOL_MAJOR


class Core:
    def __init__(self, clock: Clock, origin: str, auth: Authenticator,
                 keymap: dict[str, Any] | None = None, palette: dict[str, Any] | None = None,
                 motd: str = "", content: Any = None, world: World | None = None,
                 spawn_zone: str | None = None, character_state: dict[str, Any] | None = None) -> None:
        self.clock = clock
        self.auth = auth
        self.sessions = Sessions(clock, origin)
        self.bus = EventBus()
        self.loop = TickLoop(clock, self.bus, self.sessions, content)
        self.keymap = keymap or {}
        self.palette = palette or {}
        self.motd = motd
        self.stop_requested = False
        self.status_provider: Callable[[], dict[str, Any]] = self.status
        self.audit: Callable[[dict[str, Any]], None] = lambda row: None
        self.bus.subscribe("input", self._echo)
        self.world = world
        self.characters = Characters(world, self.sessions, clock, content, self.keymap, character_state) if character_state is not None else None
        self.simulation = ZoneSimulation(world, self.sessions, clock, spawn_zone, self.keymap) if world is not None and spawn_zone else None
        if self.simulation is not None:
            self.sessions.on_disconnect = self.simulation.disconnect
            self.loop.subsystems.append(self.simulation)
            self.loop.publishers.append(self.simulation.publish)
        if self.characters is not None:
            self.sessions.on_disconnect = self.characters.disconnect
            self.loop.subsystems.append(self.characters)
            self.loop.publishers.append(self.characters.publish)
        sim = self.characters.sim if self.characters else self.simulation
        self.chat = Chat(self.sessions, sim, clock, self.characters) if sim else None
        if self.chat:
            self.loop.subsystems.append(self.chat)
        self.commerce = Commerce(self.characters, character_state.get("commerce", {})) if self.characters else None
        if self.commerce:
            self.loop.subsystems.append(self.commerce)
        self.combat = Combat(self.commerce) if self.commerce else None
        if self.combat:
            self.loop.subsystems.append(self.combat)
        self.npcs = Npcs(self.combat, character_state.get("npcs", {})) if self.combat else None
        if self.npcs:
            self.loop.subsystems.append(self.npcs)
        self.lattice = Lattice(self.combat, character_state) if self.combat else None
        if self.lattice:
            if self.npcs:
                self.lattice.encounters.dispatch = lambda player: self.npcs.dispatch(self.combat.actor(player))
            self.loop.subsystems.append(self.lattice)
            self.sessions.on_disconnect = self._disconnect_character
            if self.chat:
                self.chat.lattice_at = self.lattice.location
                self.lattice.social_overlay = lambda session: session.id in self.chat.sitreps
                self.chat.reported_location = self.lattice.encounters.reported_location
                self.lattice.encounters.report = self.lattice.encounters.publish_report

    def _disconnect_character(self, session: Session) -> None:
        if self.lattice:
            if self.lattice.disconnect(session):
                return  # The bounded escape still owns this physical body.
        if self.characters:
            self.characters.disconnect(session)

    def connect(self, frame: Frame) -> Session:
        if frame.type != "hello":
            raise ProtocolError("hello must be first")
        validate(frame.type, frame.data, "client")
        role = self.auth.authenticate(frame.data["door_info"], frame.data["hmac"])
        session = self.sessions.connect(role, frame.data["door_info"], frame.data["caps"])
        session.chat_managed = self.chat is not None
        session.send(Frame("welcome", {"proto": PROTOCOL_MAJOR, "server_version": PACKAGE_VERSION,
            "player": self.characters.summary(session.user_id) if self.characters and role == "caller" else None,
            "keymap": self.keymap, "palette": self.palette, "motd": self.motd}))
        if self.simulation is not None:
            self.simulation.connect(session)
        if self.characters is not None:
            self.characters.connect(session)
        session.replay_log()
        return session

    def receive(self, session: Session, frame: Frame) -> None:
        if session.closed:
            return
        try:
            validate(frame.type, frame.data, "client")
        except (ValueError, TypeError):
            session.send(Frame("bye", {"reason": "protocol", "text": "Invalid frame."}))
            return
        if frame.type.startswith(("admin.", "peer.")):
            if session.role != "operator" or frame.type.startswith("peer."):
                session.send(Frame("bye", {"reason": "forbidden", "text": "Operator credential required."}))
            else:
                session.enqueue(frame, self.clock.now_tick())
        elif frame.type == "hello":
            session.send(Frame("bye", {"reason": "protocol", "text": "Hello already received."}))
        elif frame.type == "bye":
            session.send(Frame("bye", {"reason": "logout", "text": "You disconnect."}))
        elif frame.type == "ack":
            session.acknowledge(frame.data["rev"])
        elif frame.type == "ping":
            if session.allow("input", self.clock.now_tick(), INPUTS_PER_SECOND, 1):
                session.send(Frame("pong", {"t": frame.data["t"]}))
        elif frame.type == "resize":
            if session.allow("input", self.clock.now_tick(), INPUTS_PER_SECOND, 1):
                session.caps.update(frame.data)
                session.needs_full_view = True
        else:
            session.enqueue(frame, self.clock.now_tick())

    def _echo(self, event: Event) -> None:
        session = event.data["session"]
        frame = event.data["frame"]
        if frame.type.startswith("admin."):
            admin_endpoint.dispatch(session, frame, self.sessions, self.status_provider,
                                    self.request_stop, self.audit,
                                    self.lattice.who if self.lattice else lambda: [],
                                    self.lattice.debug_reveal if self.lattice else lambda p, s, c: {"ok": False})
            return
        if frame.type == "intent" and frame.data["name"] == "resync":
            session.replay_log()
        if self.lattice and self.lattice.input(session, frame, event.data["tick"]):
            return
        if self.combat and self.combat.input(session, frame, event.data["tick"]):
            return
        if self.commerce and self.commerce.input(session, frame, event.data["tick"]):
            return
        if self.npcs and self.npcs.input(session, frame, event.data["tick"]):
            return
        if self.chat and self.chat.input(session, frame, event.data["tick"]):
            return
        if self.lattice and self.lattice.terminal_input(session, frame, event.data["tick"]):
            return
        # Echo only the verb, never args, arbitrary chat, or private data.
        if self.simulation is not None:
            self.simulation.input(session, frame, event.data["tick"])
            return
        if self.characters is not None:
            self.characters.input(session, frame, event.data["tick"])
            return
        label = "intent" if frame.type == "intent" else frame.type
        session.send(Frame("log", {"lines": [{"channel": "system", "text": f"You send {label}.",
            "role": "muted", "at": self.clock.now_utc().isoformat()}]}))

    def status(self) -> dict[str, Any]:
        return {"uptime": self.clock.now_tick() / TICK_HZ, "players": sum(
            s.role == "caller" and not s.closed for s in self.sessions.active.values()),
            "active_zones": sum(not zone.dormant for zone in self.world.zones.values()) if self.world else 0,
            "tick": self.loop.timing(), "persistence_lag": 0,
            "event_state": None, "season_depth": 0}

    def request_stop(self) -> None:
        self.stop_requested = True

    def shutdown(self) -> None:
        if self.lattice:
            self.lattice.shutdown()
        for session in tuple(self.sessions.active.values()):
            final = Frame("bye", {"reason": "maintenance", "text": "The city closes for maintenance."})
            if session.role == "operator":
                session.finish(final)
            else:
                session.send(final)
            self.sessions.disconnect(session)
