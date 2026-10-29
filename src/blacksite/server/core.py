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
from blacksite.server.progression_engine import ProgressionEngine
from blacksite.server.fabrication import Fabrication
from blacksite.server.salvage import Salvage
from blacksite.server.housing_geometry import HousingGeometry
from blacksite.server.apartments import Apartments
from blacksite.server.faction_engine import Factions
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
        self.housing_geometry = HousingGeometry(world, clock, character_state.get("interlock", {})) if world and character_state is not None else None
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
            self.loop.subsystems.append(self.lattice.interlock)
            self.sessions.on_disconnect = self._disconnect_character
            if self.chat:
                self.chat.lattice_at = self.lattice.location
                self.lattice.social_overlay = lambda session: session.id in self.chat.sitreps
                self.chat.reported_location = self.lattice.encounters.reported_location
                self.lattice.encounters.report = self.lattice.encounters.publish_report
        self.progression = ProgressionEngine(self.commerce,self.lattice) if self.commerce else None
        if self.progression:
            self.loop.subsystems.append(self.progression)
        self.salvage = Salvage(self.commerce, character_state.get("salvage", {})) if self.progression else None
        self.fabrication = Fabrication(self.progression, self.salvage) if self.progression else None
        if self.fabrication:
            self.loop.subsystems.append(self.fabrication)
        self.apartments = Apartments(self.progression, self.housing_geometry) if self.progression else None
        if self.apartments:
            self.loop.subsystems.append(self.apartments)
        self.factions = Factions(self.progression) if self.progression else None
        if self.factions:
            self.loop.subsystems.append(self.factions)
            self.npcs.curfew = lambda zone: self.factions.curfew(zone)
            self.chat.rank_of = lambda session: self.factions.rank_of(session)
            self.chat.status_of = self.factions.status_of
            reported = self.chat.reported_location
            self.chat.reported_location = lambda viewer, target: reported(viewer, target) or self.factions.inspector_location(viewer, target)
            self.combat.faction_vat = self.factions.vat
        from blacksite.server.crew_engine import Crews
        self.crews = Crews(self.progression, self.chat) if self.progression else None
        if self.crews:
            self.loop.subsystems.append(self.crews)
            social = self.lattice.social_overlay
            self.lattice.social_overlay = lambda session, previous=social: previous(session) or session.id in self.crews.menus
        from blacksite.server.contract_engine import Contracts
        self.contracts = Contracts(self.progression, character_state.get('contracts', {})) if self.progression else None
        if self.contracts:
            self.loop.subsystems.append(self.contracts)
            social = self.lattice.social_overlay
            self.lattice.social_overlay = lambda session, previous=social: previous(session) or session.id in self.contracts.panels.menus
        from blacksite.server.relay_engine import Relays
        self.relays = Relays(self, character_state.get('relays', {})) if self.progression else None
        if self.relays:
            self.loop.subsystems.append(self.relays)
            social = self.lattice.social_overlay
            self.lattice.social_overlay = lambda session, previous=social: previous(session) or session.id in self.relays.views.menus
        from blacksite.server.market_engine import Trading
        self.market = Trading(self, character_state) if self.relays else None
        if self.market:
            self.loop.subsystems.append(self.market)
            social = self.lattice.social_overlay
            self.lattice.social_overlay = lambda session, previous=social: previous(session) or session.id in self.market.views.menus
        from blacksite.server.event_engine import Events
        self.events = Events(self, character_state.get('events', {})) if self.market else None
        if self.events:
            self.loop.subsystems.append(self.events)
            social = self.lattice.social_overlay
            self.lattice.social_overlay = lambda session, previous=social: previous(session) or session.id in self.events.views.menus

    def _disconnect_character(self, session: Session) -> None:
        if self.events:
            self.events.views.close(session)
        if self.market:
            self.market.views.close(session)
        if self.relays:
            self.relays.disconnect(session.player_id)
            self.relays.views.close(session)
        if self.contracts:
            self.contracts.disconnect(session)
        if self.crews:
            self.crews.disconnect(session)
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
        session.market_managed = self.market is not None
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
                                    self.lattice.debug_reveal if self.lattice else lambda p, s, c: {"ok": False},
                                    self.relays.admin if self.relays else None,
                                    self.market.admin if self.market else None,
                                    self.events.admin if self.events else None)
            return
        if frame.type == "intent" and frame.data["name"] == "resync":
            session.replay_log()
        if self.events and self.events.input(session, frame, event.data['tick']):
            return
        if self.market and self.market.input(session, frame, event.data['tick']):
            return
        if self.contracts and self.contracts.input(session, frame, event.data['tick']):
            return
        if self.factions and self.factions.input(session, frame, event.data["tick"]):
            return
        if self.crews and self.crews.input(session, frame, event.data["tick"]):
            return
        if self.relays and self.relays.input(session, frame, event.data["tick"]):
            return
        if self.apartments and self.apartments.input(session, frame, event.data["tick"]):
            return
        if self.progression and self.progression.input(session, frame, event.data["tick"]):
            return
        if self.lattice and self.lattice.input(session, frame, event.data["tick"]):
            return
        if self.lattice and self.lattice.interlock.input(session, frame, event.data["tick"]):
            return
        if self.combat and self.combat.input(session, frame, event.data["tick"]):
            return
        if self.fabrication and self.fabrication.input(session, frame, event.data["tick"]):
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
        session.emit(f"You send {label}.", kind="system", channel="system", role="muted",
                     at=self.clock.now_utc().isoformat())

    def status(self) -> dict[str, Any]:
        return {"uptime": self.clock.now_tick() / TICK_HZ, "players": sum(
            s.role == "caller" and not s.closed for s in self.sessions.active.values()),
            "active_zones": sum(not zone.dormant for zone in self.world.zones.values()) if self.world else 0,
            "tick": self.loop.timing(), "persistence_lag": 0,
            "event_state": [{'id': plan.id, 'event': plan.template, 'state': plan.state,
                             'starts_at': plan.starts_at, 'ends_at': plan.ends_at,
                             'where': list(plan.where)} for plan in self.events.scheduler.plans.values()
                             if plan.live] if self.events else None, "season_depth": 0,
            "market": {"open_listings": sum(v.status == 'open' for v in self.market.market.listings.values()),
                       "active_bounties": sum(v.status == 'active' for v in self.market.bounties.rows.values())} if self.market else {},
            "treasury": {faction: values.get('treasury', 0) for faction, values in self.relays.ledger.state['factions'].items()} if self.relays else {}}

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
