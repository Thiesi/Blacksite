"""Game 8.4: physical workshop/harvest channels and atomic craft receipts."""

from blacksite.server.interaction import Interaction, interact, object_interaction
from copy import deepcopy
from typing import Any
from collections.abc import Callable

from blacksite.content.schema import ItemTemplate, ObjectSpec
from blacksite.server.channels import PhysicalChannel
from blacksite.server.clock import TICK_HZ
from blacksite.server.inventory import Inventory
from blacksite.server.items import make_item
from blacksite.server.loop import TickContext
from blacksite.server.players import Player
from blacksite.server.progression import Grant
from blacksite.server.progression_engine import ProgressionEngine
from blacksite.server.protocol import Frame
from blacksite.server.quality import roll, bounds
from blacksite.server.salvage import Salvage
from blacksite.server.sessions import Session
from blacksite.server.skills import Use
from blacksite.server.wake import menu
from blacksite.server.world.simulation import MENU_TIMEOUT_SECONDS


class Fabrication:
    def __init__(self, progression: ProgressionEngine, salvage: Salvage) -> None:
        self.progression, self.salvage = progression, salvage
        self.commerce, self.game, self.clock = progression.commerce, progression.game, progression.clock
        self.sim, self.content = self.commerce.sim, progression.content
        self.channels: dict[str, PhysicalChannel] = {}
        self.menus: dict[str, tuple[str, int, int]] = {}
        self.requests: dict[str, list[str]] = {}
        self.quality_bonus: Callable[[Player, str], float] = lambda player, zone: 0  # S21.

    def recipes(self, player: Player) -> list[ItemTemplate]:
        known = set(player.progress.get("known_schematics", ()))
        known.update(sid for sid, count in player.progress.get("schematic_charges", {}).items() if count > 0)
        return [self.content.items[sid] for sid in sorted(known)
                if sid in self.content.items and self.content.items[sid].schematic
                and self.content.active("items", sid)]

    def workshop(self, session: Session, target: str) -> ObjectSpec:
        if not self.commerce.ready(session):
            raise ValueError("Return to your body before using the workshop.")
        obj = self.commerce.nearby(session, target)
        if obj.spec.kind != "workshop":
            raise ValueError("Choose a workshop.")
        return obj.spec

    def check(self, session: Session, target: str, recipe_id: str) -> ItemTemplate:
        shop = self.workshop(session, target)
        player = self.game.players[session.player_id]
        recipe = next((row for row in self.recipes(player) if row.id == recipe_id), None)
        if recipe is None:
            raise ValueError("Learn that schematic first.")
        output = self.content.items.get(recipe.schematic.output)
        makes = shop.params.get("makes", "any")
        allowed = (makes == "any" or makes == "rigs_programs" and (
            recipe.schematic.output in self.content.programs or output and output.class_ == "rig")
            or makes == "chemical_melee" and output and (
                output.class_ == "drug" or output.weapon and (
                    output.weapon.melee or output.weapon.damage_type == "chemical")
                or output.drone and output.drone.attack and output.drone.attack.damage_type == "chemical"))
        if not allowed:
            raise ValueError("This workshop makes "+makes.replace("_", " and ")+" only.")
        if not self.content.active("items" if output else "programs", recipe.schematic.output):
            raise ValueError("That output is not commissioned yet.")
        if output is None and recipe.schematic.output in player.progress.get("known_programs", ()):
            raise ValueError("You already know that program.")
        if self.progression.modifiers(player).skill(player, "fabrication") < recipe.schematic.skill_min:
            raise ValueError(f"Fabrication {recipe.schematic.skill_min} required.")
        amounts = self.amounts(player)
        if any(amounts.get(grade, 0) < need for grade, need in recipe.schematic.inputs.items()):
            raise ValueError("You need more unbound salvage. Your inputs remain.")
        return recipe

    def amounts(self, player: Player) -> dict[str, int]:
        amounts: dict[str, int] = {}
        for iid in player.inventory:
            item = self.commerce.items[iid]
            block = self.content.items[item.template].salvage
            if block and not item.bound and iid not in player.implants.values():
                amounts[block.grade] = amounts.get(block.grade, 0)+item.stack
        return amounts

    def close(self, session: Session) -> None:
        self.menus.pop(session.id, None)
        self.sim.external_views.pop(session.id, None)
        avatar = self.sim.avatars.get(session.user_id)
        if avatar:
            self.sim.reset_view(session, avatar)

    def stop(self, session: Session, message: str = "") -> None:
        self.channels.pop(session.player_id, None)
        actor = self.game.combat.actor(self.game.players[session.player_id]) if session.player_id in self.game.players else None
        if actor:
            actor.behaviour.pop("channel", None)
            if actor.zone:
                self.game.world.zones[actor.zone].revision += 1
        if message and not session.closed:
            self.sim.log(session, message)

    def start(self, session: Session, target: str, recipe: str = "") -> None:
        if (session.player_id in self.channels or session.player_id in self.progression.lattice.interlock.cuts
                or session.id in self.commerce.using):
            raise ValueError("Finish or cancel your current action first.")
        if not self.commerce.ready(session) or self.salvage.rules is None:
            raise ValueError("This service is not commissioned.")
        obj = self.commerce.nearby(session, target)
        actor = self.sim.avatars[session.user_id].actor
        if recipe:
            self.check(session, target, recipe)
            seconds, kind = self.salvage.rules.craft_seconds, "craft"
        else:
            if obj.spec.kind != "salvage_node" or obj.state.get("units", 0) < 1:
                raise ValueError("Choose a salvage node with units remaining.")
            seconds, kind = self.salvage.rules.harvest_seconds, "harvest"
        self.close(session)
        self.channels[session.player_id] = PhysicalChannel("", actor.zone, target, actor.position,
            self.clock.now_tick()+seconds*TICK_HZ, int(actor.behaviour.get("hit_serial", 0)), kind, recipe)
        self.sim.log(session, f"You {kind}. Hold still for {seconds}s. Damage interrupts; Esc cancels.")

    def craft(self, session: Session, channel: PhysicalChannel) -> None:
        recipe = self.check(session, channel.object, channel.recipe)
        player = self.game.players[session.player_id]
        draft, items = deepcopy(player), deepcopy(self.commerce.items)
        proposal = deepcopy(self.salvage.state)
        serial = max(self.commerce.serial, *(int(i.rsplit(":", 1)[-1]) for i in items if i.rsplit(":", 1)[-1].isdigit()))
        def next_id() -> str:
            nonlocal serial
            serial += 1
            return f"{self.game.sessions.origin}:item:{serial}"
        inv = Inventory(items, self.content.items, self.progression.modifiers(draft).secured_slots)
        for grade, need in recipe.schematic.inputs.items():
            for iid in tuple(draft.inventory):
                item = items[iid]
                block = self.content.items[item.template].salvage
                if block and block.grade == grade and not item.bound:
                    count = min(need, item.stack)
                    if count:
                        inv.remove(draft, iid, count, next_id)
                        need -= count
                if not need:
                    break
            if need:
                raise ValueError("Your salvage changed. The craft stops.")
        output = self.content.items.get(recipe.schematic.output)
        rng = self.salvage.rng(channel.zone, proposal, craft=True)
        skill = self.progression.modifiers(player).skill(player, "fabrication")
        quality = roll(output, skill, rng, self.quality_bonus(player, channel.zone))
        proposal["craft_rng"][channel.zone] = rng.getstate()
        if output:
            count = output.stack_max if output.class_ == "ammo" else 1
            inv.add(draft, make_item(next_id(), output, draft.id, self.clock.now_utc().isoformat(), count, quality))
            name, tier = output.name, output.tier
        else:
            program = self.content.programs[recipe.schematic.output]
            draft.progress.setdefault("known_programs", []).append(program.id)
            name, tier = program.name, program.tier
        if recipe.schematic.single_use:
            draft.progress["schematic_charges"][recipe.id] -= 1
        proposal["serial"] += 1
        receipt = f"craft:{self.game.sessions.origin}:{proposal['serial']}"
        patch, identity, reward = self.progression.reward_patch(player,
            Grant("craft", receipt, True, scope=recipe.id, tier=tier, consumed_inputs=True))
        draft.progress.update({key: value for key, value in patch.pop("progress", {}).items()
                               if key not in player.progress or value != player.progress[key]})
        for key, value in patch.items():
            setattr(draft, key, deepcopy(value))
        self.progression.gain(draft, Use("fabricate", "fabrication", receipt, True, changed=True))
        patch.update(inventory=draft.inventory, equipment=draft.equipment,
                     progress=draft.progress, skills=draft.skills, attributes=draft.attributes)
        def finished(success: bool) -> None:
            self.stop(session)
            if success:
                self.progression.notify_reward(player, reward)
                self.progression.sync_actor(player)
                self.sim.log(session, f"You make {name}. Quality {quality*100:.0f}%.")
            else:
                self.sim.log(session, "The craft could not be saved. Your inputs remain.")
        if not self.salvage.commit(proposal, player, patch, items, serial, finished, identity):
            raise ValueError("The city is busy. Your inputs remain.")

    def body(self, session: Session, target: str, cursor: int) -> dict[str, Any]:
        shop = self.workshop(session, target)
        player = self.game.players[session.player_id]
        recipes, amounts = self.recipes(player), self.amounts(player)
        rows = []
        skill = self.progression.modifiers(player).skill(player, "fabrication")
        for recipe in recipes:
            output = self.content.items.get(recipe.schematic.output) or self.content.programs[recipe.schematic.output]
            rows.append({"id": recipe.id, "cells": [output.name, " ".join(
                f"{grade} {amounts.get(grade, 0)}/{need}" for grade, need in recipe.schematic.inputs.items()),
                f"Fab {recipe.schematic.skill_min}"]})
        cursor = max(0, min(cursor, len(rows)-1))
        detail = "Learn schematics from your inventory. F fabricates; Esc/B leaves."
        if recipes:
            recipe = recipes[cursor]
            output = self.content.items.get(recipe.schematic.output)
            if output and output.quality.kind != "none":
                bonus = self.quality_bonus(player, self.sim.avatars[session.user_id].zone)
                lo, hi = bounds(output, skill, bonus)
                detail = f"Quality {lo*100:.0f}-{hi*100:.0f}%. Only the declared primary stat scales."
            else:
                detail = "Fixed output; no quality roll. Pack counts and permissions stay fixed."
            detail += f"\n{self.salvage.rules.craft_seconds}s channel. Inputs leave only on completion."
        title = shop.params.get("name", "WORKSHOP")
        body = menu(title, rows, cursor, detail+"\nMakes: "+shop.params.get("makes", "any").replace("_", " and "), "F fabricate  Esc/B returns")
        body.update(kind="workshop", actions=[{"key": "f", "label": "fabricate"}])
        return body

    def interaction(self, session: Session, frame: Frame) -> Interaction | None:
        if session.id in self.menus:
            return Interaction()
        if (not self.commerce.ready(session) or session.id in self.sim.external_views
                or session.pending_prompts or not interact(frame)):
            return None
        actor = self.sim.avatars[session.user_id].actor
        nearby = sorted((obj for obj in self.game.world.zones[actor.zone].objects.values()
            if obj.spec.kind != 'salvage_field' and max(abs(obj.spec.tile[0]-actor.x), abs(obj.spec.tile[1]-actor.y)) <= 1),
            key=lambda obj: (obj.spec.tile != actor.position, obj.spec.id))
        if nearby and nearby[0].spec.kind in ('salvage_node', 'workshop'):
            return object_interaction(nearby[0], 'harvest' if nearby[0].spec.kind == 'salvage_node' else 'open')
        return None

    def input(self, session: Session, frame: Frame, tick: int, *, interaction: Interaction | None = None) -> bool:
        name = frame.data.get("name", "") if frame.type == "intent" else ""
        key = frame.data.get("k", "") if frame.type == "key" else ""
        args = frame.data.get("args", {})
        if session.player_id in self.channels and (name == "menu_close" or key in ("escape", "b", "B")):
            self.stop(session, "You stop working. Completed harvest units stay with you.")
            return True
        try:
            if session.id in self.menus:
                target, cursor, opened = self.menus[session.id]
                if name == "menu_close" or key in ("escape", "b", "B"):
                    self.close(session)
                elif name == "menu_cursor" and type(args.get("delta")) is int:
                    count = len(self.recipes(self.game.players[session.player_id]))
                    self.menus[session.id] = target, max(0, min(cursor+args["delta"], count-1)), opened
                elif name == "menu_select":
                    if frame.data.get("expected_revision") != session.view_revision:
                        return True
                    request = frame.data.get("request_id")
                    if request and request in self.requests.get(session.id, ()):
                        return True
                    if args.get("key", "enter") in ("f", "enter"):
                        self.start(session, target, args.get("row", ""))
                        if request:
                            self.requests.setdefault(session.id, []).append(request)
                            self.requests[session.id] = self.requests[session.id][-128:]
                return True
            if name == "workshop.fabricate":
                self.start(session, args.get("target", ""), args.get("schematic", ""))
                return True
            if not self.commerce.ready(session) or session.id in self.sim.external_views or session.pending_prompts:
                return False
            if name != "interact" and key not in ("e", "E"):
                return False
            actor = self.sim.avatars[session.user_id].actor
            choice = interaction or self.interaction(session, frame)
            if not choice:
                return False
            obj = choice.value
            if obj.spec.kind == "salvage_node":
                self.start(session, obj.spec.id)
                return True
            if obj.spec.kind == "workshop":
                self.menus[session.id] = obj.spec.id, 0, tick
                return True
        except (ValueError, KeyError, TypeError) as exc:
            self.commerce.toast(session, str(exc) if isinstance(exc, ValueError) else "That work is no longer available.")
            return True
        return False

    def tick(self, ctx: TickContext) -> None:
        self.salvage.tick()
        self.requests = {sid: rows for sid, rows in self.requests.items() if sid in self.game.sessions.active}
        for pid, channel in tuple(self.channels.items()):
            session = self.game.combat.session(pid)
            actor = self.game.combat.actor(self.game.players[pid]) if pid in self.game.players else None
            if (not session or not channel.valid(actor) or not self.commerce.ready(session)):
                if session:
                    self.stop(session, "Your work is interrupted.")
                else:
                    self.channels.pop(pid, None)
                    if actor:
                        actor.behaviour.pop("channel", None)
                continue
            actor.behaviour["channel"] = {"label": "Harvest" if channel.kind == "harvest" else "Fabricate",
                                          "remaining": max(0, channel.until-ctx.tick)/TICK_HZ}
            self.game.world.zones[channel.zone].revision += 1
            if ctx.tick < channel.until or self.commerce.pending:
                continue
            try:
                if channel.kind == "craft":
                    self.craft(session, channel)
                else:
                    def harvested(ok: bool, label: str, session: Session = session,
                                  channel: PhysicalChannel = channel) -> None:
                        if ok:
                            self.sim.log(session, f"You recover {label}. One unit.")
                        current = self.channels.get(session.player_id)
                        if ok and current is channel and channel.object in self.game.world.zones[channel.zone].objects:
                            channel.until = self.clock.now_tick()+self.salvage.rules.harvest_seconds*TICK_HZ
                        elif current is channel:
                            self.stop(session, "The node is empty." if ok else "The harvest could not be saved. The unit remains.")
                    self.salvage.harvest(self.game.players[pid], channel.zone, channel.object, harvested)
            except (ValueError, KeyError) as exc:
                self.stop(session, str(exc) if isinstance(exc, ValueError) else "That work is no longer available.")
        for sid, (target, cursor, opened) in tuple(self.menus.items()):
            session = self.game.sessions.active.get(sid)
            if not session:
                self.menus.pop(sid, None)
                continue
            try:
                if ctx.tick-opened >= MENU_TIMEOUT_SECONDS*TICK_HZ:
                    raise ValueError("The workshop menu closes.")
                self.sim.external_views[sid] = "menu", self.body(session, target, cursor)
            except (ValueError, KeyError):
                self.close(session)
