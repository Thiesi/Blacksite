"""Pure character/Wake lifecycle. The I/O layer executes the write outbox."""

from copy import deepcopy
from dataclasses import replace
from datetime import datetime
from typing import Any

from blacksite.content.loader import ContentTree
from blacksite.server.clock import Clock, TICK_HZ
from blacksite.server.loop import TickContext
from blacksite.server.players import Player, pack_memory, unpack_memory
from blacksite.server.protocol import Frame
from blacksite.server.rules import character as rules
from blacksite.server.sessions import Session, Sessions
from blacksite.server.views.delta import ViewStore
from blacksite.server.wake import Wake, menu, wrapped
from blacksite.server.world.registry import World
from blacksite.server.world.simulation import Avatar, ZoneSimulation

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
        self.wakes: dict[str, Wake] = {}
        self.screens: dict[str, tuple[str, int]] = {}
        self.dirty_screens: set[str] = set()
        self.outbox: list[dict[str, Any]] = []
        self.pending: dict[str, tuple[Player, list[dict[str, Any]]]] = {}
        self.sleepers: dict[str, tuple[Any, int]] = {}
        self.saved_stamps: dict[str, tuple[Any, ...]] = {}
        self.deleting: set[str] = set()
        # Reconcile elapsed offline time before any caller can attach.
        for player in self.players.values():
            offline = player.progress.get("offline_at", player.last_seen_at)
            if offline and not self.protected(player):
                remaining = rules.SLEEPER_SECONDS - (clock.now_utc() - datetime.fromisoformat(offline)).total_seconds()
                if remaining <= 0:
                    self.recover(player)
                else:
                    actor = player.actor()
                    actor.stance = "sleeper"
                    world.enter(actor, player.zone, world.free_tile(player.zone, player.tile))
                    self.sleepers[player.id] = (actor, clock.now_tick() + int(remaining * TICK_HZ))
                    world.zones[player.zone].activate("sleeper:" + player.id, clock.now_tick())

    def owned(self, user: str) -> list[Player]:
        return sorted((p for p in self.players.values() if p.bbs_user_id == user and p.origin == self.sessions.origin), key=lambda p: p.id)

    def summary(self, user: str) -> dict[str, Any] | None:
        owned = self.owned(user)
        return owned[0].summary() if len(owned) == 1 else None

    def protected(self, player: Player) -> bool:
        return player.zone in self.world.zones and self.world.zones[player.zone].safety_at(player.tile) in ("safe", "pocket")

    def identity(self, user: str) -> dict[str, Any]:
        if user not in self.identities:
            self.identities[user] = {"first_decanted_at": self.clock.now_utc().isoformat(), "legal_at": None,
                                     "receipts": {}, "clone_debt": 0, "wake": {}}
            self.queue("identity", user)
        return self.identities[user]

    def queue(self, action: str, user: str, player: Player | None = None, **extra: Any) -> None:
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
            self.attach(session, owned[0])
        elif owned:
            self.screens[session.id] = ("characters", 0)
            self.dirty_screens.add(session.id)
        else:
            self.wakes[session.id] = Wake.restore(identity.get("wake", {}))
            if self.wakes[session.id].stage == "saving":
                self.wakes[session.id].stage = "card"

    def attach(self, session: Session, player: Player) -> None:
        sleeper = self.sleepers.pop(player.id, None)
        actor = sleeper[0] if sleeper else player.actor()
        if sleeper:
            self.world.zones[player.zone].deactivate("sleeper:" + player.id, self.clock.now_tick())
            self.world.leave(actor)
        actor.stance, actor.handle = "normal", session.door_info["handle"]
        player.bbs_handle = actor.handle
        avatar = Avatar(actor, player.zone)
        for zone_id, blob in player.progress.get("memory", {}).items():
            if zone_id in self.world.zones:
                zone = self.world.zones[zone_id].template
                avatar.perception.remembered[zone_id] = unpack_memory(blob, zone.width, zone.height)
        avatar.seen_zones = set(player.progress.get("seen_zones", []))
        self.world.enter(actor, player.zone, self.world.free_tile(player.zone, player.tile))
        session.player_id, session.subscribed, session.player_name = player.id, player.zone, player.name
        session.keymap_id = player.settings.get("keymap", "arrows")
        self.world.zones[player.zone].activate(session.id, self.clock.now_tick())
        self.sim.avatars[session.user_id] = avatar
        self.sim.views[session.id] = ViewStore()
        self.sim.published.pop(session.id, None)
        self.wakes.pop(session.id, None)
        self.screens.pop(session.id, None)
        player.progress.pop("offline_at", None)
        player.update_personhood(self.identity(session.user_id), self.clock.now_utc())
        self.queue("save", session.user_id, player, immediate=True)

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

    def disconnect(self, session: Session) -> None:
        wake = self.wakes.pop(session.id, None)
        self.screens.pop(session.id, None)
        self.dirty_screens.discard(session.id)
        if session.role != "caller":
            return
        if wake:
            self.identities[session.user_id]["wake"] = wake.saved()
            self.queue("identity", session.user_id)
        player = self.players.get(session.player_id)
        avatar = self.sim.avatars.get(session.user_id)
        if player is None or avatar is None or avatar.actor.id != player.id:
            return
        self.snapshot(player, avatar)
        self.sim.views.pop(session.id, None)
        self.sim.published.pop(session.id, None)
        self.world.zones[player.zone].deactivate(session.id, self.clock.now_tick())
        player.progress["offline_at"] = self.clock.now_utc().isoformat()
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
        # S10 supplies combat/death consequences; S07 has no combat producer.
        self.queue("save", player.bbs_user_id, player, immediate=True)

    def create(self, session: Session, card: str) -> None:
        wake = self.wakes[session.id]
        if len(self.owned(session.user_id)) >= self.cap or session.id in self.pending:
            return
        if not self.name_available(wake.name):
            wake.stage, wake.error = "name", "That name is already in use. Choose another."
            return
        self.serial += 1
        player = Player(f"{self.sessions.origin}:player:{self.serial}", self.sessions.origin, session.user_id,
                        session.door_info["handle"], wake.name, wake.archetype, self.clock.now_utc().isoformat())
        player.tile = self.world.zones[player.zone].template.meta.spawn
        player.health = rules.health_max(player.attributes["vitals"])
        player.stamina = rules.stamina_max(player.attributes["nerve"], player.attributes["frame"])
        if card != "none":
            player.standing[card] = rules.CARD_STANDING
        start = self.content.starts[player.archetype]
        items: list[dict[str, Any]] = []
        for template_id, quantity in start.items.items():
            template = self.content.items[template_id]
            while quantity:
                stack = min(quantity, template.stack_max)
                iid = f"{self.sessions.origin}:item:{(self.serial << 32) + len(items)}"
                items.append({"id": iid, "template": template_id, "owner": player.id, "quality": 1.0,
                              "ammo": 0, "charges": 0, "secured": template.secured_default,
                              "stack": stack, "created_at": player.created_at})
                player.inventory.append(iid)
                for slot, template_key in start.equipment.items():
                    if template_key == template_id:
                        player.equipment[slot] = iid
                for slot, template_key in start.implants.items():
                    if template_key == template_id:
                        player.implants[slot] = iid
                quantity -= stack
        player.progress = {"points": 0, "known_programs": list(start.programs), "known_hymns": list(start.hymns), "memory": {}}
        player.rig = {"native": bool(start.rig_slots), "slots": (list(start.programs) + [None] * start.rig_slots)[:start.rig_slots]}
        identity = self.identity(session.user_id)
        player.clone_debt = identity.get("clone_debt", 0)
        player.update_personhood(identity, self.clock.now_utc())
        self.pending[session.id] = player, items
        wake.stage = "saving"
        self.queue("create", session.user_id, player, items=items, serial=self.serial, token=session.id)

    def name_available(self, name: str) -> bool:
        key = rules.name_key(name)
        return all(rules.name_key(p.name) != key for p in [*self.players.values(), *(v[0] for v in self.pending.values())])

    def committed(self, effect: dict[str, Any], error: bool = False) -> None:
        token, action = effect.get("token"), effect["action"]
        session = self.sessions.active.get(token)
        if action == "create":
            player, _ = self.pending.pop(token)
            if error:
                wake = self.wakes.get(token)
                if wake:
                    wake.stage, wake.error, wake.dirty = "card", "The record did not settle. Enter retries; Esc takes no card.", True
                return
            self.players[player.id] = player
            self.identities[player.bbs_user_id]["wake"] = {}
            if session is not None and not session.closed:
                self.attach(session, player)
                session.send(Frame("toast", {"text": "The corridor is quiet today. Vesper's card points to the Tin Halo.", "role": "ui_text", "seconds": 8}))
        elif action == "delete":
            self.deleting.discard(effect["player"]["id"])
            if not error:
                self.players.pop(effect["player"]["id"], None)
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
                    self.wakes[token] = Wake()
                self.dirty_screens.add(token)

    def input(self, session: Session, frame: Frame, tick: int) -> None:
        name = frame.data.get("name", "") if frame.type == "intent" else ""
        key = frame.data.get("k", "") if frame.type == "key" else ""
        if name == "resync":
            session.needs_full_view = True
        wake = self.wakes.get(session.id)
        if wake:
            if wake.stage == "saving":
                return
            if wake.stage in ("archetype", "card"):
                count = len(rules.ARCHETYPES) if wake.stage == "archetype" else len(self.content.wake_cards) + 1
                if name == "menu_cursor":
                    delta = frame.data.get("args", {}).get("delta", frame.data.get("args", {}).get("dir", 0))
                    wake.cursor = max(0, min(count - 1, wake.cursor + (-1 if delta in (-1, "up") else 1)))
                elif name == "menu_close" or key in ("escape", "b", "B"):
                    if wake.stage == "card":
                        self.create(session, "none")
                    else:
                        session.send(Frame("bye", {"reason": "logout", "text": "You leave the hall."}))
                elif name == "menu_select":
                    if frame.data.get("expected_revision", session.view_revision) != session.view_revision:
                        wake.dirty = True
                        return
                    if wake.stage == "archetype":
                        wake.archetype, wake.stage, wake.error = rules.ARCHETYPES[wake.cursor][0], "name", ""
                    else:
                        card = [*self.content.wake_cards, "none"][wake.cursor]
                        self.create(session, card)
            elif wake.stage == "name":
                if name == "prompt_cancel":
                    wake.stage = "archetype"
                elif frame.type == "line" and frame.data["id"] == wake.prompt_id:
                    candidate = rules.normalize_name(frame.data["text"]) or rules.default_name(session.door_info["handle"])
                    if not rules.valid_name(candidate):
                        wake.error = "Use 2-24 columns of letters, digits, spaces, - _ '."
                    elif not self.name_available(candidate):
                        wake.error = "That name is already in use. Choose another."
                    else:
                        wake.name, wake.stage, wake.screen, wake.page, wake.error = candidate, "briefing", 1, 0, ""
            elif wake.stage == "briefing" and key:
                if key in ("escape", "b", "B"):
                    session.send(Frame("bye", {"reason": "logout", "text": "You leave the hall."}))
                else:
                    wake.advance_briefing(self.content, session.caps["width"], session.caps["height"], key)
            wake.dirty = True
            self.identities[session.user_id]["wake"] = wake.saved()
            self.queue("identity", session.user_id)
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
                    self.attach(session, owned[cursor])
                else:
                    self.screens.pop(session.id, None)
                    self.wakes[session.id] = Wake()
            elif name == "menu_close":
                session.send(Frame("bye", {"reason": "logout", "text": "You leave your place."}))
            self.dirty_screens.add(session.id)
            return
        if player is None:
            return
        if screen == "delete":
            if name == "prompt_cancel":
                self.screens[session.id] = ("sheet", 0)
            elif frame.type == "line" and frame.data["id"] == "delete:" + player.id:
                if frame.data["text"] == player.name:
                    identity = deepcopy(self.identities[session.user_id])
                    identity["clone_debt"], identity["wake"] = player.clone_debt, {}
                    self.deleting.add(player.id)
                    self.queue("delete", session.user_id, player, identity=identity, token=session.id)
                    self.screens[session.id] = ("saving", 0)
                else:
                    self.screens[session.id] = ("sheet", 0)
            self.dirty_screens.add(session.id)
        elif name == "delete_character" or (screen == "sheet" and name == "menu_select" and frame.data.get("args", {}).get("key") == "d"):
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
        elif key in ("p", "P"):
            self.screens[session.id] = ("sheet", 0)
            self.dirty_screens.add(session.id)
        else:
            self.sim.input(session, frame, tick)

    def me(self, session: Session) -> dict[str, Any]:
        player = self.players[session.player_id]
        identity = self.identities[session.user_id]
        days = max(0, (self.clock.now_utc() - datetime.fromisoformat(identity["first_decanted_at"])).days)
        return {"name": player.name, "handle": player.bbs_handle, "grade": player.grade,
                "chits": player.chits_hand, "lease_days": days, "legal_at": player.legal_at,
                "discharge_xp": rules.grade_threshold(rules.DISCHARGE_GRADE), "xp": player.xp}

    def sheet(self, player: Player, cursor: int) -> dict[str, Any]:
        me = self.me(next(s for s in self.sessions.active.values() if s.player_id == player.id))
        values = [("Archetype", player.archetype.title()), ("Grade", f"{player.grade} {rules.grade_name(player.grade)}"),
                  ("XP", f"{player.xp} / {rules.grade_threshold(min(30, player.grade + 1))}"),
                  ("Points", player.progress.get("points", 0)), ("Health", f"{player.health}/{rules.health_max(player.attributes['vitals'])}"),
                  ("Stamina", f"{player.stamina}/{rules.stamina_max(player.attributes['nerve'], player.attributes['frame'])}"),
                  ("Tolerance", rules.tolerance(player.attributes["vitals"], player.archetype)),
                  ("Evasion", rules.evasion(player.attributes["nerve"])), ("Carry kg", rules.carry_kg(player.attributes["frame"])),
                  ("Lease days", f"{me['lease_days']} / 90"), ("Early discharge XP", f"{player.xp} / {me['discharge_xp']}"),
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
                self.world.zones[actor.zone].deactivate("sleeper:" + pid, ctx.tick)
                self.world.leave(actor)
                del self.sleepers[pid]
                self.recover(player)
        self.sim.tick(ctx)
        for player in self.players.values():
            previous = player.legal_at
            player.update_personhood(self.identities[player.bbs_user_id], self.clock.now_utc())
            if previous != player.legal_at:
                self.queue("save", player.bbs_user_id, player, immediate=True)
        for avatar in self.sim.avatars.values():
            actor = avatar.actor
            if actor.zone and actor.shock > 0 and ctx.tick - actor.cooldowns.get("last_hit", -3 * TICK_HZ) >= 3 * TICK_HZ:
                actor.shock = max(0, actor.shock - rules.SHOCK_DECAY_PER_SECOND / TICK_HZ)
                self.world.zones[actor.zone].revision += 1

    def publish(self, ctx: TickContext) -> None:
        playing = tuple(s for s in ctx.sessions if s.id not in self.wakes and s.id not in self.screens)
        self.sim.publish(replace(ctx, sessions=playing))
        for session in ctx.sessions:
            if session.closed or session.role != "caller":
                continue
            wake = self.wakes.get(session.id)
            if wake is not None:
                if not wake.dirty and not session.needs_full_view:
                    continue
                body = wake.body(self.content, session.door_info["handle"], session.caps["width"], session.caps["height"])
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
                else:
                    body = {"title": "DELETE CHARACTER" if screen == "delete" else "SAVING", "lines": [
                        "This removes your character and its items.", "Your identity clock and receipts remain.", "Type the exact name: " + player.name],
                        "hint": "Esc cancels", "clear_prompt": screen != "delete"}
                kind = "menu" if screen in ("characters", "sheet") else "text"
                if session.publish_view(Frame("view", {"rev": session.view_revision + 1, "kind": kind, "body": body}), None, ctx.tick):
                    self.dirty_screens.discard(session.id)
                    if screen == "delete":
                        session.send(Frame("prompt", {"id": "delete:" + player.id, "kind": "line", "label": "Type name to delete", "max_len": 24}))
            if player and player.id not in self.deleting and session.user_id in self.sim.avatars:
                avatar = self.sim.avatars[session.user_id]
                actor = avatar.actor
                stamp = (actor.position, actor.health, actor.stamina, actor.shock, actor.facing, avatar.perception.grid_key,
                         ctx.tick // (PRESENCE_CHECKPOINT_SECONDS * TICK_HZ))
                if stamp != self.saved_stamps.get(player.id):
                    self.snapshot(player, avatar)
                    self.queue("save", session.user_id, player)
                    self.saved_stamps[player.id] = stamp
                    if self.screens.get(session.id, (None,))[0] == "sheet":
                        self.dirty_screens.add(session.id)
