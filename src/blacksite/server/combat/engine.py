"""Deterministic combat adapter; persistence is proposed through commerce.

Game design 4, 5.3, 5.4 and 7.3. No I/O or wall-clock reads occur here.
"""

from blacksite.server.interaction import Focus, Interaction, interact, key_action, object_interaction
from collections import deque
from copy import deepcopy
from datetime import datetime, timezone
from math import ceil
from typing import Any
from collections.abc import Callable

from blacksite.content.schema import HymnTemplate, WeaponBlock
from blacksite.server.commerce import Commerce
from blacksite.server.inventory import Inventory
from blacksite.server.items import ItemInstance, make_item
from blacksite.server.loop import TickContext
from blacksite.server.players import Player
from blacksite.server.progression import Grant
from blacksite.server.protocol import Frame
from blacksite.server.rules import character, combat as rules
from blacksite.server.sessions import Session
from blacksite.server.skills import Use
from blacksite.server.quality import value as quality_value, damage_multiplier
from blacksite.server.wake import menu
from blacksite.server.world.actors import Actor
from blacksite.server.views import presentation
from blacksite.server.world.sight import line, sees_actor, visible_tiles, line_of_sight, sight_radius, detection_limit
from blacksite.server.world.sight import private_visible


class Combat:
    def __init__(self, commerce: Commerce) -> None:
        self.commerce, self.game, self.sim = commerce, commerce.game, commerce.sim
        self.world, self.content, self.clock = self.game.world, self.game.content, self.game.clock
        self.warnings: dict[tuple[str, str], int] = {}
        self.casts: dict[str, dict[str, Any]] = {}
        self.menus: dict[str, int] = {}
        self.verbose: set[str] = set()
        self.restored: dict[str, Actor] = {}
        self.pending_deaths: set[str] = set()
        self.refused_hook: Callable[[Actor, Actor], None] = lambda source, target: None
        self.hostile_hook: Callable[[Actor, Actor], None] = lambda source, target: None
        self.npc_death_hook: Callable[[Actor, Actor], None] = lambda source, target: None
        self.npc_armour: Callable[[Actor, str], int] = lambda actor, kind: 0
        self.relation_provider: Callable[[Actor, Actor], str] | None = None
        self.training_provider: Callable[[Player, Actor, int], None] = lambda player, actor, tick: None
        self.allies_provider: Callable[[Actor], list[Actor]] = lambda actor:[actor]  # S22 supplies local crew.
        self.crew_together: Callable[[str, str], bool] = lambda one, other: False
        self.ability_effect: Callable[[Player, HymnTemplate], dict[str, Any]] = lambda player, ability: dict(ability.effect)
        self.sim.target_provider = self.target_view
        self.sim.pvp_provider = self.pvp_eligible
        self.game.combat = self

    def now(self) -> float:
        return self.clock.now_utc().timestamp()

    def pvp_eligible(self, actor: Actor) -> bool:
        """Game 5.1: protection at this body, independent of an opponent."""
        from blacksite.server.rules.character import DISCHARGE_GRADE
        zone = self.world.zones.get(actor.zone)
        player = self.game.players.get(actor.id)
        return bool(zone and zone.allows_hostile(actor.position)
                    and (zone.safety_at(actor.position) == "open"
                         or player and player.grade >= DISCHARGE_GRADE))

    def session(self, pid: str) -> Session | None:
        return next((s for s in self.game.sessions.active.values() if s.player_id == pid and not s.closed), None)

    def actor(self, player: Player) -> Actor | None:
        av = self.sim.avatars.get(player.bbs_user_id)
        return av.actor if av and av.actor.id == player.id else self.world.actors.get(player.id)

    def log(self, actor: Actor, text: str, warning: bool = False) -> None:
        session = self.session(actor.owner if actor.behaviour.get("player_drone") else actor.id)
        if session:
            session.emit(text, kind="danger" if warning else "combat", channel="combat",
                         role="warning" if warning else "chan_sys", at=self.clock.now_utc().isoformat())

    def relation(self, source: Actor, target: Actor) -> str:
        if self.crew_together(source.id, target.id):
            return "allied"
        if self.relation_provider:
            return self.relation_provider(source, target)
        if target.owner == source.id and target.behaviour.get("training"): return "hostile"
        if target.marked: return "hostile"
        faction = self.content.factions.get(source.faction)
        value = faction.relations.get(target.faction,"N") if faction else "N"
        return {"H":"hostile","N":"neutral","A":"allied"}[value]

    def legal(self, source: Actor, target: Actor) -> bool:
        if source.behaviour.get("powered") is False:
            return False
        if initiator_id := source.behaviour.get("interlock_initiator"):
            initiator = self.world.actors.get(initiator_id)
            if not initiator or not self.permits_indirect(initiator, target):
                return False
        if source.stance in ("down","dead","sleeper","jacked") or target.stance in ("down","dead"):
            return False
        if source.id == target.id or source.zone != target.zone or source.zone not in self.world.zones:
            return False
        if self.crew_together(source.id, target.id):
            return False
        # Mission bodies are scoped copies, never somebody else's permanent
        # handler or escort. S22 may supply crew permissions explicitly.
        if target.behaviour.get("mission") and target.behaviour.get('mission_roster') is None and source.kind == "player" and target.owner != source.id and not self.crew_together(source.id, target.owner):
            return False
        if source.behaviour.get("mission") and source.behaviour.get('mission_roster') is None and target.kind == "player" and source.owner != target.id and not self.crew_together(source.owner, target.id):
            return False
        training = source if source.behaviour.get("training") else target if target.behaviour.get("training") else None
        if training:
            return training.owner == (target.id if source is training else source.id)
        return self.permits_indirect(source, target)

    def permits_indirect(self, source: Actor, target: Actor) -> bool:
        """Physical body permission; Lattice separately checks its own range.

        A jacked source can burn a presence, never fire a physical weapon.
        Neither body may use its different zone to bypass safety or grade.
        """
        if source.id == target.id or source.stance in ("down", "dead", "sleeper") or target.stance in ("down", "dead"):
            return False
        if not self.world.permits_harm(source, target): return False
        if source.behaviour.get("player_drone"):
            source = self.game.progression.drones.controller_body(source,acting=True)
            if source is None:
                return False
        if target.behaviour.get("player_drone"):
            target = self.game.progression.drones.controller_body(target,acting=False)
            if target is None:
                return False
        if source.id == target.id or not self.world.permits_harm(source,target):
            return False
        if self.crew_together(source.id, target.id):
            return False
        if target.behaviour.get("mission") and target.behaviour.get('mission_roster') is None and source.kind == "player" and target.owner != source.id and not self.crew_together(source.id, target.owner):
            return False
        if source.behaviour.get("mission") and source.behaviour.get('mission_roster') is None and target.kind == "player" and source.owner != target.id and not self.crew_together(source.owner, target.id):
            return False
        if source.kind == target.kind == "player":
            if any(self.world.zones[a.zone].safety_at(a.position) != "open" for a in (source, target)):
                if min(self.game.players[source.id].grade, self.game.players[target.id].grade) < 5: return False
        return True

    def visible(self, actor: Actor, target: Actor) -> bool:
        if actor.zone != target.zone or actor.zone not in self.world.zones: return False
        if target.behaviour.get("training") and target.owner != actor.id: return False
        zone = self.world.zones[actor.zone]
        hour = self.clock.now_local().hour
        radius = sight_radius(actor, zone, hour >= 20 or hour < 6)
        limit = detection_limit(radius, target)
        if (actor.x-target.x)**2 + (actor.y-target.y)**2 > limit**2:
            return False
        # An NPC asks about one target, not a rendered field of view. Use
        # the same radius/stealth/occlusion rules without tracing 400+ tiles.
        if actor.kind != "player":
            return line_of_sight(zone, actor.position, target.position)
        return sees_actor(actor, target, visible_tiles(actor, zone, radius), radius)

    def select(self, actor: Actor, backwards: bool = False) -> None:
        candidates = sorted((a for a in self.world.zones[actor.zone].actors.values()
            if a is not actor and a.stance not in ("down", "dead") and self.visible(actor, a)),
            key=lambda a:(self.relation(actor,a)!="hostile",rules.distance(actor.position, a.position), a.id))
        ids = [a.id for a in candidates]
        if not ids: actor.target = None
        elif actor.target not in ids: actor.target = ids[-1 if backwards else 0]
        else: actor.target = ids[(ids.index(actor.target) + (-1 if backwards else 1)) % len(ids)]
        self.world.zones[actor.zone].revision += 1

    def cover(self, source: Actor, target: Actor) -> int:
        zone = self.world.zones[target.zone]
        tiles = line(target.position, source.position)[1:2]
        return max((zone.tiles[zone.tile_id(tile)].cover for tile in tiles), default=0)

    def armour(self, actor: Actor, damage_type: str) -> int:
        player = self.game.players.get(actor.id)
        total = self.npc_armour(actor, damage_type) + sum(int(e.get("armour",0)) for e in actor.effects)
        total += int(actor.modifiers.get("arm_"+damage_type[0], 0))
        if player:
            for iid in set(player.equipment.values()):
                item = self.commerce.items.get(iid)
                template = self.content.items[item.template] if item else None
                if template and template.armour:
                    total += int(quality_value(template, item.quality, "armour", damage_type,
                                               getattr(template.armour.armour, damage_type)))
        return total

    def evasion(self, actor: Actor) -> float:
        if actor.stance == "jacked":
            return 0  # Game design 5.2: the body cannot evade while jacked.
        player = self.game.players.get(actor.id)
        if not player: return float(actor.behaviour.get("evasion",0))
        value = min(100, max(0, player.attributes["nerve"]+actor.modifiers.get("nerve", 0))) / 3
        value += actor.modifiers.get("evasion", 0)
        for iid in set(player.equipment.values()):
            item = self.commerce.items.get(iid)
            template = self.content.items[item.template] if item else None
            if template and template.armour: value += template.armour.evasion
        return value

    def target_view(self, actor: Actor) -> dict[str, Any] | None:
        target = self.world.actors.get(actor.target)
        if not target or target.zone != actor.zone or not private_visible(actor, target): return None
        obscured = not self.visible(actor,target)
        if obscured:
            zone = self.world.zones[actor.zone]
            hour = self.clock.now_local().hour
            radius = sight_radius(actor, zone, hour >= 20 or hour < 6)
            if not actor.modifiers.get("target_through_cover") or rules.distance(actor.position, target.position) > radius:
                return None
        hidden = presentation.covered(target, actor, self.content)
        legacy_role = "player_hostile" if target.marked else self.content.factions[target.faction].colour if target.faction in self.content.factions else "text"
        return {"id":target.id, "name":presentation.name(target, actor, self.content), "handle":target.handle,
            "faction": presentation.presented_class(target, actor, self.content).title() if hidden else target.faction or "Freelance",
            "class": presentation.presented_class(target, actor, self.content), "jacked": target.stance == "jacked",
            "name_role": presentation.role(target, actor, self.content, legacy_role),
            "hp_percent":max(0,ceil(100 * target.health / target.health_max)),
            **({"hp": target.health, "hp_max": target.health_max} if actor.modifiers.get("target_through_cover") else {}),
            "range":round(rules.distance(actor.position,target.position),1), "cover":self.cover(actor,target),
            "relation":"neutral" if hidden else self.relation(actor,target), "stance":target.stance,
            "protected":not self.legal(actor,target),
            "warning":"Protected" if not self.legal(actor,target) else "Obscured; no clear shot" if obscured
                else "Firing marks you" if (target.kind == "player" or target.behaviour.get("player_drone")) and self.relation(actor,target) != "hostile" else ""}

    def warn(self, source: Actor, target: Actor, tick: int) -> bool:
        self.reveal(source, target)
        key = source.id, target.id
        private_training = source.behaviour.get("training") or target.behaviour.get("training")
        if key not in self.warnings or (not private_training and tick-self.warnings[key] > rules.ticks(rules.COMBAT_SECONDS)
                and tick>=max(source.cooldowns.get("combat",0),target.cooldowns.get("combat",0))):
            self.warnings[key] = tick
            self.log(source, "You raise your weapon. Fire again after two seconds; the target can move to safety.", True)
            self.log(target, source.name + " raises a weapon at you. Move to cover or safety.", True)
            return False
        return tick >= self.warnings[key] + rules.ticks(rules.WARNING_SECONDS)

    def would_mark(self, source: Actor, target: Actor, indirect: bool = False) -> bool:
        if self.crew_together(source.id, target.id):
            return False
        if source.kind != "player" or target.kind != "player" or self.relation(source, target) == "hostile":
            return False
        bodies = (source, target) if indirect else (source,)
        return not all(self.world.zones[actor.zone].safety_at(actor.position) == "open" for actor in bodies)

    def mark(self, source: Actor, target: Actor) -> None:
        if source.behaviour.get("player_drone") or target.behaviour.get("player_drone"):
            source_body = self.game.progression.drones.controller_body(source,acting=True) if source.behaviour.get("player_drone") else source
            target_body = self.game.progression.drones.controller_body(target,acting=False) if target.behaviour.get("player_drone") else target
            if source_body and target_body:
                self.mark_indirect(source_body,target_body)
            return
        if not self.would_mark(source, target): return
        player = self.game.players[source.id]
        player.marked_until = datetime.fromtimestamp(self.now()+rules.MARKED_SECONDS,timezone.utc).isoformat()
        already_marked = source.marked
        source.marked = True
        if not already_marked: self.log(source,"You are Marked for fifteen minutes.",True)
        self.game.queue("save", player.bbs_user_id, player, immediate=True)

    def mark_indirect(self, source: Actor, target: Actor) -> None:
        """Game 7.3: the remote open exception requires both bodies open."""
        if not self.would_mark(source, target, indirect=True):
            return
        player = self.game.players[source.id]
        player.marked_until = datetime.fromtimestamp(self.now()+rules.MARKED_SECONDS, timezone.utc).isoformat()
        if not source.marked:
            self.log(source, "You are Marked for fifteen minutes.", True)
        source.marked = True
        self.game.queue("save", player.bbs_user_id, player, immediate=True)

    def weapon(self, player: Player) -> tuple[Any, WeaponBlock] | None:
        slots = [player.progress.get("weapon_slot",""), "weapon_main", "weapon_side", "melee"]
        for slot in dict.fromkeys(slots):
            item = self.commerce.items.get(player.equipment.get(slot))
            if item:
                template = self.content.items[item.template]
                if template.weapon: return item, template.weapon
        return None

    def fire(self, pid: str, requested: str | None = None) -> None:
        player = self.game.players.get(pid)
        actor = self.actor(player) if player else None
        if not actor or actor.zone is None or actor.stance in ("down","dead","sleeper","jacked"): return
        tick = self.clock.now_tick()
        if tick < max(actor.cooldowns.get("weapon",0),actor.cooldowns.get("knockdown",0)) or pid in self.casts: return
        target = self.world.actors.get(requested or actor.target)
        if not target or target.stance in ("down","dead") or not self.visible(actor,target):
            self.log(actor,"Select a visible target with Tab."); return
        if not self.legal(actor,target):
            self.log(actor,self.game.crews.text("friendly_fire") if self.crew_together(actor.id, target.id) else "Protected: you cannot harm that body.",True)
            self.refused_hook(actor, target)
            return
        equipped = self.weapon(player)
        if not equipped: self.log(actor,"Equip a weapon first."); return
        item, weapon = equipped
        range_ = 1.5 if weapon.melee else weapon.range
        distance = rules.distance(actor.position,target.position)
        if distance > range_ or not line_of_sight(self.world.zones[actor.zone],actor.position,target.position):
            self.log(actor,"Out of range or line of sight."); return
        targets = self.weapon_targets(actor,target,weapon)
        warned = [self.warn(actor,other,tick) for other in targets]
        if not all(warned): return
        if weapon.melee and actor.stamina < weapon.stamina: self.log(actor,"You need stamina."); return
        items = deepcopy(self.commerce.items)
        inventory = list(player.inventory)
        if weapon.ammo:
            ammo = next((i for i in items.values() if i.id in inventory and i.owner == pid and i.template == weapon.ammo and i.stack>0), None)
            if not ammo: self.log(actor,"Click. No matching ammunition."); return
            ammo.stack -= 1
            if not ammo.stack and self.content.items[ammo.template].ammo.recharge_price is None:
                del items[ammo.id]; inventory.remove(ammo.id)
        elif not weapon.melee and self.content.items[item.template].requires_archetype != player.archetype:
            self.log(actor,"That weapon requires its resonance interface."); return
        jam = max((float(e.get("weapon_multiplier",1)) for e in actor.effects), default=1)
        jam *= actor.modifiers.get("weapon_cooldown_multiplier", 1)
        if weapon.heavy:
            jam *= actor.modifiers.get("heavy_cooldown_multiplier", 1)
        seconds = rules.action_seconds(rules.MELEE_SECONDS if weapon.melee else weapon.cooldown, actor.shock, jam)
        def resolved(success: bool) -> None:
            if not success: self.log(actor,"The shot did not settle. Try again.",True); return
            if actor.stance in ("down","dead","sleeper") or actor.zone is None: return
            actor.cooldowns["weapon"] = rules.cooldown_deadline(self.clock.now_tick(), seconds,
                                                               actor.cooldowns.get("weapon", 0))
            actor.stance = "normal"
            if weapon.melee: actor.stamina -= weapon.stamina
            # The queue can outlive an input frame. Recheck physical safety at impact.
            if not self.legal(actor,target) or not self.visible(actor,target): return
            for other in targets:
                if not self.legal(actor,other) or not self.visible(actor,other): continue
                self.mark(actor,other)
                for _ in range(weapon.hits): self.shot(actor,other,weapon,damage_multiplier(self.content.items[item.template],item.quality),player.skills.get("melee" if weapon.melee else "energy" if weapon.damage_type == "energy" else "kinetic",0))
            self.remember(player,actor)
        self.commerce.settle(player,{"inventory":inventory,
            "equipment":{s:i for s,i in player.equipment.items() if i in inventory}},items,self.commerce.caches,self.commerce.serial,resolved)

    def weapon_targets(self, source: Actor, target: Actor, weapon: WeaponBlock) -> list[Actor]:
        if weapon.targets <= 1 and not weapon.cone: return [target]
        candidates = []
        aim = target.x-source.x,target.y-source.y
        for other in self.world.zones[source.zone].actors.values():
            if other is source or other is target or other.stance in ("down","dead"): continue
            if not self.legal(source,other) or not self.visible(source,other): continue
            if weapon.cone:
                ray = other.x-source.x,other.y-source.y
                dot = aim[0]*ray[0]+aim[1]*ray[1]
                cross = abs(aim[0]*ray[1]-aim[1]*ray[0])
                if rules.distance(source.position,other.position)>weapon.cone or dot<=0 or cross>dot: continue
            elif rules.distance(target.position,other.position)>2 or rules.distance(source.position,other.position)>weapon.range: continue
            candidates.append(other)
        candidates.sort(key=lambda a:(rules.distance(target.position,a.position),a.id))
        return [target,*candidates] if weapon.cone else [target,*candidates[:weapon.targets-1]]

    def shot(self, source: Actor, target: Actor, weapon: WeaponBlock, quality: float = 1, skill: float = 0) -> None:
        if self.commerce.pending:
            try:
                self.commerce.enqueue_system(lambda: self.shot(source, target, weapon, quality, skill))
            except ValueError:
                return  # Match hurt: overload declines harm instead of aborting the tick.
            return
        if (not self.legal(source,target) or target.stance in ("down","dead") or not self.visible(source,target)
                or rules.distance(source.position,target.position) > (weapon.range or 1.5)):
            return
        self.reveal(source, target)
        if source.behaviour.get("interlock_initiator"):
            initiator = self.world.actors[source.behaviour["interlock_initiator"]]
            self.mark_indirect(initiator, target)  # A committed remote miss still marks.
        zone = self.world.zones[source.zone]
        accuracy = (weapon.accuracy if weapon.accuracy is not None else rules.MELEE_ACCURACY)+source.modifiers.get("accuracy", 0)
        if weapon.damage_type == "kinetic": accuracy += source.modifiers.get("kinetic_accuracy", 0)
        penalty = 0 if weapon.melee else rules.range_penalty(rules.distance(source.position,target.position),weapon.range)
        penalty *= source.modifiers.get("range_penalty_multiplier", 1)
        chance = rules.to_hit(accuracy,skill,self.evasion(target),self.cover(source,target),penalty)
        roll = zone.rng.random()*100
        self.exchange(source,target)
        hit = roll < chance
        self.log(source,f"{'Hit' if hit else 'Miss'}: {target.name}." + (f" Roll {roll:.1f}, hit {chance:.1f}%, cover {self.cover(source,target)}." if source.id in self.verbose else ""))
        if not hit: return
        amount = rules.damage(weapon.damage*quality,skill,self.armour(target,weapon.damage_type),weapon.melee)
        progression = self.game.progression
        attack_use = progression.combat_eligible(source, target)
        armour_use = progression.combat_eligible(target, source) and amount < rules.damage(weapon.damage*quality,skill,0,weapon.melee)
        before = target.health
        self.hurt(source,target,amount,weapon.shock,damage_type=weapon.damage_type)
        if target.health < before:
            receipt = f"hit:{source.id}:{target.id}:{self.clock.now_utc().isoformat()}:{target.behaviour['hit_serial']}"
            if attack_use:
                player = progression.controller(source)
                if source.behaviour.get("player_drone"):
                    progression.record_use(player.id, Use("drone_command","drones",receipt,True,changed=True,threat=True))
                else:
                    line = "melee" if weapon.melee else "energy" if weapon.damage_type == "energy" else "kinetic"
                    progression.record_use(player.id, Use("melee_hit" if weapon.melee else "weapon_hit",
                        line, receipt, True, threat=True))
            if armour_use:
                progression.record_use(progression.controller(target).id,
                    Use("armour_absorb", "armour", "armour:"+receipt, True, threat=True))
        if weapon.dot and target.stance not in ("down","dead"):
            # Reapplying the same agent refreshes, rather than stacking an unbounded DoT.
            target.effects[:] = [e for e in target.effects if not (e.get("kind")=="dot" and e.get("source")==source.id and e.get("damage_type")==weapon.damage_type)]
            target.effects.append({"kind":"dot", "source":source.id, "damage_type":weapon.damage_type,
                "damage":weapon.dot.per_second, "until_tick":self.clock.now_tick()+rules.ticks(weapon.dot.seconds),
                "next_tick":self.clock.now_tick()+10})

    def exchange(self, source: Actor, target: Actor) -> None:
        if source.behaviour.get("training") or target.behaviour.get("training"): return
        self.hostile_hook(source, target)
        target.behaviour["last_attacker"] = source.id
        target.cooldowns["attacked"] = self.clock.now_tick()+rules.ticks(rules.COMBAT_SECONDS)
        for actor, opponent in ((source, target), (target, source)):
            self.game.progression.hostile_contact(actor, opponent)
        tick = self.clock.now_tick()
        for actor in (source,target):
            actor.cooldowns["combat"] = tick + rules.ticks(rules.COMBAT_SECONDS)
            player = self.game.progression.controller(actor)
            if player:
                body = self.actor(player)
                player.progress["last_exchange"] = self.now()
                if body:
                    body.cooldowns["combat"] = actor.cooldowns["combat"]
                    if body.stance == "sleeper": player.progress["sleeper_combat"] = True
                    if body is not actor:
                        self.remember(player,body,immediate=False)

    def hurt(self, source: Actor, target: Actor, amount: int, shock: float = 0, *, damage_type: str = "") -> None:
        if target.stance in ("down", "dead"):
            return
        if self.commerce.pending:
            try: self.commerce.enqueue_system(lambda:self.hurt(source,target,amount,shock,damage_type=damage_type))
            except ValueError: self.log(source,"The city is busy. Try again.",True)
            return
        if not self.legal(source,target) or target.stance in ("down","dead"): return
        self.reveal(source, target)
        training = source.behaviour.get("training")
        self._apply_damage(source, target, amount, shock, source.id, source.name, bool(training), damage_type)

    def reveal(self, source: Actor, target: Actor) -> None:
        if source.reveal_against(target) and source.zone in self.world.zones:
            self.world.zones[source.zone].revision += 1

    def feedback_hurt(self, target: Actor, amount: int, source_id: str, source_name: str,
                      permit: Callable[[], bool]) -> bool:
        """Server-owned NPC feedback, using the ordinary hit/down pipeline.

        The encounter supplies a run-scoped authority check, including
        current body safety. The caller defers the complete integrity/body
        hit while a transfer is pending. No frame supplies this callback.
        """
        if target.id not in self.game.players or target.stance in ("down", "dead"):
            return False
        if self.commerce.pending:
            return False
        if not permit():
            return False
        self._apply_damage(None, target, amount, 0, source_id, source_name, False)
        return True

    def _apply_damage(self, source: Actor | None, target: Actor, amount: int, shock: float,
                      source_id: str, source_name: str, training: bool, damage_type: str = "") -> None:
        responsible = self.world.actors.get(source.behaviour.get("interlock_initiator"), source) if source else None
        target.health = max(1 if training else 0,target.health-amount)
        target.shock = min(100,target.shock+amount/2+shock)
        target.cooldowns["last_hit"] = self.clock.now_tick()
        target.behaviour["hit_serial"] = int(target.behaviour.get("hit_serial",0))+1
        self.log(target,f"{source_name} hits you for {amount}.",True)
        self.casts.pop(target.id,None)
        if target.shock >= rules.SHOCK_KNOCK:
            if damage_type == "dissonance" and target.modifiers.get("dissonance_knockdown_immune"):
                target.shock = rules.SHOCK_KNOCK-1
            else:
                target.shock = rules.SHOCK_RESET
                target.cooldowns["knockdown"] = self.clock.now_tick()+rules.ticks(rules.KNOCK_SECONDS)
        if target.health <= 0:
            if target.behaviour.get("training"):
                self.world.leave(target)
                player = self.game.players.get(target.owner)
                if player and source is not None:
                    player.progress["wake_combat"] = "done"
                    self.log(source,"The training drone falls silent. The tutorial terminal is ahead.")
                    self.remember(player,source)
            elif target.id in self.game.players:
                target.stance = "down"
                target.effects.clear()
                controller = self.game.progression.controller(responsible) if responsible is not None else None
                self.game.players[target.id].progress["combat"] = {"stage":"down", "until":self.now()+rules.DOWN_SECONDS,
                    "killer":controller.id if controller else source_id}
                self.log(target,"You are down. A nearby ally can press E to pick you up.",True)
            else:
                if source is not None:
                    self.npc_death_hook(responsible, target)
        if target.id in self.game.players:
            self.remember(self.game.players[target.id],target,immediate=target.health <= 0)
        if target.zone: self.world.zones[target.zone].revision += 1

    def remember(self, player: Player, actor: Actor, immediate: bool = True) -> None:
        player.health,player.stamina,player.shock = actor.health,actor.stamina,actor.shock
        if "last_hit" in actor.cooldowns:
            player.progress["last_hit_at"] = self.now()-(self.clock.now_tick()-actor.cooldowns["last_hit"])/10
        player.progress["combat_effects"] = [{**deepcopy(e), "until":self.now()+max(0,e["until_tick"]-self.clock.now_tick())/10,
            **({"next":self.now()+max(0,e["next_tick"]-self.clock.now_tick())/10} if "next_tick" in e else {})}
            for e in actor.effects if "until_tick" in e]
        player.progress["combat_cooldowns"] = {k:self.now()+max(0,v-self.clock.now_tick())/10 for k,v in actor.cooldowns.items()
            if k in ("weapon","knockdown") or k.startswith("ability:")}
        # Architecture 6.2: ordinary HP/shock writes use the five-second
        # player checkpoint. Death, spent goods and action cooldowns remain
        # immediate. A nonfatal NPC hit must not fsync the whole street.
        self.game.queue("save",player.bbs_user_id,player,immediate=immediate)

    def next_serial(self) -> int:
        return max(self.commerce.serial,max((int(i.rsplit(":",1)[-1]) for i in self.commerce.items),default=0))

    def die(self, player: Player, actor: Actor) -> None:
        if player.id in self.pending_deaths or self.commerce.pending: return
        progress = deepcopy(player.progress)
        state = progress["combat"]
        state.update(stage="dead",until=self.now()+rules.DECANT_SECONDS)
        inventory,equipment,items,caches = list(player.inventory),dict(player.equipment),deepcopy(self.commerce.items),deepcopy(self.commerce.caches)
        serial = self.next_serial()+1
        zone = self.world.zones[player.zone]
        if zone.allows_hostile(player.tile):
            dropped = [iid for iid in inventory if not items[iid].secured and not items[iid].bound
                and iid not in player.implants.values() and not items[iid].template.startswith("story_")]
            if dropped:
                cid = f"{player.origin}:cache:{serial}"
                caches[cid] = {"zone":player.zone,"tile":list(player.tile),"items":dropped,"expires":self.now()+rules.CACHE_SECONDS,
                    "victim":player.id,"killer":state.get("killer"),"private_until":self.now()+rules.LOOT_PRIVATE_SECONDS}
                for iid in dropped: items[iid].owner = cid; inventory.remove(iid)
                equipment = {s:i for s,i in equipment.items() if i not in dropped}
        hand,debt,xp,charge = rules.clone_settlement(player.chits_hand,player.grade,player.xp,character.grade_threshold(player.grade),player.clone_debt)
        state["charge"] = charge
        identity = deepcopy(self.game.identities[player.bbs_user_id]); identity["clone_debt"] = debt
        progression = self.game.progression
        killer = self.game.players.get(state.get("killer"))
        reward, killer_patch, killer_identity = None, {}, None
        grant = None
        before_standing = deepcopy(killer.standing) if killer else {}
        if (killer and killer.id not in self.game.deleting and killer.id != player.id
                and killer.bbs_user_id != player.bbs_user_id
                and progression.permit_combat(killer.id, player.id)):
            crew = progression.crew_of(killer.id)
            receipt = f"pvp:{player.id}:{state['until']}"
            grant = Grant("combat", receipt,
                True, scope="pvp:"+player.bbs_user_id, opponent_grade=player.grade,
                opponent_identity=player.bbs_user_id,
                self_or_crew=bool(crew and crew == progression.crew_of(player.id)))
            killer_patch, killer_identity, reward = progression.reward_patch(killer, grant)
            from blacksite.server.factions import player_kill
            changes = player_kill(killer, player, self.content.factions, killer_identity, self.clock.now_utc())
            killer_patch.update(self.game.factions.standing_patch(killer, changes, "explicit"))
        self.pending_deaths.add(player.id)
        def committed(success: bool) -> None:
            self.pending_deaths.discard(player.id)
            if not success: return
            if killer:
                progression.notify_reward(killer, reward)
                self.game.factions.notify_standing(killer, before_standing, "player kill")
            actor.stance = "dead"; actor.target = None
            if actor.zone:
                self.world.zones[actor.zone].deactivate("sleeper:"+actor.id,self.clock.now_tick())
                session = self.session(player.id)
                if session: self.world.zones[actor.zone].deactivate(session.id,self.clock.now_tick())
            self.world.leave(actor)
            self.game.sleepers.pop(player.id,None)
            self.log(actor,f"Clone charge {charge}. Hand remaining {hand}; owed {debt}.")
            session = self.session(player.id)
            if session:
                self.commerce.close(session)
                self.game.screens.pop(session.id,None)
                self.menus.pop(session.id,None)
        self.commerce.settle(player,{"inventory":inventory,"equipment":equipment,"progress":progress,
            "health":0,"chits_hand":hand,"clone_debt":debt,"xp":xp},items,caches,serial,committed,identity)
        if killer_patch or (killer_identity is not None and killer_identity != self.game.identities[killer.bbs_user_id]):
            if "progress" in killer_patch:
                killer_patch["progress"] = {key: value for key, value in killer_patch["progress"].items()
                    if key not in killer.progress or value != killer.progress[key]}
            self.commerce.outbox[-1]["player_patches"] = {killer.id: killer_patch}
            self.commerce.outbox[-1]["identities"] = {killer.bbs_user_id: killer_identity}
        if grant and hasattr(self.game, 'crews'):
            self.game.crews.add_rewards(self.commerce.outbox[-1], killer, grant)
        if killer and hasattr(self.game, 'crews'):
            for cid in set(caches)-set(self.commerce.caches):
                self.game.crews.stage_cache(self.commerce.outbox[-1], cid, killer.id)
        market = getattr(self.game, 'market', None)
        if market:
            market.stage_death(self.commerce.outbox[-1], player, killer)

    faction_vat: Callable[[Player], tuple[str, tuple[int, int]] | None] = staticmethod(lambda player: None)

    def vat(self, player: Player) -> tuple[str, tuple[int,int]]:
        faction = self.faction_vat(player)
        if faction:
            return faction
        pending,seen = deque([player.zone]),set()
        while pending:
            zid = pending.popleft()
            if zid in seen or zid not in self.world.zones: continue
            seen.add(zid); zone = self.world.zones[zid]
            vats = [o.spec.tile for o in zone.objects.values() if o.spec.kind == "vat"]
            if vats: return zid,self.world.free_tile(zid,vats[0])
            pending.extend(ex.target_zone for ex in zone.template.meta.exits if not ex.hidden)
        zid = "vatside-wake-hall"
        return zid,self.world.free_tile(zid,self.world.zones[zid].template.meta.spawn)

    def recovery_items(self, player: Player) -> tuple[Player,dict[str,ItemInstance],int]:
        draft,items = deepcopy(player),deepcopy(self.commerce.items)
        serial = self.next_serial()
        inv = Inventory(items,self.content.items,self.game.progression.modifiers(draft).secured_slots)
        usable = False
        body_gear = False
        for iid in player.inventory:
            if iid in items:
                template = self.content.items[items[iid].template]
                if not (template.weapon or template.armour): continue
                try: inv.slots(draft,iid)
                except ValueError: continue
                if template.armour and template.armour.slot=="body": body_gear = True
                weapon = template.weapon
                if weapon and (weapon.melee or not weapon.ammo or any(items[i].template==weapon.ammo and items[i].stack>0 for i in player.inventory)):
                    usable = True
        if not usable or not body_gear or player.recovery_kit_id:
            draft.recovery_kit_id = player.recovery_kit_id or player.id+":loan"
            for tid,quantity in self.content.starts[player.archetype].recovery_items.items():
                missing = quantity-sum(items[i].stack for i in draft.inventory if items[i].template == tid)
                while missing > 0:
                    count = min(missing,self.content.items[tid].stack_max)
                    serial += 1
                    item = make_item(f"{player.origin}:item:{serial}",self.content.items[tid],player.id,self.clock.now_utc().isoformat(),count)
                    item.bound = True
                    item.secured = False  # Bound recovery needs no free secured slot.
                    inv.add(draft,item); missing -= count
            for slot,tid in (("weapon_side","wpn_kestrel_sidearm"),("body","arm_wake_coverall"),("quick1","con_sablier_patch")):
                if slot not in draft.equipment and not (slot=="quick1" and draft.progress.get("quick_abilities",{}).get("1")):
                    iid = next((i for i in draft.inventory if items[i].template == tid),None)
                    if iid: draft.equipment[slot] = iid
        return draft,items,serial

    def respawn(self, player: Player, actor: Actor) -> None:
        if player.id in self.pending_deaths or self.commerce.pending: return
        zid,tile = self.vat(player)
        draft,items,serial = self.recovery_items(player)
        progress = deepcopy(draft.progress)
        progress.pop("faction_vat", None)
        progress.pop("combat",None); progress.pop("offline_at",None)
        progress.pop("combat_effects",None); progress.pop("combat_cooldowns",None)
        self.pending_deaths.add(player.id)
        def committed(success: bool) -> None:
            self.pending_deaths.discard(player.id)
            if not success: return
            actor.health,actor.stamina,actor.shock = player.health,player.stamina,0
            actor.stance = "normal"; actor.effects.clear(); actor.cooldowns.clear()
            session = self.session(player.id)
            if session:
                self.world.enter(actor,zid,self.world.free_tile(zid,tile))
                av = self.sim.avatars[session.user_id]; av.zone = session.subscribed = zid
                self.world.zones[zid].activate(session.id,self.clock.now_tick())
                self.sim.external_views.pop(session.id,None)
                self.sim.reset_view(session,av)
                self.log(actor,"You wake in the vat. Missing recovery supplies are bound to you.")
        self.commerce.settle(player,{"zone":zid,"tile":tile,"inventory":draft.inventory,"equipment":draft.equipment,
            "recovery_kit_id":draft.recovery_kit_id,"progress":progress,"health":actor.health_max,"stamina":actor.stamina_max,"shock":0},
            items,self.commerce.caches,serial,committed)

    def recover_at_vat(self, pid: str, target: str) -> None:
        player = self.game.players.get(pid)
        actor = self.actor(player) if player else None
        if not actor or actor.zone is None or actor.stance in ("down","dead","sleeper"): return
        obj = self.world.zones[actor.zone].objects.get(target)
        if not obj or obj.spec.kind!="vat" or max(abs(actor.x-obj.spec.tile[0]),abs(actor.y-obj.spec.tile[1]))>1:
            self.log(actor,"Move next to a public vat for recovery supplies."); return
        draft,items,serial = self.recovery_items(player)
        if draft.inventory==player.inventory:
            self.log(actor,"You already carry usable recovery supplies."); return
        def committed(success: bool) -> None:
            if success:
                actor.overweight = Inventory(self.commerce.items,self.content.items).weight(player)>player.attributes["frame"]/2
                self.log(actor,"Missing recovery supplies settle. They are bound to you.")
            else: self.log(actor,"The recovery supplies did not settle. Try again.",True)
        self.commerce.settle(player,{"inventory":draft.inventory,"equipment":draft.equipment,"recovery_kit_id":draft.recovery_kit_id},
            items,self.commerce.caches,serial,committed)

    def can_pickup(self, source: Actor, target: Actor) -> bool:
        player = self.game.players.get(target.id)
        if not player or target.stance != "down" or source.stance in ("down","dead","sleeper"): return False
        if source.zone != target.zone or rules.distance(source.position,target.position)>1.5: return False
        if not self.crew_together(source.id, target.id): return False
        if player.progress.get('combat', {}).get('until', float('inf')) <= self.now(): return False
        return not (self.relation(source,target)=="hostile" or self.relation(target,source)=="hostile"
                    or player.progress["combat"].get("killer")==source.id)

    def pickup(self, source: Actor, target: Actor) -> bool:
        if not self.can_pickup(source, target):
            return False
        player = self.game.players[target.id]
        target.health = max(1,ceil(target.health_max*rules.REVIVE_FRACTION)); target.stance = "normal"
        player.progress.pop("combat",None)
        self.remember(player,target); self.log(target,source.name+" picks you up.")
        self.world.zones[target.zone].revision += 1
        return True

    def unlocked(self, player: Player, ability: HymnTemplate) -> bool:
        mods = self.game.progression.modifiers(player)
        tier = mods.bonus("hymn_tier" if ability.kind == "hymn" else "dissonance_tier")
        return player.archetype == "cantor" and tier >= ability.tier and (not ability.requires_one_of
            or bool(mods.installed_templates.intersection(ability.requires_one_of)))

    def cast(self, player: Player, actor: Actor, aid: str) -> None:
        ability = self.content.hymns.get(aid)
        tick = self.clock.now_tick()
        if not ability or not self.unlocked(player,ability): raise ValueError("That ability requires a resonance implant.")
        if any(e.get("hush") for e in actor.effects): raise ValueError("You cannot speak a hymn yet.")
        if player.id in self.casts or tick < max(actor.cooldowns.get("ability:"+aid,0),actor.cooldowns.get("knockdown",0)): return
        target = self.world.actors.get(actor.target) if ability.kind == "dissonance" else actor
        if ability.kind == "dissonance":
            if not target or not self.visible(actor,target): raise ValueError("Choose an unprotected visible target.")
            if not self.legal(actor,target):
                self.refused_hook(actor, target)
                raise ValueError("Choose an unprotected visible target.")
            if rules.distance(actor.position,target.position)>rules.ABILITY_RANGE: raise ValueError("Out of ability range.")
            if not self.warn(actor,target,tick): return
            self.mark(actor,target)
        self.casts[player.id] = {"ability":aid,"until":tick+rules.ticks(rules.action_seconds(ability.cast_seconds*actor.modifiers.get("cantor_cast_multiplier", 1),actor.shock)),
            "tile":actor.position,"zone":actor.zone,"target":target.id,"last_hit":actor.cooldowns.get("last_hit")}
        self.log(actor,"You begin "+ability.name+".")

    def complete_cast(self, actor: Actor, cast: dict[str,Any]) -> None:
        if self.commerce.pending:
            try: self.commerce.enqueue_system(lambda:self.complete_cast(actor,cast))
            except ValueError: self.log(actor,"The city is busy. Try again.",True)
            return
        if actor.stance in ("down","dead","sleeper") or actor.zone is None: return
        ability = self.content.hymns[cast["ability"]]
        target = self.world.actors.get(cast["target"])
        if not target or actor.zone != target.zone: return
        if ability.kind == "dissonance" and (not self.legal(actor,target) or not self.visible(actor,target) or rules.distance(actor.position,target.position)>rules.ABILITY_RANGE): return
        player = self.game.players[actor.id]
        factor = 1+player.skills.get("hymns" if ability.kind == "hymn" else "dissonance",0)/200
        receipt = f"ability:{actor.id}:{ability.id}:{cast.get('until', self.clock.now_tick())}:{self.clock.now_utc().isoformat()}"
        restored = threatened = False
        effect = self.ability_effect(player, ability)
        recipients = [target]
        if ability.kind == "hymn":
            recipients = [a for a in self.allies_provider(actor) if a.zone==actor.zone
                and rules.distance(actor.position,a.position)<=max(rules.ABILITY_RANGE, actor.modifiers.get("hymn_radius", 0))
                    +actor.modifiers.get('hymn_radius_bonus', 0)]
        if effect.get("revive"):
            recipients = [a for a in recipients if a.stance=="down"][:1]
            if not recipients:
                self.log(actor,"No downed crew member is in range."); return
        if effect.get("area"):
            recipients = [a for a in self.world.zones[actor.zone].actors.values() if a is not actor
                and rules.distance(actor.position,a.position)<=effect["area"] and self.visible(actor,a) and self.legal(actor,a)]
        for other in recipients:
            before_health, before_shock = other.health, other.shock
            if ability.kind == "dissonance":
                threatened |= self.game.progression.combat_eligible(actor, other)
            if effect.get("revive"):
                other.health=max(1,ceil(other.health_max*rules.REVIVE_FRACTION));other.stance="normal"
                self.game.players[other.id].progress.pop("combat",None)
            if ability.kind == "dissonance": self.exchange(actor,other)
            if effect.get("damage"):
                self.hurt(actor,other,rules.damage(effect["damage"]*actor.modifiers.get("dissonance_damage_multiplier", 1),
                    player.skills.get("dissonance",0),self.armour(other,"dissonance")),float(effect.get("shock",0)),damage_type="dissonance")
            elif effect.get("shock"):
                other.shock = max(0,other.shock+effect["shock"]*factor)
            ongoing = {key:value for key,value in effect.items() if key not in ("damage","shock","area","seconds","revive")}
            if ongoing:
                other.effects.append({"kind":ability.id,"source":actor.id,"until_tick":self.clock.now_tick()+rules.ticks(float(effect.get("seconds",0))),
                    "next_tick":self.clock.now_tick()+10,**ongoing,"scale":factor,"use_receipt":receipt})
            restored |= other.health > before_health or other.shock < before_shock
            if other.id in self.game.players: self.remember(self.game.players[other.id],other)
        actor.cooldowns["ability:"+ability.id] = self.clock.now_tick()+rules.ticks(ability.cooldown_seconds)
        self.log(actor,ability.name+" settles.")
        self.remember(player,actor)
        self.world.zones[actor.zone].revision += 1
        if ability.kind == "hymn" and restored:
            self.game.progression.record_use(player.id, Use("hymn_restore", "hymns", receipt, True, changed=True))
        elif ability.kind == "dissonance" and threatened:
            self.game.progression.record_use(player.id, Use("dissonance_threat", "dissonance", receipt, True, threat=True))

    def interaction(self, session: Session, frame: Frame) -> Interaction | None:
        player = self.game.players.get(session.player_id)
        actor = self.actor(player) if player else None
        if not actor or session.pending_prompts.get('chat'):
            return None
        if player.progress.get('combat', {}).get('stage') in ('down', 'dead'):
            return Interaction()
        if actor.zone is None:
            return None
        if session.id in self.menus:
            return Interaction()
        if (session.id in self.game.screens or session.id in self.sim.maps
                or session.id in self.commerce.menus or session.id in self.commerce.prompts):
            return None
        if interact(frame) or key_action(self.sim.keymap, session, frame) == 'interact':
            for other in self.world.zones[actor.zone].actors.values():
                if other is not actor and self.can_pickup(actor, other):
                    return Interaction(Focus(other.id, presentation.name(other, actor, self.content), 'pick up'),
                                       other, other.position, other.id)
            vat = next((o for o in self.world.zones[actor.zone].objects.values() if o.spec.kind == 'vat'
                and max(abs(actor.x-o.spec.tile[0]), abs(actor.y-o.spec.tile[1])) <= 1), None)
            if vat:
                return object_interaction(vat, 'use')
        return None

    def input(self, session: Session, frame: Frame, tick: int, *, interaction: Interaction | None = None) -> bool:
        player = self.game.players.get(session.player_id)
        actor = self.actor(player) if player else None
        if not actor: return False
        name = frame.data.get("name","") if frame.type == "intent" else ""
        key = frame.data.get("k","") if frame.type == "key" else ""
        args = frame.data.get("args",{})
        if session.pending_prompts.get("chat"): return False
        table = next((m for m in self.sim.keymap.get("keymaps",[]) if m["id"]==session.keymap_id),{})
        action = next((a for a,keys in table.get("bindings",{}).items() if key in keys),name)
        if player.progress.get("combat",{}).get("stage") in ("down","dead"):
            return not (action in ("say","shout","whisper","emote","log") or name.startswith("chat.") or frame.type == "line" or name == "resync")
        if actor.zone is None: return False
        if tick < actor.cooldowns.get("knockdown",0) and (action == "fire" or action.startswith(("move","sprint"))): return True
        try:
            if name == "inv.use" and any(e.get("hush") for e in actor.effects): raise ValueError("You cannot use consumables yet.")
            if session.id in self.menus:
                if name == "menu_close": self.close_menu(session)
                elif name == "menu_cursor": self.menus[session.id] = max(0,min(len(self.content.hymns)-1,self.menus[session.id]+int(args.get("delta",0))))
                elif name == "menu_select" and frame.data.get("expected_revision") == session.view_revision:
                    aid = args.get("row")
                    if aid not in self.content.hymns or not self.unlocked(player,self.content.hymns[aid]): raise ValueError("That ability is locked.")
                    hotkey = args.get("key","")
                    if hotkey in tuple("12345"):
                        player.progress.setdefault("quick_abilities",{})[hotkey] = aid
                        player.equipment.pop("quick"+hotkey,None)
                        self.remember(player,actor); self.log(actor,"Ability bound to "+hotkey+".")
                    else:
                        self.close_menu(session); self.cast(player,actor,aid)
                return True
            if session.id in self.game.screens or session.id in self.sim.maps or session.id in self.commerce.menus or session.id in self.commerce.prompts: return False
            if action in ("target_next","target_prev"): self.select(actor,action == "target_prev"); return True
            if action == "target_clear": actor.target = None; self.world.zones[actor.zone].revision += 1; return True
            if action == "fire":
                target = args.get("target")
                if target is not None and not isinstance(target,str): raise ValueError("Choose a target.")
                self.commerce.enqueue_system(lambda:self.fire(player.id,target)); return True
            if name == "combat_log_verbose":
                if actor.id in self.verbose: self.verbose.remove(actor.id)
                else: self.verbose.add(actor.id)
                self.log(actor,"Verbose combat log "+("on." if actor.id in self.verbose else "off.")); return True
            if action == "abilities" or name == "abilities": self.menus[session.id] = 0; return True
            if name == "ability": self.cast(player,actor,args.get("id","")); return True
            if name == "loot_take":
                cid = args.get("target") or next((key for key,cache in self.commerce.caches.items()
                    if cache["zone"]==actor.zone and rules.distance(actor.position,tuple(cache["tile"]))<=1.5),"")
                self.commerce.propose(session,"inv.pickup",{"target":cid,"item":args.get("item","")}); return True
            if action.startswith(("use_slot_","quick_")) or name == "use_slot" or key in tuple("12345"):
                slot = str(args.get("slot",action.rsplit("_",1)[-1] if action.startswith("use_slot_") else key))
                if slot not in tuple("12345"): raise ValueError("Choose slot 1-5.")
                aid = player.progress.get("quick_abilities",{}).get(slot)
                if aid: self.cast(player,actor,aid)
                else:
                    if any(e.get("hush") for e in actor.effects): raise ValueError("You cannot use consumables yet.")
                    iid = player.equipment.get("quick"+slot)
                    if not iid and slot == "1": iid = next((i for i in player.inventory if self.commerce.items[i].template == "con_sablier_patch"),None)
                    if iid: self.commerce.propose(session,"inv.use",{"item":iid})
                return True
            if action == "weapon_cycle" or name == "weapon_select":
                slots = [s for s in ("weapon_main","weapon_side","melee") if s in player.equipment]
                current = player.progress.get("weapon_slot",slots[0] if slots else "")
                selected = args.get("slot") or (slots[(slots.index(current)+1)%len(slots)] if current in slots else slots[0] if slots else "")
                if selected not in slots: raise ValueError("Equip a weapon in that slot.")
                player.progress["weapon_slot"] = selected; self.remember(player,actor); self.world.zones[actor.zone].revision += 1; return True
            if name == "stance" or action == "stealth":
                if player.archetype != "ghost": raise ValueError("Stealth stance requires Ghost.")
                actor.stance = "normal" if actor.stance == "stealth" else "stealth"
                self.world.zones[actor.zone].revision += 1; return True
            if action == "interact" or key in ("e","E") or name == "pickup":
                # pickup is also a typed intent; its selection is the E query.
                choice = interaction or self.interaction(session, Frame('intent', {'name': 'interact'}))
                if choice:
                    if choice.actor_id:
                        self.pickup(actor, choice.value)
                    else:
                        vat = choice.value
                        self.commerce.enqueue_system(lambda:self.recover_at_vat(player.id,vat.spec.id))
                    return True
            if name == "recovery":
                self.commerce.enqueue_system(lambda:self.recover_at_vat(player.id,str(args.get("target","")))); return True
            if key in ("b","B") and any(a.owner == actor.id and a.behaviour.get("training") for a in self.world.actors.values()):
                player.progress["wake_combat"] = "skipped"; self.remember(player,actor)
                for drone in tuple(self.world.actors.values()):
                    if drone.owner == actor.id and drone.behaviour.get("training"): self.world.leave(drone)
                return True
        except (ValueError,KeyError,TypeError) as exc:
            self.log(actor,str(exc) if isinstance(exc,ValueError) else "That combat action is unavailable.",True)
            return True
        return False

    def close_menu(self, session: Session) -> None:
        self.menus.pop(session.id,None)
        self.sim.external_views.pop(session.id,None)
        self.sim.reset_view(session,self.sim.avatars[session.user_id])

    def tick(self, ctx: TickContext) -> None:
        tick,now = ctx.tick,self.now()
        for drone in tuple(self.world.actors.values()):
            if drone.behaviour.get("training") and (drone.owner not in self.game.players or self.session(drone.owner) is None):
                self.world.leave(drone)
        for player in tuple(self.game.players.values()):
            actor = self.actor(player)
            state = player.progress.get("combat",{})
            if actor is None and state:
                actor = player.actor(); actor.stance = state["stage"]
                if actor.stance == "down": self.world.enter(actor,player.zone,self.world.free_tile(player.zone,player.tile))
            if actor is None: continue
            self.restore(player,actor)
            was_marked = actor.marked
            actor.marked = bool(player.marked_until and datetime.fromisoformat(player.marked_until).timestamp()>now)
            expired = False
            if player.marked_until and not actor.marked:
                player.marked_until = None
                expired = True
                if was_marked:
                    self.log(actor, "Your Mark ends.")
            if player.warden_heat_until and datetime.fromisoformat(player.warden_heat_until).timestamp() <= now:
                player.warden_heat_until = None
                expired = True
                self.log(actor, "Warden heat ends.")
            if expired:
                self.game.queue("save", player.bbs_user_id, player, immediate=True)
            if state:
                actor.stance = state["stage"]
                if actor.stance == "down" and state["until"] <= now: self.die(player,actor)
                elif actor.stance == "dead":
                    if actor.zone: self.world.leave(actor)
                    if state["until"] <= now: self.respawn(player,actor)
                session = self.session(player.id)
                if session:
                    self.game.screens.pop(session.id,None)
                    self.commerce.menus.pop(session.id,None)
                    self.sim.external_views[session.id] = "dead",{"title":"DOWN" if state["stage"]=="down" else "SABLIER DECANT",
                        "seconds_left":max(0,ceil(state["until"]-now)),"lines":[f"{max(0,ceil(state['until']-now))} seconds.",
                            *self.content.text["dead-screen"].body.splitlines(),f"Clone charge {state.get('charge',0)}. Debt owed {player.clone_debt}."],"hint":"Your log remains below. Ctrl-X leaves; the timer continues.","clear_prompt":True}
                continue
            if actor.zone:
                self.training_provider(player,actor,tick)
                cast = self.casts.get(player.id)
                if cast:
                    if (actor.zone,actor.position,actor.cooldowns.get("last_hit")) != (cast["zone"],cast["tile"],cast["last_hit"]): self.casts.pop(player.id)
                    elif tick>=cast["until"]: self.casts.pop(player.id); self.complete_cast(actor,cast)
        for actor in tuple(self.world.actors.values()):
            if actor.zone is None: continue
            for effect in tuple(actor.effects):
                if "until_tick" not in effect: continue
                if tick >= effect.get("next_tick",tick+1) and tick<=effect["until_tick"]:
                    effect["next_tick"] += 10
                    source = self.world.actors.get(effect.get("source"))
                    if effect.get("kind") == "dot" and source and self.legal(source,actor):
                        multiplier = actor.modifiers.get("chemical_dot_multiplier", 1) if effect["damage_type"] == "chemical" else 1
                        self.hurt(source,actor,max(1,int(effect["damage"]*multiplier)-self.armour(actor,str(effect["damage_type"]))),
                                  damage_type=str(effect["damage_type"]))
                    if effect.get("heal") and actor.stance not in ("down","dead"):
                        amount = ceil(effect["heal"]*effect.get("scale",1))
                        receipt, healer = str(effect.get("use_receipt", "")), str(effect.get("source", ""))
                        try: self.commerce.enqueue_system(lambda actor=actor,amount=amount,receipt=receipt,healer=healer:self.heal(actor,amount,healer,receipt))
                        except ValueError: pass
                if tick>=effect["until_tick"] and effect in actor.effects: actor.effects.remove(effect)
            if actor.zone is None: continue
            if actor.target and not self.world.actors.get(actor.target): actor.target = None
            self.world.zones[actor.zone].revision += 1
        for sid,cursor in tuple(self.menus.items()):
            session = self.game.sessions.active.get(sid)
            if session is None or session.closed:
                self.menus.pop(sid);self.sim.external_views.pop(sid,None);continue
            player = self.game.players[session.player_id]
            rows = [{"id":a.id,"cells":[a.name,f"T{a.tier}","ready" if self.unlocked(player,a) else "locked"]} for a in self.content.hymns.values()]
            if rows:
                ability = self.content.hymns[rows[cursor]["id"]]
                self.sim.external_views[sid] = "menu",{**menu("ABILITIES",rows,cursor,ability.description,"Enter uses  1-5 binds  Esc/B returns"),"actions":[{"key":k,"label":"bind "+k} for k in "12345"]}

    def heal(self, actor: Actor, amount: int, healer: str = "", receipt: str = "") -> None:
        if actor.stance not in ("down","dead"):
            before = actor.health
            actor.health = min(actor.health_max,actor.health+amount)
            if actor.health > before and receipt and healer in self.game.players:
                self.game.progression.record_use(healer, Use("hymn_restore", "hymns", receipt, True, changed=True))

    def restore(self, player: Player, actor: Actor) -> None:
        stage = player.progress.get("combat",{}).get("stage")
        if stage in ("down","dead"): actor.stance = stage
        if self.restored.get(player.id) is actor: return
        self.restored[player.id] = actor
        self.casts.pop(player.id,None)
        tick,now = self.clock.now_tick(),self.now()
        if "last_hit_at" in player.progress:
            actor.cooldowns["last_hit"] = tick-rules.ticks(max(0,now-player.progress["last_hit_at"]))
        for key,until in player.progress.get("combat_cooldowns",{}).items(): actor.cooldowns[key] = tick+rules.ticks(max(0,until-now))
        for effect in player.progress.get("combat_effects",[]):
            if effect["until"]>now:
                actor.effects.append({**deepcopy(effect),"until_tick":tick+rules.ticks(effect["until"]-now),
                    "next_tick":tick+rules.ticks(max(0,effect.get("next",now+1)-now))})
