"""Pure character/Wake lifecycle. The I/O layer executes the write outbox."""

from karst41.server.interaction import Focus, Interaction, interact, object_interaction
from copy import deepcopy
from collections.abc import Callable
from dataclasses import asdict, replace
from datetime import datetime, timezone
from typing import Any

from karst41.content.loader import ContentTree
from karst41.server.clock import Clock, TICK_HZ
from karst41.server.loop import TickContext
from karst41.server.players import Player, pack_memory, unpack_memory
from karst41.server.items import ItemInstance, grant_starter_kit
from karst41.server.inventory import Inventory
from karst41.server.protocol import Frame
from karst41.server.rules import character as rules
from karst41.server.rules import combat as combat_rules
from karst41.server.sessions import Session, Sessions
from karst41.server.views.delta import ViewStore
from karst41.server.wake import MENU_STAGES, Wake, card_rows, cards, menu, wrapped
from karst41.server.world.registry import World
from karst41.server.world.simulation import Avatar, ZoneSimulation
from karst41.server.world.exits import Travel, complete_paid_pass
from karst41.server.world.safety import safety_at
from karst41.content.schema import Exit, Requirement

PRESENCE_CHECKPOINT_SECONDS = 5  # Architecture 6.2 player flush cadence.


class Characters:
    def __init__(self, world: World, sessions: Sessions, clock: Clock, content: ContentTree,
                 keymap: dict[str, Any], state: dict[str, Any]) -> None:
        self.world, self.sessions, self.clock, self.content = world, sessions, clock, content
        self.players = {row["id"]: Player.from_record(row) for row in state.get("players", [])}
        self.identities = deepcopy(state.get("identities", {}))
        self.serial, self.cap = state.get("serial", 0), max(1, int(state.get("cap") or 1))
        self.sim = ZoneSimulation(world, sessions, clock, "vatside-wake-hall", keymap)
        self.sim.me_provider = self.me
        self.sim.access_provider = self.access
        # S48 (#220 beat 7): an unread body cannot leave the hall; the street
        # door opens the decant record instead, on E or on a step.
        self.sim.travel_refusal = self.unread_door
        # Game 5.6: S26 supplies committed story/season route permissions.
        self.route_permissions: Callable[[Player], frozenset[str]] = lambda player: frozenset()
        self.item_templates = {row["id"]: row["template"] for row in state.get("items", [])}
        self.items = {row["id"]: ItemInstance.from_record(row) for row in state.get("items", [])}
        self.wakes: dict[str, Wake] = {}
        self.screens: dict[str, tuple[str, int]] = {}
        # Forced rename (game design 4 step 7, #221): session -> (player id, error).
        self.renaming: dict[str, tuple[str, str]] = {}
        self.card_tables: dict[str, str] = {}  # The table a card menu was opened at (its recruiter target).
        # S48 (#220): provisional bodies in the Wake Hall, before the decant
        # record is read. They live in `players` so every engine finds them,
        # but nothing about them is ever stored (write guards in queue() and
        # Commerce).
        self.unread_ids: set[str] = set()
        # A recruiter card is taken once per identity (technical lead, S48c1):
        # identity["wake_card"] holds it. Identities from before S48 had the
        # card menu in their Wake, so one with a stored character counts as
        # having had its card. Known pre-S48 data gap (technical lead, #241):
        # an identity whose characters were all deleted before S48 leaves no
        # stored trace of its creation (deletion removes the player row and
        # writes no tombstone), so it may take one card again.
        owners = {p.bbs_user_id for p in self.players.values()}
        for user, identity in self.identities.items():
            if user in owners and "wake_card" not in identity:
                identity["wake_card"] = "legacy"
        self.dirty_screens: set[str] = set()
        self.outbox: list[dict[str, Any]] = []
        self.pending: dict[str, tuple[Player, list[dict[str, Any]]]] = {}
        self.sleepers: dict[str, tuple[Any, int]] = {}
        self.saved_stamps: dict[str, tuple[Any, ...]] = {}
        self.deleting: set[str] = set()
        self.before_delete: Callable[[Session, Player, Callable[[], None]], None] = lambda session, player, proceed: proceed()
        # A disconnected Lattice escape keeps its original, targetable body.
        self.retained_avatar: Callable[[Player], Avatar | None] = lambda player: None
        self.attached: Callable[[Session, Player], None] = lambda session, player: None
        # Reconcile elapsed offline time before any caller can attach.
        for player in self.players.values():
            if player.progress.get("combat",{}).get("stage") in ("down","dead"):
                continue  # S10 resumes the durable down/decant timer, including offline.
            travel = player.progress.get("travel")
            if travel:
                self.arrive_offline(player)
                continue
            offline = player.progress.get("offline_at", player.last_seen_at)
            if offline and not self.protected(player):
                remaining = rules.SLEEPER_SECONDS - (clock.now_utc() - datetime.fromisoformat(offline)).total_seconds()
                if remaining <= 0:
                    self.recover(player)
                else:
                    actor = player.actor()
                    actor.stance = "sleeper"
                    world.enter(actor, player.zone, world.free_tile(player.zone, player.tile, actor))
                    self.sleepers[player.id] = (actor, clock.now_tick() + int(remaining * TICK_HZ))
                    world.zones[player.zone].activate("sleeper:" + player.id, clock.now_tick())

    def unread(self, pid: str | None) -> bool:
        """An unread body: a Wake that has not yet read its decant record (S48)."""
        return pid in self.unread_ids

    def owned(self, user: str) -> list[Player]:
        return sorted((p for p in self.players.values() if p.bbs_user_id == user and p.origin == self.sessions.origin
                       and p.id not in self.unread_ids), key=lambda p: p.id)

    def arrive_offline(self, player: Player) -> None:
        travel = player.progress.get("travel")
        now = self.clock.now_utc().timestamp()
        if not travel or now < travel["arrival"]:
            return
        player.zone = travel["exit"]["target_zone"]
        player.tile = tuple(travel["exit"]["target_tile"])
        player.progress.pop("travel")
        complete_paid_pass(player.progress, player.zone)
        player.progress["offline_at"] = datetime.fromtimestamp(travel["arrival"], timezone.utc).isoformat()
        if not self.protected(player):
            remaining = rules.SLEEPER_SECONDS - (now - travel["arrival"])
            if remaining <= 0:
                self.recover(player)
                return
            actor = player.actor()
            actor.stance = "sleeper"
            self.world.enter(actor, player.zone, self.world.free_tile(player.zone, player.tile, actor))
            player.tile = actor.position
            self.sleepers[player.id] = actor, self.clock.now_tick() + int(remaining * TICK_HZ)
            self.world.zones[player.zone].activate("sleeper:" + player.id, self.clock.now_tick())
        self.queue("save", player.bbs_user_id, player, immediate=True)

    def summary(self, user: str) -> dict[str, Any] | None:
        owned = self.owned(user)
        return owned[0].summary() if len(owned) == 1 else None

    def protected(self, player: Player) -> bool:
        if player.progress.get("travel"):
            return True  # An in-flight character has no targetable body.
        return player.zone in self.world.zones and safety_at(self.world.zones[player.zone], player.tile) in ("safe", "pocket")

    def access(self, session: Session) -> dict[str, Any]:
        player = self.players[session.player_id]
        return {"standing": player.standing, "faction": player.faction,
                "story": self.route_permissions(player),
                "zone": player.zone,
                "open_objects": frozenset(key for key, obj in self.world.zones[player.zone].objects.items() if obj.open),
                "items": [self.item_templates.get(iid, iid) for iid in player.inventory]}

    def card_taken(self, user: str) -> bool:
        return bool(self.identity(user).get("wake_card"))

    def identity(self, user: str) -> dict[str, Any]:
        if user not in self.identities:
            self.identities[user] = {"first_decanted_at": self.clock.now_utc().isoformat(), "legal_at": None,
                                     "receipts": {}, "clone_debt": 0, "wake": {}}
            self.queue("identity", user)
        return self.identities[user]

    def queue(self, action: str, user: str, player: Player | None = None, **extra: Any) -> None:
        if action == "save" and player and (player.id in self.deleting or player.id not in self.players):
            return
        if action in ("save", "delete") and player and player.id in self.unread_ids:
            return  # S48 write guard 1: an unread body is never stored.
        effect = {"action": action, "user": user, "identity": deepcopy(self.identities[user]),
                  "player": player.record() if player else None, **extra}
        self.outbox.append(effect)

    def connect(self, session: Session) -> None:
        if session.role != "caller":
            return
        # Sessions carries reconnect metadata, but the chooser has no attached
        # character. Only attach() may assign body ownership in S07.
        session.player_id = session.subscribed = session.player_name = None
        identity = self.identity(session.user_id)
        owned = self.owned(session.user_id)
        if len(owned) == 1 and self.cap == 1:
            self.enter(session, owned[0])
        elif owned:
            self.screens[session.id] = ("characters", 0)
            self.dirty_screens.add(session.id)
        else:
            pending = next((token for token, (p, _) in self.pending.items() if p.bbs_user_id == session.user_id), None)
            if pending is not None:
                # A redial while the record settles waits for the commit (S48c1).
                wake = Wake.restore(identity.get("wake", {}))
                wake.stage = "saving"
                self.wakes[session.id] = wake
                self.pending[session.id] = self.pending.pop(pending)
            else:
                self.enter_hall(session, Wake.restore(identity.get("wake", {})))

    def menu_open(self, session: Session) -> bool:
        """A Wake menu (record, name, saving) or the card table is over the hall."""
        wake = self.wakes.get(session.id)
        return bool(wake and wake.stage in MENU_STAGES) or self.screens.get(session.id, ("",))[0] == "cards"

    def enter_hall(self, session: Session, wake: Wake) -> None:
        """S48 (#220): wake in the hall with an unread body, before any record.

        The body is held in memory only. Its gurney serial is taken here and
        kept in the stored wake record, so a redial resumes the same number.
        """
        identity = self.identity(session.user_id)
        if not wake.serial:
            self.serial += 1
            while f"{self.sessions.origin}:player:{self.serial}" in self.players:
                self.serial += 1
            wake.serial = self.serial
            identity["wake"] = wake.saved()
            self.queue("identity", session.user_id, serial=self.serial)
        pid = f"{self.sessions.origin}:player:{wake.serial}"
        player = Player(pid, self.sessions.origin, session.user_id, session.door_info["handle"],
                        rules.gurney_name(wake.serial), rules.UNREAD, self.clock.now_utc().isoformat())
        spawn = self.world.zones[player.zone].template.meta.spawn
        player.tile = tuple(wake.tile) if wake.tile else spawn
        player.chits_hand = 0
        player.health = rules.health_max(player.attributes["vitals"])
        player.stamina = rules.stamina_max(player.attributes["nerve"], player.attributes["frame"])
        player.progress = {"memory": {}, "met_talkers": list(wake.met)}
        if wake.lessons.get("drone") in ("done", "skipped"):
            player.progress["wake_combat"] = wake.lessons["drone"]
        self.players[pid] = player
        self.unread_ids.add(pid)
        self.wakes[session.id] = wake
        self._place(session, player)

    def unread_door(self, session: Session, exit: Any) -> str | None:
        if not self.unread(session.player_id):
            return None
        self.open_record(session, "door")
        return "Read your decant record first."

    def open_record(self, session: Session, source: str) -> bool:
        """The decant record opens on a key the caller pressed (#220 beat 9)."""
        wake = self.wakes.get(session.id)
        if wake is None or wake.stage != "hall" or not self.unread(session.player_id):
            return False
        names = [slug for slug, _ in rules.ARCHETYPES]
        wake.stage, wake.source, wake.error, wake.dirty = "record", source, "", True
        wake.cursor = names.index(wake.archetype) if wake.archetype in names else 0
        return True

    def take_card(self, session: Session, card: str) -> None:
        """A recruiter card counts when it is taken at the table (#220 ruling 4).

        Once per identity, in the Wake Hall. Before the record it is held in
        the wake record and applied at creation; afterwards it is applied
        with the same standing, by an ordinary save (technical lead, S48c1).
        """
        if card == "none" or self.card_taken(session.user_id):
            return
        wake = self.wakes.get(session.id)
        if wake is not None and self.unread(session.player_id):
            wake.card = card
            self.identities[session.user_id]["wake"] = wake.saved()
            self.queue("identity", session.user_id)
            return
        player = self.players.get(session.player_id)
        if player is None:
            return
        selected = self.content.wake_cards[card]
        key = selected.faction or card
        standing = {**player.standing, key: max(player.standing.get(key, 0), rules.CARD_STANDING)}
        identity = {**deepcopy(self.identity(session.user_id)), "wake_card": card}
        commerce = self.combat.commerce
        if not commerce.settle(player, {"standing": standing}, commerce.items, commerce.caches,
                               commerce.serial, lambda ok: None, identity):
            raise ValueError("Let the current transfer settle before taking a card.")

    def enter(self, session: Session, player: Player) -> None:
        """Attach, unless the name falls under the reserved gurney form (#221).

        Such a character first chooses a new name. Every stored reference is
        keyed by id, so only the name itself changes.
        """
        if rules.reserved_name(player.name):
            self.renaming[session.id] = (player.id, "")
            self.screens[session.id] = ("rename", 0)
            self.dirty_screens.add(session.id)
        else:
            self.attach(session, player)

    def rename(self, session: Session, text: str) -> None:
        pid, _ = self.renaming[session.id]
        player = self.players.get(pid)
        if player is None or player.id in self.deleting:
            self.renaming.pop(session.id, None)
            self.screens[session.id] = ("characters", 0)
            return
        candidate = rules.normalize_name(text)
        if rules.reserved_name(candidate):
            error = rules.GURNEY_TYPED
        elif not rules.valid_name(candidate):
            error = "Use 2-24 columns of letters, digits, spaces, - _ '."
        elif not self.name_available(candidate):
            error = "That name is already in use. Choose another."
        else:
            self.renaming.pop(session.id)
            player.name = candidate
            self.attach(session, player)  # Saves at once, so no other rename races the unique index.
            return
        self.renaming[session.id] = (pid, error)

    def attach(self, session: Session, player: Player) -> None:
        self._place(session, player)
        self.wakes.pop(session.id, None)
        self.screens.pop(session.id, None)
        player.progress.pop("offline_at", None)
        player.update_personhood(self.identity(session.user_id), self.clock.now_utc())
        self.queue("save", session.user_id, player, immediate=True)
        self.attached(session, player)

    def promote(self, session: Session, player: Player) -> None:
        """The record is read: the unread body becomes the character in place."""
        avatar = self.sim.avatars.get(session.user_id)
        self.unread_ids.discard(player.id)
        self.players[player.id] = player
        if avatar is not None:
            actor = avatar.actor
            actor.name, actor.handle = player.name, session.door_info["handle"]
            actor.health_max = rules.health_max(player.attributes["vitals"])
            actor.stamina_max = rules.stamina_max(player.attributes["nerve"], player.attributes["frame"])
            actor.health, actor.stamina = actor.health_max, actor.stamina_max  # Game design 17 (#238).
            player.zone, player.tile = avatar.zone, actor.position
            self.world.zones[avatar.zone].revision += 1
        session.player_name = player.name
        self.wakes.pop(session.id, None)
        self.screens.pop(session.id, None)
        self.identities[player.bbs_user_id]["wake"] = {}
        player.update_personhood(self.identity(session.user_id), self.clock.now_utc())
        self.queue("save", session.user_id, player, immediate=True)
        self.attached(session, player)

    def _place(self, session: Session, player: Player) -> None:
        retained = self.retained_avatar(player)
        sleeper = self.sleepers.pop(player.id, None)
        actor = retained.actor if retained else sleeper[0] if sleeper else player.actor()
        actor.name = player.name  # A sleeper or retained body may predate a rename.
        actor.overweight = Inventory(self.items,self.content.items).weight(player) > player.attributes["frame"] / 2
        if sleeper:
            self.world.zones[player.zone].deactivate("sleeper:" + player.id, self.clock.now_tick())
            self.world.leave(actor)
        actor.handle = session.door_info["handle"]
        if retained is None:
            actor.stance = "normal"
            if hasattr(self,"combat"): self.combat.restore(player,actor)
        player.bbs_handle = actor.handle
        avatar = retained or Avatar(actor, player.zone)
        if retained is None:
            for zone_id, blob in player.progress.get("memory", {}).items():
                if zone_id in self.world.zones:
                    zone = self.world.zones[zone_id].template
                    avatar.perception.remembered[zone_id] = unpack_memory(blob, zone.width, zone.height)
            avatar.seen_zones = set(player.progress.get("seen_zones", []))
            self.world.enter(actor, player.zone, self.world.free_tile(player.zone, player.tile, actor))
        session.player_id, session.subscribed, session.player_name = player.id, player.zone, player.name
        session.keymap_id = player.settings.get("keymap", "arrows")
        self.world.zones[player.zone].activate(session.id, self.clock.now_tick())
        self.sim.avatars[session.user_id] = avatar
        self.sim.views[session.id] = ViewStore()
        self.sim.published.pop(session.id, None)
        travel = player.progress.get("travel")
        if travel:
            data = dict(travel["exit"])
            data["tile"], data["target_tile"] = tuple(data["tile"]), tuple(data["target_tile"])
            if data.get("requirement"):
                data["requirement"] = Requirement(**data["requirement"])
            data['alternatives'] = tuple(Requirement(**row) for row in data.get('alternatives', ()))
            avatar.travel = Travel(Exit(**data), travel["departure"], travel["arrival"], True)
            self.world.zones[player.zone].deactivate(session.id, self.clock.now_tick())
            self.world.leave(actor)
            self.sim.transition(session, avatar, self.clock.now_utc().timestamp(), self.clock.now_tick())
        else:
            self.sim.discover(session, avatar)

    def snapshot(self, player: Player, avatar: Avatar) -> None:
        actor = avatar.actor
        player.zone, player.tile, player.facing = avatar.zone, actor.position, actor.facing
        player.health, player.stamina, player.shock = actor.health, actor.stamina, actor.shock
        player.last_seen_at = self.clock.now_utc().isoformat()
        memory = player.progress.setdefault("memory", {})
        previous_grid = self.saved_stamps.get(player.id, (None,) * 6)[5]
        for zone_id, cells in avatar.perception.remembered.items():
            if zone_id not in memory or (zone_id == avatar.zone and previous_grid != avatar.perception.grid_key):
                zone = self.world.zones[zone_id].template
                memory[zone_id] = pack_memory(cells, zone.width, zone.height)
        player.progress["seen_zones"] = sorted(avatar.seen_zones)
        if avatar.travel and avatar.travel.departed:
            player.progress["travel"] = {"exit": asdict(avatar.travel.exit), "departure": avatar.travel.departure,
                                         "arrival": avatar.travel.arrival}
        else:
            player.progress.pop("travel", None)

    def disconnect(self, session: Session, avatar_override: Avatar | None = None) -> None:
        wake = self.wakes.pop(session.id, None)
        self.screens.pop(session.id, None)
        self.renaming.pop(session.id, None)
        self.dirty_screens.discard(session.id)
        if session.role != "caller":
            return
        player = self.players.get(session.player_id)
        avatar = avatar_override or self.sim.avatars.get(session.user_id)
        if wake:
            if player is not None and self.unread(player.id) and avatar is not None:
                wake.tile = list(avatar.actor.position)
            self.identities[session.user_id]["wake"] = wake.saved()
            self.queue("identity", session.user_id)
        if player is not None and self.unread(player.id):
            # S48: nothing about an unread body is stored; the redial rebuilds it.
            for store in (self.sim.views, self.sim.published, self.sim.maps, self.sim.map_opened, self.sim.overlays):
                store.pop(session.id, None)
            if avatar is not None and avatar.actor.zone:
                self.world.zones[avatar.actor.zone].deactivate(session.id, self.clock.now_tick())
                self.world.leave(avatar.actor)
            self.sim.avatars.pop(session.user_id, None)
            self.players.pop(player.id, None)
            self.unread_ids.discard(player.id)
            self.saved_stamps.pop(player.id, None)
            return
        if player is None or avatar is None or avatar.actor.id != player.id:
            return
        self.snapshot(player, avatar)
        self.sim.views.pop(session.id, None)
        self.sim.published.pop(session.id, None)
        self.sim.maps.pop(session.id, None)
        self.sim.map_opened.pop(session.id, None)
        self.sim.overlays.pop(session.id, None)
        self.world.zones[player.zone].deactivate(session.id, self.clock.now_tick())
        player.progress["offline_at"] = self.clock.now_utc().isoformat()
        if self.clock.now_utc().timestamp()-player.progress.get("last_exchange",0)<combat_rules.COMBAT_SECONDS:
            player.progress["sleeper_combat"] = True
        if player.progress.get("combat",{}).get("stage") in ("down","dead"):
            self.queue("save", session.user_id, player, immediate=True)
            return
        if avatar.travel and avatar.travel.departed:
            self.queue("save", session.user_id, player, immediate=True)
            return
        avatar.travel = None  # Leaving the platform cancels boarding, not a ride.
        if player.id in self.deleting:
            return
        if self.protected(player):
            self.world.leave(avatar.actor)
        else:
            avatar.actor.stance = "sleeper"
            self.sleepers[player.id] = (avatar.actor, self.clock.now_tick() + rules.SLEEPER_SECONDS * TICK_HZ)
            self.world.zones[player.zone].activate("sleeper:" + player.id, self.clock.now_tick())
        self.queue("save", session.user_id, player, immediate=True)

    def recover(self, player: Player) -> None:
        # Zone graph distance, then authored exit order. Ignore destinations
        # that remain in an incomplete authoring bundle (travel itself is S08).
        pending, seen = [(player.zone, player.tile)], set()
        destination = None
        while pending:
            zone_id, tile = pending.pop(0)
            if zone_id in seen or zone_id not in self.world.zones:
                continue
            seen.add(zone_id)
            zone = self.world.zones[zone_id]
            if zone.template.meta.safety in ("safe", "pocket"):
                destination = zone_id, tile
                break
            pending.extend((ex.target_zone, ex.target_tile) for ex in zone.template.meta.exits if not ex.hidden)
        player.zone, player.tile = destination or ("vatside-wake-hall", self.world.zones["vatside-wake-hall"].template.meta.spawn)
        player.progress.pop("offline_at", None)
        if player.progress.pop("sleeper_combat",False):
            player.chits_hand,player.clone_debt,player.xp,_ = combat_rules.clone_settlement(player.chits_hand,player.grade,player.xp,
                rules.grade_threshold(player.grade),player.clone_debt)
            self.identities[player.bbs_user_id]["clone_debt"] = player.clone_debt
            player.zone = "vatside-wake-hall"
            player.tile = self.world.zones[player.zone].template.meta.spawn
            player.health,player.shock = rules.health_max(player.attributes["vitals"]),0
        self.queue("save", player.bbs_user_id, player, immediate=True)

    def create(self, session: Session, card: str | None = None) -> None:
        wake = self.wakes[session.id]
        if session.id in self.pending:
            return
        if len(self.owned(session.user_id)) >= self.cap:
            wake.stage, wake.error = "name", "This BBS identity already has its characters."
            return
        card = wake.card if card is None else card
        if self.card_taken(session.user_id):
            card = None  # Once per identity, deletion included (game design 4).
        if not self.name_available(wake.name):
            wake.stage, wake.error = "name", "That name is already in use. Choose another."
            return
        if rules.reserved_name(wake.name):  # A Wake saved before the rule.
            wake.stage, wake.error = "name", rules.GURNEY_TYPED
            return
        if not wake.serial:  # A direct creation path (tests) may skip the hall.
            self.serial += 1
            wake.serial = self.serial
        serial = wake.serial
        player = Player(f"{self.sessions.origin}:player:{serial}", self.sessions.origin, session.user_id,
                        session.door_info["handle"], wake.name, wake.archetype, self.clock.now_utc().isoformat())
        body = self.players.get(player.id)
        avatar = self.sim.avatars.get(session.user_id)
        if body is not None and self.unread(body.id) and avatar is not None:
            player.zone, player.tile = avatar.zone, avatar.actor.position
            player.settings = deepcopy(body.settings)
        else:
            player.tile = self.world.zones[player.zone].template.meta.spawn
        player.health = rules.health_max(player.attributes["vitals"])
        player.stamina = rules.stamina_max(player.attributes["nerve"], player.attributes["frame"])
        if card and card != "none":
            selected = self.content.wake_cards[card]
            player.standing[selected.faction or card] = rules.CARD_STANDING
        start = self.content.starts[player.archetype]
        items = grant_starter_kit(player, start, self.content.items, serial)
        player.progress = {"points": 0, "known_programs": list(start.programs), "known_hymns": list(start.hymns), "memory": {}}
        # Held facts from the hall (S48c1), applied at creation.
        if wake.met:
            player.progress["met_talkers"] = sorted(set(wake.met))
        if wake.lessons.get("drone") in ("done", "skipped"):
            player.progress["wake_combat"] = wake.lessons["drone"]
        player.rig = {"native": bool(start.rig_slots), "slots": (list(start.programs) + [None] * start.rig_slots)[:start.rig_slots]}
        identity = self.identity(session.user_id)
        # Saved with the create effect's identity; "" records "none taken yet"
        # so a restart cannot mistake this identity for a pre-S48 one.
        identity["wake_card"] = card if card and card != "none" else identity.get("wake_card", "")
        player.clone_debt = identity.get("clone_debt", 0)
        player.update_personhood(identity, self.clock.now_utc())
        self.pending[session.id] = player, items
        self.item_templates.update({item["id"]: item["template"] for item in items})
        wake.stage = "saving"
        self.queue("create", session.user_id, player, items=items, serial=max(self.serial, serial), token=session.id)

    def name_available(self, name: str) -> bool:
        key = rules.name_key(name)
        return all(rules.name_key(p.name) != key for p in [*self.players.values(), *(v[0] for v in self.pending.values())]
                   if p.id not in self.unread_ids)

    def committed(self, effect: dict[str, Any], error: bool = False) -> None:
        token, action = effect.get("token"), effect["action"]
        session = self.sessions.active.get(token)
        if action == "create":
            owner = next((sid for sid, (p, _) in self.pending.items() if p.id == effect["player"]["id"]), token)
            player, _ = self.pending.pop(owner)
            session = self.sessions.active.get(owner)
            if error:
                wake = self.wakes.get(owner)
                identity = self.identities.get(player.bbs_user_id, {})
                if wake and wake.card and identity.get("wake_card") == wake.card:
                    identity["wake_card"] = ""  # The card was not settled either; it stays held.
                if wake:  # Back at the name, with the reason; never bodiless, never two bodies.
                    wake.stage, wake.error, wake.dirty = "name", "The record did not settle. Enter tries again.", True
                if session is not None and not session.closed and session.player_id is None:
                    self.wakes.pop(owner, None)
                    self.enter_hall(session, wake or Wake())
                    self.wakes[owner].stage, self.wakes[owner].error = "name", "The record did not settle. Enter tries again."
                return
            self.items.update({row["id"]: ItemInstance.from_record(row) for row in effect["items"]})
            self.identities[player.bbs_user_id]["wake"] = {}
            if session is not None and not session.closed:
                if self.unread(session.player_id) and session.player_id == player.id:
                    self.promote(session, player)
                else:
                    self.players[player.id] = player
                    self.attach(session, player)
            else:
                self.players[player.id] = player
                self.unread_ids.discard(player.id)
        elif action == "delete":
            self.deleting.discard(effect["player"]["id"])
            if not error:
                self.players.pop(effect["player"]["id"], None)
                for iid in [key for key, item in self.items.items() if item.owner == effect["player"]["id"]]:
                    self.items.pop(iid)
                    self.item_templates.pop(iid, None)
                self.identities[effect["user"]] = effect["identity"]
                sleeper = self.sleepers.pop(effect["player"]["id"], None)
                actor = self.world.actors.get(effect["player"]["id"])
                if actor is not None:
                    self.world.zones[actor.zone].deactivate("sleeper:" + actor.id, self.clock.now_tick())
                    self.world.leave(actor)
            if session is not None and not session.closed:
                if error:
                    self.screens[token] = ("sheet", 0)
                    session.send(Frame("toast", {"text": "The record did not settle. Your character remains.", "role": "ui_text", "seconds": 8}))
                else:
                    self.sim.disconnect(session)
                    self.sim.avatars.pop(session.user_id, None)
                    session.player_id = session.subscribed = session.player_name = None
                    self.screens.pop(token, None)
                    self.enter_hall(session, Wake())
                self.dirty_screens.add(token)

    def interaction(self, session: Session, frame: Frame) -> Interaction:
        if (self.menu_open(session) or session.id in self.screens
                or session.player_id not in self.players):
            return Interaction()
        return self.sim.interaction(session, frame)

    def wake_interaction(self, session: Session, frame: Frame) -> Interaction | None:
        """E in the hall before the record: the door, the outfitter or the cards (#220)."""
        if self.menu_open(session) or not interact(frame):
            return None
        avatar = self.sim.avatars.get(session.user_id)
        # The card table, the record door and the outfitter are the Wake Hall's.
        if (avatar is None or avatar.travel or avatar.actor.zone != Player.zone
                or avatar.actor.stance == "jacked" or session.id in self.sim.external_views
                or session.pending_prompts):
            return None  # Jacked in, the Lattice owns E; the hall is physical.
        unread = self.unread(session.player_id)
        zone = self.world.zones[avatar.actor.zone]
        here = avatar.actor.position
        near = lambda tile: max(abs(tile[0]-here[0]), abs(tile[1]-here[1])) <= 1
        for obj in zone.objects.values():
            if not near(obj.spec.tile):
                continue
            if (obj.spec.params.get("recruiters") and not self.card_taken(session.user_id)
                    and (not unread or self.wakes[session.id].card is None)):
                # The same hint the recruiter menu gave at this table (#104 labels).
                return replace(object_interaction(obj), value=("cards", obj.spec.id), kind="wake")
            if unread and obj.spec.params.get("vendor") == "wake-outfitter":
                return Interaction(Focus(obj.spec.id, str(obj.spec.params.get("name", "Wake Outfitter")), "ask"),
                                   ("record", "outfitter"), obj.spec.tile, kind="wake")
        if unread:
            for exit in zone.template.meta.exits:
                if near(exit.tile) and not exit.hidden:
                    return Interaction(Focus(exit.id, self.world.zones[exit.target_zone].template.meta.name, "go to"),
                                       ("record", "door"), exit.tile, kind="wake")
        return None

    def wake_input(self, session: Session, frame: Frame, tick: int, *, interaction: Interaction | None = None) -> bool:
        """The record, the name prompt and the card table, over the hall (S48c1)."""
        if interaction is not None and interaction.kind == "wake" and interaction.value:
            kind, target = interaction.value
            if kind == "cards":
                self.screens[session.id] = ("cards", 0)
                self.card_tables[session.id] = target
                self.dirty_screens.add(session.id)
            else:
                self.open_record(session, target)
            return True
        if not self.menu_open(session):
            return False
        name = frame.data.get("name", "") if frame.type == "intent" else ""
        key = frame.data.get("k", "") if frame.type == "key" else ""
        screen = self.screens.get(session.id, ("", 0))
        if screen[0] == "cards":
            ids = card_rows(self.content, not self.unread(session.player_id))
            count = len(ids)
            cursor = screen[1]
            if name == "menu_cursor":
                delta = frame.data.get("args", {}).get("delta", frame.data.get("args", {}).get("dir", 0))
                cursor = max(0, min(count - 1, cursor + (-1 if delta in (-1, "up") else 1)))
                self.screens[session.id] = ("cards", cursor)
            elif name == "menu_close" or key in ("escape", "b", "B"):
                self.screens.pop(session.id, None)
                self._reset_view(session)
            elif name == "menu_select":
                card = ids[min(cursor, count - 1)]
                self.screens.pop(session.id, None)
                self._reset_view(session)
                if card == "ask":
                    # The table's ordinary recruiter menu, by its own checks.
                    target = self.card_tables.get(session.id, "")
                    self.factions.input(session, Frame("intent", {"name": "faction.open", "args": {"target": target}}), tick)
                else:
                    try:
                        self.take_card(session, card)
                    except ValueError as exc:
                        session.send(Frame("toast", {"text": str(exc), "role": "ui_text", "seconds": 4}))
            self.dirty_screens.add(session.id)
            return True
        wake = self.wakes[session.id]
        if wake.stage == "saving":
            return True
        if wake.stage == "record":
            count = len(rules.ARCHETYPES)
            if name == "menu_cursor":
                delta = frame.data.get("args", {}).get("delta", frame.data.get("args", {}).get("dir", 0))
                wake.cursor = max(0, min(count - 1, wake.cursor + (-1 if delta in (-1, "up") else 1)))
            elif name == "menu_close" or key in ("escape", "b", "B"):
                wake.stage = "hall"  # The record closes; the hall goes on.
                self._reset_view(session)
            elif name == "menu_select":
                if frame.data.get("expected_revision", session.view_revision) != session.view_revision:
                    wake.dirty = True
                    return True
                wake.archetype, wake.stage, wake.error = rules.ARCHETYPES[wake.cursor][0], "name", ""
        elif wake.stage == "name":
            if name == "prompt_cancel":
                wake.stage = "record"
            elif frame.type == "line" and frame.data["id"] == wake.prompt_id:
                candidate = rules.normalize_name(frame.data["text"]) or rules.default_name(session.door_info["handle"])
                if rules.reserved_name(candidate):
                    wake.error = rules.GURNEY_TYPED
                elif not rules.valid_name(candidate):
                    wake.error = "Use 2-24 columns of letters, digits, spaces, - _ '."
                elif not self.name_available(candidate):
                    wake.error = "That name is already in use. Choose another."
                else:
                    wake.name, wake.error = candidate, ""
                    self.create(session)
        wake.dirty = True
        self.identities[session.user_id]["wake"] = wake.saved()
        self.queue("identity", session.user_id)
        return True

    def _reset_view(self, session: Session) -> None:
        avatar = self.sim.avatars.get(session.user_id)
        if avatar is not None:
            self.sim.reset_view(session, avatar)

    def input(self, session: Session, frame: Frame, tick: int, *, interaction: Interaction | None = None) -> None:
        name = frame.data.get("name", "") if frame.type == "intent" else ""
        key = frame.data.get("k", "") if frame.type == "key" else ""
        if name == "resync":
            session.needs_full_view = True
        if self.wake_input(session, frame, tick):
            return
        screen, cursor = self.screens.get(session.id, ("", 0))
        player = self.players.get(session.player_id)
        if screen == "characters":
            owned = self.owned(session.user_id)
            if name == "menu_cursor":
                cursor = max(0, min(len(owned) - 1 + int(len(owned) < self.cap), cursor + frame.data.get("args", {}).get("delta", 0)))
                self.screens[session.id] = (screen, cursor)
            elif name == "menu_select":
                if cursor < len(owned):
                    self.enter(session, owned[cursor])
                else:
                    self.screens.pop(session.id, None)
                    self.enter_hall(session, Wake.restore(self.identity(session.user_id).get("wake", {})))
            elif name == "menu_close":
                session.send(Frame("bye", {"reason": "logout", "text": "You leave your place."}))
            self.dirty_screens.add(session.id)
            return
        if screen == "rename" and session.id in self.renaming:
            pid = self.renaming[session.id][0]
            if name == "prompt_cancel":
                self.renaming.pop(session.id)
                if len(self.owned(session.user_id)) > 1 or self.cap > 1:
                    self.screens[session.id] = ("characters", 0)
                else:
                    session.send(Frame("bye", {"reason": "logout", "text": "You leave your place."}))
            elif frame.type == "line" and frame.data["id"] == "rename:" + pid:
                self.rename(session, frame.data["text"])
            self.dirty_screens.add(session.id)
            return
        if player is None:
            return
        if session.id in self.sim.maps or (self.sim.avatars.get(session.user_id) and self.sim.avatars[session.user_id].travel):
            self.sim.input(session, frame, tick, interaction=interaction)
            return
        if screen == "delete" and player.id in self.unread_ids:
            self.screens[session.id] = ("sheet", 0)  # S48: an unread body has nothing to delete.
            self.dirty_screens.add(session.id)
        elif screen == "delete":
            if name == "prompt_cancel":
                self.screens[session.id] = ("sheet", 0)
            elif frame.type == "line" and frame.data["id"] == "delete:" + player.id:
                if frame.data["text"] == player.name:
                    self.screens[session.id] = ("saving", 0)
                    def proceed() -> None:
                        identity = deepcopy(self.identities[session.user_id])
                        identity["clone_debt"], identity["wake"] = player.clone_debt, {}
                        self.deleting.add(player.id)
                        self.queue("delete", session.user_id, player, identity=identity, token=session.id)
                    try:
                        self.before_delete(session, player, proceed)
                    except ValueError as exc:
                        self.screens[session.id] = ('sheet', 0)
                        session.send(Frame('toast', {'text': str(exc), 'role': 'ui_text', 'seconds': 4}))
                else:
                    self.screens[session.id] = ("sheet", 0)
            self.dirty_screens.add(session.id)
        elif (name == "delete_character" or (screen == "sheet" and name == "menu_select" and frame.data.get("args", {}).get("key") == "d")) \
                and player.id not in self.unread_ids:
            self.screens[session.id] = ("delete", 0)
            self.dirty_screens.add(session.id)
        elif screen == "sheet":
            if name == "menu_close":
                self.screens.pop(session.id)
                self.sim.views[session.id] = ViewStore()
                self.sim.published.pop(session.id, None)
            elif name == "menu_cursor":
                last = len(self.sheet(player, cursor)["rows"]) - 1
                self.screens[session.id] = ("sheet", max(0, min(last, cursor + frame.data.get("args", {}).get("delta", 0))))
                self.dirty_screens.add(session.id)
            elif (name == "menu_select" and frame.data.get("args", {}).get("key") == "s"
                  and frame.data.get("expected_revision") == session.view_revision
                  and hasattr(self, "progression")):
                self.progression.open_skills(session)
        elif key in ("p", "P"):
            self.screens[session.id] = ("sheet", 0)
            self.dirty_screens.add(session.id)
        else:
            self.sim.input(session, frame, tick, interaction=interaction)

    def me(self, session: Session) -> dict[str, Any]:
        player = self.players[session.player_id]
        identity = self.identities[session.user_id]
        days = max(0, (self.clock.now_utc() - datetime.fromisoformat(identity["first_decanted_at"])).days)
        equipped = self.combat.weapon(player) if hasattr(self,"combat") else None
        return {"name_role": "player_hostile" if player.marked_until and datetime.fromisoformat(player.marked_until) > self.clock.now_utc() else self.content.factions[player.faction].colour if player.faction in self.content.factions else "title",
                "faction": player.faction, "rank": self.factions.rank_of(session) if hasattr(self, "factions") else "",
                "name": player.name, "handle": player.bbs_handle,
                "grade": None if self.unread(player.id) else player.grade,
                "chits": player.chits_hand, "weapon": self.content.items[equipped[0].template].name if equipped else "None",
                "in_combat": self.clock.now_utc().timestamp()-player.progress.get("last_exchange",0)<combat_rules.COMBAT_SECONDS,
                "hit_serial": self.sim.avatars[session.user_id].actor.behaviour.get("hit_serial",0),
                "marked_until": player.marked_until,
                "heat_until": player.warden_heat_until if player.warden_heat_until and datetime.fromisoformat(player.warden_heat_until) > self.clock.now_utc() else None,
                "lease_days": days, "legal_at": player.legal_at,
                "discharge_xp": rules.grade_threshold(rules.DISCHARGE_GRADE), "xp": player.xp,
                **({"effects": [*deepcopy(self.sim.avatars[session.user_id].actor.effects),
                                 *self.progression.substances.effects(player)]} if hasattr(self, "progression") else {})}

    def sheet(self, player: Player, cursor: int) -> dict[str, Any]:
        if hasattr(self, "progression"):
            return self.progression.sheet(player, cursor)
        me = self.me(next(s for s in self.sessions.active.values() if s.player_id == player.id))
        values = [("Archetype", player.archetype.title()), ("Grade", f"{player.grade} {rules.grade_name(player.grade)}"),
                  ("XP", f"{player.xp} / {rules.grade_threshold(min(30, player.grade + 1))}"),
                  ("Points", player.progress.get("points", 0)), ("Hand chits", player.chits_hand), ("Bank chits", player.chits_bank), ("Health", f"{player.health}/{rules.health_max(player.attributes['vitals'])}"),
                  ("Stamina", f"{player.stamina}/{rules.stamina_max(player.attributes['nerve'], player.attributes['frame'])}"),
                  ("Tolerance", rules.tolerance(player.attributes["vitals"], player.archetype)),
                  ("Evasion", rules.evasion(player.attributes["nerve"])), ("Carry kg", rules.carry_kg(player.attributes["frame"])),
                  ("Lease days", f"{me['lease_days']} / 90"), ("Signatory XP", f"{player.xp} / {me['discharge_xp']}"),
                  ("Personhood", player.legal_at or "Under lease"), *[(k.title(), v) for k, v in player.attributes.items()],
                  *[(k.title(), f"{v:g}") for k, v in player.skills.items()]]
        rows = [{"id": str(i), "cells": [k, str(v)]} for i, (k, v) in enumerate(values)]
        return {**menu("CHARACTER - " + player.name, rows, min(cursor, len(rows) - 1),
                       f"BBS: {player.bbs_handle}\nChits: {player.chits_hand}\nPockets protect your body.\nGrade protection is separate from personhood.", "Esc/B returns  D deletes character"),
                "actions": [{"key": "d", "label": "delete character"}]}

    def tick(self, ctx: TickContext) -> None:
        for session in tuple(self.sessions.active.values()):
            if session.closed:
                self.sessions.disconnect(session)
        for pid, (actor, due) in tuple(self.sleepers.items()):
            if ctx.tick >= due:
                player = self.players[pid]
                if player.progress.get("combat",{}).get("stage") in ("down","dead"):
                    continue  # Combat owns the down/decant lifecycle.
                self.world.zones[actor.zone].deactivate("sleeper:" + pid, ctx.tick)
                self.world.leave(actor)
                del self.sleepers[pid]
                self.recover(player)
        self.sim.tick(ctx)
        online = {s.player_id for s in self.sessions.active.values() if not s.closed}
        for player in self.players.values():
            if player.id not in online and player.progress.get("travel"):
                self.arrive_offline(player)
        for player in self.players.values():
            previous = player.legal_at
            player.update_personhood(self.identities[player.bbs_user_id], self.clock.now_utc())
            if previous != player.legal_at:
                self.queue("save", player.bbs_user_id, player, immediate=True)
        for avatar in self.sim.avatars.values():
            actor = avatar.actor
            if actor.zone and actor.shock > 0 and ctx.tick - actor.cooldowns.get("last_hit", -3 * TICK_HZ) >= 3 * TICK_HZ:
                actor.shock = max(actor.modifiers.get("shock_floor", 0), actor.shock
                    - rules.SHOCK_DECAY_PER_SECOND / TICK_HZ*actor.modifiers.get("shock_decay_multiplier", 1))
                self.world.zones[actor.zone].revision += 1

    def publish(self, ctx: TickContext) -> None:
        playing = tuple(s for s in ctx.sessions if not self.menu_open(s) and s.id not in self.screens)
        self.sim.publish(replace(ctx, sessions=playing))
        for session in ctx.sessions:
            if session.closed or session.role != "caller":
                continue
            wake = self.wakes.get(session.id)
            if wake is not None and wake.stage in MENU_STAGES:
                if not wake.dirty and not session.needs_full_view:
                    continue
                body = wake.body(self.content, session.door_info["handle"], session.caps["width"], session.caps["height"])
                avatar = self.sim.avatars.get(session.user_id)
                if avatar is not None and avatar.actor.zone in self.world.zones:
                    # The record opens over the hall: the header carries the
                    # place's real safety word (game design 2.1), not the
                    # renderer's default for a Wake with no body.
                    # The door reads it from the inner body it renders.
                    body.setdefault("body", {})["body_safety"] = self.world.zones[avatar.actor.zone].safety_at(avatar.actor.position)
                full = Frame("view", {"rev": session.view_revision + 1, "kind": "wake", "body": body})
                if session.publish_view(full, None, ctx.tick):
                    wake.dirty = False
                    if wake.stage == "name":
                        wake.prompt_id = f"wake:{session.id}:{session.view_revision}"
                        session.send(Frame("prompt", {"id": wake.prompt_id, "kind": "line", "label": "Name (Enter keeps default)", "max_len": 24}))
                continue
            player = self.players.get(session.player_id)
            if session.id in self.screens and (session.id in self.dirty_screens or session.needs_full_view):
                screen, cursor = self.screens[session.id]
                if screen == "characters":
                    owned = self.owned(session.user_id)
                    rows = [{"id": p.id, "cells": [p.name, p.archetype]} for p in owned]
                    if len(owned) < self.cap:
                        rows.append({"id": "new", "cells": ["Create a new character"]})
                    body = menu("YOUR CHARACTERS", rows, cursor, "One active body per BBS identity.")
                elif screen == "sheet":
                    body = self.sheet(player, cursor)
                elif screen == "cards":
                    body = cards(self.content, cursor, session.caps["width"], session.caps["height"],
                                 ask=not self.unread(session.player_id))
                elif screen == "rename":
                    pid, error = self.renaming.get(session.id, ("", ""))
                    target = self.players.get(pid)
                    body = {"title": "CHOOSE A NAME", "lines": [rules.gurney_rename(target.name if target else ""),
                            *([error] if error else [])], "hint": "Esc cancels", "clear_prompt": False}
                else:
                    body = {"title": "DELETE CHARACTER" if screen == "delete" else "SAVING", "lines": [
                        "This removes your character and its items.", "Your identity clock and receipts remain.", "Type the exact name: " + player.name],
                        "hint": "Esc cancels", "clear_prompt": screen != "delete"}
                kind = "menu" if screen in ("characters", "sheet", "cards") else "text"
                if session.publish_view(Frame("view", {"rev": session.view_revision + 1, "kind": kind, "body": body}), None, ctx.tick):
                    self.dirty_screens.discard(session.id)
                    if screen == "delete":
                        session.send(Frame("prompt", {"id": "delete:" + player.id, "kind": "line", "label": "Type name to delete", "max_len": 24}))
                    elif screen == "rename" and session.id in self.renaming:
                        session.send(Frame("prompt", {"id": "rename:" + self.renaming[session.id][0], "kind": "line", "label": "New name", "max_len": 24}))
            if player and player.id not in self.deleting and session.user_id in self.sim.avatars:
                avatar = self.sim.avatars[session.user_id]
                actor = avatar.actor
                stamp = (actor.position, actor.health, actor.stamina, actor.shock, actor.facing, avatar.perception.grid_key,
                         ctx.tick // (PRESENCE_CHECKPOINT_SECONDS * TICK_HZ), avatar.zone,
                         avatar.travel.departed if avatar.travel else None)
                if stamp != self.saved_stamps.get(player.id):
                    was_in_flight = bool(player.progress.get("travel"))
                    self.snapshot(player, avatar)
                    self.queue("save", session.user_id, player,
                               immediate=was_in_flight != bool(player.progress.get("travel")))
                    self.saved_stamps[player.id] = stamp
                    if self.screens.get(session.id, (None,))[0] == "sheet":
                        self.dirty_screens.add(session.id)
