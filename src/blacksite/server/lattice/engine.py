"""Socket-free Lattice lifecycle. Game design 6.1; entity model 3.3.

The body remains in its physical zone. Only its owner's subscription and
view change; the street continues to simulate and can still hurt it.
"""

from collections.abc import Callable
from math import ceil
from typing import Any

from blacksite.server.combat.engine import Combat
from blacksite.server.clock import TICK_HZ
from blacksite.server.lattice.presence import (
    ESCAPE_SECONDS, INTEGRITY_MAX, INTEGRITY_PER_SECOND,
    EscapeChannel, Presence, directional_neighbour,
)
from blacksite.server.lattice.sectors import Credentials, Sectors, access, permitted, requirement_label
from blacksite.server.loop import TickContext
from blacksite.server.players import Player
from blacksite.server.protocol import Frame
from blacksite.server.sessions import Session
from blacksite.server.world.actors import Actor
from blacksite.server.world.movement import direction
from blacksite.server.world.simulation import Avatar
from blacksite.server.lattice.cores import Sources
from blacksite.server.lattice.encounters import Encounters

PUBLIC_LOAN_SLOTS = 3  # Game design 6.1: public terminal loan rig.
TRANSITION_FRAMES = 3  # Terminal UI 3: bounded jack transition.


class Lattice:
    def __init__(self, combat: Combat, state: dict[str, Any] | None = None) -> None:
        self.combat, self.game, self.sim = combat, combat.game, combat.sim
        self.content, self.clock = combat.content, combat.clock
        self.sectors = Sectors(self.content.sectors.values())
        state = state or {}
        self.season = state.get("season", 0)
        self.sources = Sources(self.game.sessions.origin, state.get("lattice", {}), self.clock.now_tick())
        self.presences: dict[str, Presence] = {}
        self.transitions: dict[str, tuple[str, int]] = {}
        self.events: set[str] = set()  # S24 installs active event credentials.
        self.crew_of: Callable[[str], str | None] = lambda pid: None  # S22.
        self.social_overlay: Callable[[Session], bool] = lambda session: False
        self.orphans: dict[str, tuple[Session, Avatar]] = {}
        self.game.retained_avatar = self.retained_avatar
        self.game.attached = self.attached
        self.encounters = Encounters(self)

    def retained_avatar(self, player: Player) -> Avatar | None:
        held = self.orphans.pop(player.id, None)
        if held is None:
            return None
        old, avatar = held
        if avatar.actor.zone:
            self.game.world.zones[avatar.actor.zone].deactivate(old.id, self.clock.now_tick())
        self.sim.views.pop(old.id, None)
        self.sim.published.pop(old.id, None)
        self.sim.external_views.pop(old.id, None)
        self.transitions.pop(old.id, None)
        return avatar

    def attached(self, session: Session, player: Player) -> None:
        presence = self.presences.get(player.id)
        if presence:
            session.subscribed = presence.sector

    def avatar(self, session: Session) -> Avatar | None:
        held = self.orphans.get(session.player_id)
        avatar = held[1] if held else self.sim.avatars.get(session.user_id)
        return avatar if avatar and avatar.actor.id == session.player_id else None

    def public(self, presence: Presence) -> bool:
        return presence.instance is None and access(self.sectors.cells[presence.sector][presence.cell]) == "public"

    def session(self, pid: str) -> Session | None:
        return self.combat.session(pid)

    def location(self, session: Session) -> tuple[str, str] | None:
        presence = self.presences.get(session.player_id)
        if presence and presence.instance:
            return presence.descent or presence.sector, presence.instance+":"+presence.room
        return (presence.sector, presence.cell) if presence else None

    def log(self, session: Session, text: str, warning: bool = False) -> None:
        session.send(Frame("log", {"lines": [{"channel": "lat", "text": text,
            "role": "warning" if warning else "chan_lat", "at": self.clock.now_utc().isoformat()}]}))

    def jack_key(self, session: Session) -> str:
        return "Ctrl-O" if session.keymap_id == "vi" else "J"

    def saved(self, player: Player) -> dict[str, Any]:
        return player.progress.setdefault("lattice", {})

    def integrity(self, player: Player) -> float:
        state = self.saved(player)
        elapsed = max(0, self.clock.now_utc().timestamp()-state.get("out_at", self.clock.now_utc().timestamp()))
        return min(INTEGRITY_MAX, max(0, state.get("integrity", INTEGRITY_MAX))+elapsed*INTEGRITY_PER_SECOND)

    def found(self, player: Player, sector: str) -> set[str]:
        return set(self.saved(player).get("found_cells", {}).get(sector, []))

    def reveal(self, player: Player, sector: str, cell: str) -> bool:
        """Operator/debug hook; S14/S16/S24 supply real discovery actions."""
        if sector not in self.sectors.cells or cell not in self.sectors.cells[sector]:
            return False
        found = self.found(player, sector)
        found.add(cell)
        self.saved(player).setdefault("found_cells", {})[sector] = sorted(found)
        self.game.queue("save", player.bbs_user_id, player, immediate=True)
        return True

    def credentials(self, player: Player, presence: Presence) -> Credentials:
        programs = frozenset(pid for pid in presence.rig if pid and self.content.programs[pid].class_ != "key") | presence.key_programs
        tiers: dict[str, int] = {"key": presence.key_tier}
        for pid in programs:
            program = self.content.programs.get(pid)
            if program:
                tiers[program.class_] = (presence.key_tier if program.class_ == "key" else
                                        max(tiers.get(program.class_, 0), program.tier))
        return Credentials(frozenset(self.game.item_templates.get(iid, iid) for iid in player.inventory),
            programs, tuple(tiers.items()), player.faction, tuple(player.standing.items()), frozenset(self.events))

    def label(self, requirement: str | None) -> str:
        parts = (requirement or "").split(":")
        key = parts[-1]
        for records in (self.content.items, self.content.programs, self.content.factions):
            record = records.get(key)
            if record:
                return record.name
        if len(parts) == 3 and parts[0] == "standing":
            faction = self.content.factions.get(parts[1])
            return f"{faction.name if faction else parts[1]} standing {parts[2]}"
        return requirement_label(requirement)

    def accepts(self, player: Player, presence: Presence, cell: Any, requirement: str | None) -> bool:
        if (requirement and requirement.startswith("program:key:") and cell.gate_owner == "halvard"
                and "prg_signet" in presence.key_programs):
            return True
        return permitted(requirement, self.credentials(player, presence))

    def terminal(self, actor: Actor, target: str | None = None) -> Any:
        zone = self.game.world.zones[actor.zone]
        return next((obj for obj in sorted(zone.objects.values(), key=lambda o: o.spec.id)
            if obj.spec.kind == "terminal" and (target is None or obj.spec.id == target)
            and max(abs(actor.x-obj.spec.tile[0]), abs(actor.y-obj.spec.tile[1])) <= 1), None)

    def carried_slots(self, player: Player) -> int:
        result = 0
        for iid in set(player.inventory) | set(player.implants.values()):
            item = self.game.items.get(iid)
            template = self.content.items.get(item.template) if item else None
            if template and template.implant and template.implant.rig_slots:
                if template.class_ == "rig" or iid in player.implants.values():
                    result = max(result, template.implant.rig_slots)
        return result

    def jack_in(self, session: Session, target: str | None = None) -> None:
        player = self.game.players.get(session.player_id)
        avatar = self.sim.avatars.get(session.user_id)
        if not player or not avatar or avatar.actor.id != player.id or player.id in self.presences:
            return
        actor = avatar.actor
        if (actor.zone is None or avatar.travel or actor.stance in ("down", "dead", "sleeper")
                or session.id in self.game.screens or session.id in self.sim.maps
                or session.id in self.combat.menus or session.id in self.combat.commerce.menus
                or session.id in self.combat.commerce.prompts):
            self.log(session, "Return to the street before you jack in.", True)
            return
        if self.combat.commerce.pending or self.combat.commerce.waiting or player.id in self.combat.casts:
            self.log(session, "Let your current action settle first.", True)
            return
        terminal = self.terminal(actor, target)
        if target is not None and terminal is None:
            self.log(session, "Move next to that terminal.", True)
            return
        slots = max(self.content.starts[player.archetype].rig_slots or 0,
                    self.carried_slots(player))
        if not terminal and not slots:
            self.log(session, "Move next to a public terminal, or carry a rig.", True)
            return
        zone = self.game.world.zones[actor.zone]
        sector = terminal.spec.params.get("sector") if terminal else None
        sector = sector or zone.template.meta.sector
        if sector not in self.sectors.records:
            self.log(session, "This terminal has no live district link.", True)
            return
        if terminal and not slots:
            slots = PUBLIC_LOAN_SLOTS
        configured = player.rig.get("slots", [])
        if not configured:
            configured = list(self.content.starts[player.archetype].programs)
        # Shrinking capacity never retains half of a multi-slot program.
        occupied: set[int] = set()
        clean: list[str | None] = [None]*slots
        for index, pid in enumerate(configured[:slots]):
            program = self.content.programs.get(pid)
            if program and index+program.slots <= slots and not occupied.intersection(range(index, index+program.slots)) and pid not in clean:
                clean[index] = pid
                occupied.update(range(index, index+program.slots))
        rig = tuple(clean)
        presence = Presence(player.id+":presence", player.id, sector, self.sectors.entrance(sector), rig,
                            integrity=self.integrity(player))
        self.presences[player.id] = presence
        actor.stance = "jacked"
        actor.target = None
        actor.cooldowns.pop("move", None)
        zone.revision += 1
        session.subscribed = sector
        self.transitions[session.id] = "in", self.clock.now_tick()
        state = self.saved(player)
        if not state.get("initiated"):
            ritual = self.content.text.get("lattice-jackin")
            if ritual:
                for line in ritual.body.splitlines():
                    if line:
                        self.log(session, line)
            state["initiated"] = True
        self.log(session, "You enter "+self.sectors.records[sector].district+". "+self.sectors.cells[sector][presence.cell].label+" resolves.")
        self.notify(presence, player.name+" arrives.", exclude=player.id)
        self.game.snapshot(player, avatar)
        self.game.queue("save", session.user_id, player, immediate=True)

    def notify(self, presence: Presence, text: str, exclude: str | None = None) -> None:
        for other in self.presences.values():
            if other.player_id != exclude and self.encounters.location(other) == self.encounters.location(presence):
                session = self.session(other.player_id)
                if session:
                    self.log(session, text)

    def leave(self, session: Session, transition: bool = True) -> None:
        presence = self.presences.pop(session.player_id, None)
        if presence is None:
            return
        player = self.game.players[presence.player_id]
        self.encounters.leave(presence)
        self.notify(presence, player.name+" leaves.")
        state = self.saved(player)
        state.update(integrity=presence.integrity, out_at=self.clock.now_utc().timestamp())
        avatar = self.avatar(session)
        if avatar:
            if avatar.actor.stance == "jacked":
                avatar.actor.stance = "normal"
            if avatar.actor.zone:
                self.game.world.zones[avatar.actor.zone].revision += 1
            session.subscribed = avatar.zone
            self.sim.reset_view(session, avatar)
        overlay = self.sim.external_views.get(session.id)
        if overlay and overlay[0] in ("lattice", "menu"):
            self.sim.external_views.pop(session.id, None)
        self.transitions.pop(session.id, None)
        if transition and avatar and avatar.actor.stance == "normal":
            self.transitions[session.id] = "out", self.clock.now_tick()
        self.log(session, "You jack out. Your body is here.")
        self.game.queue("save", session.user_id, player, immediate=True)
        held = self.orphans.pop(player.id, None)
        if held:
            self.game.disconnect(held[0], held[1])

    def jack_out(self, session: Session) -> None:
        presence = self.presences.get(session.player_id)
        if not presence:
            return
        if self.public(presence):
            self.leave(session)
        elif presence.escape is None:
            actor = self.avatar(session).actor
            presence.destination = None
            presence.room_destination = None
            presence.cast = presence.procedure = None
            presence.escape = EscapeChannel(self.clock.now_tick()+ceil(ESCAPE_SECONDS*TICK_HZ),
                                            self.encounters.hit_serial(presence))
            self.log(session, "You start a two-second escape. Hits can interrupt it three times.")

    def move(self, session: Session, sector: str, cell: str) -> None:
        presence = self.presences[session.player_id]
        if not self.encounters.idle(presence):
            raise ValueError("Finish or cancel the current action first.")
        if presence.instance:
            raise ValueError("Use a linked room or retreat through the core entrance.")
        if self.clock.now_tick() < presence.pinned_until:
            raise ValueError("You are pinned. J still starts escape.")
        player = self.game.players[presence.player_id]
        if not self.sectors.adjacent(presence.sector, presence.cell, sector, cell):
            raise ValueError("Choose a linked cell.")
        target = self.sectors.cells[sector][cell]
        if access(target) != "public" and self.sources.locked(player.bbs_user_id, sector, self.clock.now_utc().timestamp()):
            raise ValueError("This identity's five-minute district lockout is still active.")
        if access(target) == "hidden" and cell not in self.found(player, sector):
            raise ValueError("No known link leads there.")
        source = self.sectors.cells[presence.sector][presence.cell]
        for owner, requirement in ((target, target.requirement), (source, source.uplink.requirement if sector != presence.sector and source.uplink else None)):
            if not self.accepts(player, presence, owner, requirement):
                raise ValueError("This link requires "+self.label(requirement)+".")
        if presence.begin_move(sector, cell, self.clock.now_tick(), player.attributes["cortex"],
                               self.encounters.move_multiplier(player)):
            presence.redline_move = presence.effects.has("prg_redline", self.clock.now_tick())
            if presence.redline_move:
                presence.move_until = min(presence.move_until, self.clock.now_tick()+
                    ceil(float(self.content.programs["prg_redline"].effect.amount)*TICK_HZ))

    def input(self, session: Session, frame: Frame, tick: int) -> bool:
        name = frame.data.get("name", "") if frame.type == "intent" else ""
        key = frame.data.get("k", "") if frame.type == "key" else ""
        args = frame.data.get("args", {})
        table = next((m for m in self.sim.keymap.get("keymaps", []) if m["id"] == session.keymap_id), {})
        action = next((a for a, keys in table.get("bindings", {}).items() if key in keys), name)
        presence = self.presences.get(session.player_id)
        if session.pending_prompts.get("chat"):
            return False
        if presence:
            actor = self.sim.avatars[session.user_id].actor
            if actor.stance in ("down", "dead"):
                self.leave(session, transition=False)
                return False
            if self.social_overlay(session):
                return not (name in ("menu_close", "menu_cursor", "menu_select", "resync", "settings", "ignore", "report", "chat") or frame.type == "line")
            if action == "sitrep":
                return False
            if name == "resync" or frame.type == "line" or name.startswith("chat") or action.startswith("chat_") or name in ("ignore", "report", "settings"):
                return False
            try:
                if action == "jack" or name == "lat.jack_out":
                    self.encounters.menus.pop(session.id, None)
                    self.jack_out(session)
                elif self.encounters.input(session, presence, name, action, key, args,
                                           frame.data.get("expected_revision")):
                    pass
                elif name == "lat.move":
                    sector, cell = args.get("sector", presence.sector), args.get("cell")
                    if not isinstance(sector, str) or not isinstance(cell, str):
                        raise ValueError("Choose a linked cell.")
                    self.move(session, sector, cell)
                elif action.startswith("move_") or name == "move":
                    vector = direction(action[5:] if action.startswith("move_") else args.get("dir", ""))
                    source = self.sectors.cells[presence.sector][presence.cell]
                    neighbours = {c.id: c.pos for c in self.sectors.known(presence.sector, self.found(self.game.players[presence.player_id], presence.sector)) if c.id in source.neighbours}
                    target = directional_neighbour(source.pos, neighbours, vector) if vector else None
                    if target:
                        self.move(session, presence.sector, target)
                elif action == "interact" or key in ("e", "E"):
                    cell = self.sectors.cells[presence.sector][presence.cell]
                    if cell.uplink:
                        self.move(session, cell.uplink.sector, cell.uplink.cell)
                    elif cell.kind == "core_entrance":
                        self.log(session, "The core link is not open yet.")
                    elif cell.kind == "descent":
                        self.log(session, "The descent has no stable route yet.")
                elif key in tuple("1234567") or action.startswith("program_") or name.startswith("program"):
                    self.log(session, "Programs are not online yet.")
                elif (action in ("inventory", "map", "character", "abilities", "fire", "weapon_cycle", "stealth")
                      or name.startswith(("inv.", "bank.", "vendor.", "ability", "pickup", "recovery", "stance", "sprint"))):
                    if session.allow("lattice_body_hint", tick, 1, 1):
                        self.log(session, "Your body cannot act here. "+self.jack_key(session)+" returns to the street.")
            except (ValueError, KeyError, TypeError) as exc:
                self.log(session, str(exc) if isinstance(exc, ValueError) else "Choose a known linked cell.", True)
            return True  # The helpless body never receives physical controls.
        if action == "jack" or name == "lat.jack_in":
            target = args.get("target")
            if target is None or isinstance(target, str):
                self.jack_in(session, target)
            return True
        if name.startswith("lat."):
            return True
        return False

    def terminal_input(self, session: Session, frame: Frame, tick: int) -> bool:
        """Fallback E interaction after counters, recovery and NPC services.

        J remains an explicit jack action. Sharing a tile or adjacency
        with a terminal must not make an existing counter unusable.
        """
        name = frame.data.get("name", "") if frame.type == "intent" else ""
        key = frame.data.get("k", "") if frame.type == "key" else ""
        table = next((m for m in self.sim.keymap.get("keymaps", []) if m["id"] == session.keymap_id), {})
        action = next((a for a, keys in table.get("bindings", {}).items() if key in keys), name)
        if action == "interact" or key in ("e", "E"):
            avatar = self.sim.avatars.get(session.user_id)
            if avatar and avatar.actor.zone and self.terminal(avatar.actor):
                self.jack_in(session)
                return True
        return False

    def view(self, session: Session, presence: Presence) -> dict[str, Any]:
        player = self.game.players[presence.player_id]
        sector = self.sectors.records[presence.sector]
        known = self.sectors.known(sector.id, self.found(player, sector.id))
        ids = {cell.id for cell in known}
        cells = [{"id": c.id, "x": c.pos[0], "y": c.pos[1], "kind": c.kind,
                  "access": access(c), "label": c.label, "known": True,
                  "core": c.core_id, "placeholder": c.core_placeholder,
                  "uplink": bool(c.uplink)} for c in known]
        edges = [{"a": c.id, "b": other, "kind": "hidden" if "hidden" in (access(c), access(self.sectors.cells[sector.id][other]))
                  else "gated" if "gated" in (access(c), access(self.sectors.cells[sector.id][other])) else "public"}
                 for c in known for other in c.neighbours if other in ids and c.id < other]
        actor = self.sim.avatars[session.user_id].actor
        peers = []
        for other in self.presences.values():
            if (other.player_id == player.id or other.sector != presence.sector
                    or other.instance != presence.instance):
                continue
            crew = self.crew_of(player.id)
            if self.encounters.location(other) != self.encounters.location(presence) and not (crew and self.crew_of(other.player_id) == crew):
                continue
            peer = self.game.players[other.player_id]
            other_actor = self.combat.actor(peer)
            relation = self.combat.relation(actor, other_actor) if other_actor else "neutral"
            peers.append({"id": other.id, "cell": other.cell, "name": peer.name,
                          "role": "faction_"+(peer.faction or "freelance"), "relation": relation,
                          "marker_role": {"hostile": "player_hostile", "allied": "player_crew"}.get(relation, "player_neutral")})
        cell = self.sectors.cells[sector.id][presence.cell]
        return {"title": sector.district.upper()+" / LATTICE", "sector": sector.id,
            "layout_size": list(sector.layout_size), "cells": cells, "edges": edges,
            "presences": peers, "me": {"cell": presence.cell, "integrity": presence.integrity,
                "trace": presence.trace, "rig": [{"slot": i+1, "program": pid,
                    "name": self.content.programs[pid].name if pid in self.content.programs else "Empty", "cd": 0} for i, pid in enumerate(presence.rig)],
                "move_ticks": max(0, presence.move_until-self.clock.now_tick()) if presence.destination else 0,
                "escape_ticks": max(0, presence.escape.until_tick-self.clock.now_tick()) if presence.escape else None,
                "interruptions": presence.escape.interruptions if presence.escape else 0,
                "body_hp": actor.health, "body_hp_max": actor.health_max,
                "hit_serial": actor.behaviour.get("hit_serial", 0)},
            "room": None, "label": cell.label,
            "body_safety": self.game.world.zones[actor.zone].safety_at(actor.position),
            "hint": "Arrows links  E uplink / enter  "+self.jack_key(session)+" jack out  Tab target  1-7 cast  R rig"}

    def tick(self, ctx: TickContext) -> None:
        self.encounters.advance(ctx.tick)
        for pid, presence in tuple(self.presences.items()):
            held = self.orphans.get(pid)
            session = held[0] if held else self.session(pid)
            if not session:
                continue
            actor = self.avatar(session).actor
            if actor.stance != "jacked" or not actor.zone:
                self.leave(session, transition=False)
                continue
            waiting_hit = self.combat.commerce.pending and self.encounters.pending_hit(pid)
            if presence.escape and not waiting_hit and presence.escape.advance(ctx.tick, self.encounters.hit_serial(presence)):
                self.leave(session)
                continue
            if held:
                continue  # Hazards/escape continue; no output to a dead transport.
            if presence.destination and ctx.tick >= presence.move_until:
                # Membership/event credentials may change during a traversal.
                target_sector, target_cell = presence.destination
                cell = self.sectors.cells[target_sector][target_cell]
                source = self.sectors.cells[presence.sector][presence.cell]
                requirements = [cell.requirement]
                if target_sector != presence.sector and source.uplink:
                    requirements.append(source.uplink.requirement)
                locked = access(cell) != "public" and self.sources.locked(self.game.players[pid].bbs_user_id, target_sector, self.clock.now_utc().timestamp())
                if locked or not (self.accepts(self.game.players[pid], presence, cell, requirements[0]) and
                        all(self.accepts(self.game.players[pid], presence, source, r) for r in requirements[1:])):
                    presence.destination = None
                    self.log(session, "The link no longer accepts your credentials.", True)
                else:
                    self.notify(presence, self.game.players[pid].name+" leaves.", exclude=pid)
                    presence.arrive(ctx.tick)
                    self.encounters.trace(presence, 0, entered=True)
                    if pid not in self.presences:
                        continue
                    if presence.redline_move:
                        presence.integrity = max(0, presence.integrity-float(self.content.programs["prg_redline"].effect.params["integrity_per_move"]))
                        if presence.integrity <= 0:
                            self.encounters.force_out(presence)
                            continue
                    self.encounters.follow(presence)
                    session.subscribed = presence.sector
                    self.log(session, "You enter "+cell.label+".")
                    self.notify(presence, self.game.players[pid].name+" arrives.", exclude=pid)
            body = self.view(session, presence)
            transition = self.transitions.get(session.id)
            if transition:
                age = ctx.tick-transition[1]
                if age < TRANSITION_FRAMES:
                    body["transition"] = {"direction": transition[0], "frame": age+1}
                else:
                    self.transitions.pop(session.id)
            if not self.social_overlay(session):
                self.sim.external_views[session.id] = self.encounters.view(session, presence, body)
        for sid, (kind, start) in tuple(self.transitions.items()):
            if kind != "out":
                continue
            session = self.game.sessions.active.get(sid)
            if not session or session.closed or ctx.tick-start >= TRANSITION_FRAMES:
                self.transitions.pop(sid, None)
                overlay = self.sim.external_views.get(sid)
                if overlay and overlay[0] == "lattice":
                    self.sim.external_views.pop(sid, None)
                continue
            actor = self.sim.avatars[session.user_id].actor
            if actor.stance in ("down", "dead"):
                self.transitions.pop(sid)
                continue
            self.sim.external_views[sid] = "lattice", {"title": "RETURNING", "cells": [], "edges": [],
                "me": {}, "presences": [], "transition": {"direction": "out", "frame": ctx.tick-start+1},
                "hint": "Your body is already back. The street continues."}

    def disconnect(self, session: Session) -> bool:
        presence = self.presences.get(session.player_id)
        avatar = self.avatar(session)
        if (presence and avatar and avatar.actor.stance == "jacked"
                and not self.public(presence)):
            self.orphans[presence.player_id] = session, avatar
            self.jack_out(session)
            return True
        self.leave(session, transition=False)
        self.transitions.pop(session.id, None)
        return False

    def shutdown(self) -> None:
        for pid in tuple(self.presences):
            held = self.orphans.get(pid)
            session = held[0] if held else self.session(pid)
            if session:
                self.leave(session, transition=False)

    def who(self) -> list[dict[str, str]]:
        return [{"player": self.game.players[p.player_id].name, "id": p.player_id,
                 "sector": p.sector, "cell": p.cell} for p in sorted(self.presences.values(), key=lambda p: (p.sector, p.cell, p.player_id))]

    def debug_reveal(self, player_id: str, sector: str, cell: str) -> dict[str, bool]:
        player = self.game.players.get(player_id)
        return {"ok": bool(player and self.reveal(player, sector, cell))}
