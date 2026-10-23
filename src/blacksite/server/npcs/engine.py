"""NPC lifecycle, relations, legal combat and service interactions (5.5)."""

from collections.abc import Callable
from copy import deepcopy
from datetime import datetime, timezone
from math import ceil
from typing import Any

from blacksite.server.combat.engine import Combat
from blacksite.server.commerce import CommerceMenu
from blacksite.server.clock import TICK_HZ
from blacksite.server.items import make_item
from blacksite.server.loop import TickContext
from blacksite.server.npcs.behaviours import patrol, step_toward
from blacksite.server.npcs.spawn import Spawners
from blacksite.server.npcs.templates import (
    DORMANT_SECONDS, EVALUATION_TICKS, FLEE_FRACTION, HEAT_SECONDS,
    LOST_SIGHT_SECONDS, PROVOCATION_SECONDS, WANDER_PAUSE_TICKS,
    SUBDUE_SECONDS, SUBDUE_SHOCK, make_actor, relation, weapon,
    RESPONSE_COUNT, RESPONSE_RADIUS,
    HEAT_SAVE_SECONDS,
)
from blacksite.server.players import Player
from blacksite.server.progression import Grant
from blacksite.server.protocol import Frame
from blacksite.server.rules.combat import (
    CACHE_SECONDS, LOOT_PRIVATE_SECONDS, WARNING_SECONDS, SHOCK_DELAY,
    SHOCK_DECAY, action_seconds, distance, ticks,
)
from blacksite.server.sessions import Session
from blacksite.server.world.actors import Actor
from blacksite.server.world.zone import ZoneInstance


class Npcs:
    def __init__(self, combat: Combat, state: dict[str, Any]) -> None:
        self.combat, self.commerce = combat, combat.commerce
        self.game, self.world, self.clock = combat.game, combat.world, combat.clock
        self.content, self.sim = combat.content, combat.sim
        self.spawners = Spawners(self.world, deepcopy(state), self.game.sessions.origin)
        self.dormant: dict[str, float] = {}
        self.provocations: dict[tuple[str, str, str], float] = {}
        self.menus: set[str] = set()
        self.pending_deaths: set[str] = set()
        self.restraints: dict[str, dict[str, Any]] = {}
        self.heat_saved_at: dict[str, float] = {}
        self.heat_multiplier: float = 1
        self.curfew: Callable[[str], bool] = lambda zone: False  # S24 committed event.
        self.reward_permit: Callable[[Actor, Actor], bool] = lambda source, target: not any(
            target.behaviour.get(key) for key in ("nonlethal", "willing", "escort"))
        combat.refused_hook = self.refused
        combat.hostile_hook = self.provoked
        combat.npc_death_hook = self.died
        combat.training_provider = self.training
        combat.npc_armour = self.armour
        combat.relation_provider = self.actor_relation

    def spawn_mission(self, owner: Actor, mission: str, template_id: str,
                      tile: tuple[int, int], willing: bool = False) -> Actor:
        """S19 creates a scoped copy; a permanent service is never removed."""
        self.spawners.serial += 1
        actor = make_actor(self.content.npcs[template_id],
            f"{self.game.sessions.origin}:npc:{self.spawners.serial}",
            {"mission": mission, "willing": willing, "home": tile, "phase": self.spawners.serial % EVALUATION_TICKS})
        actor.owner = owner.id
        self.world.enter(actor, owner.zone, tile)
        return actor

    def escort(self, source: Actor, target: Actor) -> bool:
        if not target.behaviour.get("mission") or target.owner != source.id or not target.behaviour.get("willing"):
            return False
        target.behaviour["escort"] = source.id
        return True

    def subdue(self, source: Actor, target: Actor) -> bool:
        if (not target.behaviour.get("mission") or target.owner != source.id
                or target.shock < SUBDUE_SHOCK or distance(source.position, target.position) > 1.5
                or not self.combat.legal(source, target)):
            return False
        self.restraints[source.id] = {"target": target.id, "until": self.clock.now_tick()+ticks(SUBDUE_SECONDS),
            "position": source.position, "last_hit": source.cooldowns.get("last_hit")}
        return True

    def actor_relation(self, source: Actor, target: Actor) -> str:
        if target.behaviour.get("training"):
            return "hostile" if target.owner == source.id else "neutral"
        if target.marked or self.hostile(target, source) or self.hostile(source, target):
            return "hostile"
        return {"H": "hostile", "N": "neutral", "A": "allied"}[relation(self.content, source.faction, target.faction)]

    def hostile(self, actor: Actor, other: Actor) -> bool:
        if actor is other or actor.kind == "player" or actor.zone != other.zone:
            return False
        if actor.behaviour.get("training"):
            return actor.owner == other.id
        template = self.content.npcs.get(actor.behaviour.get("template"))
        if template is None:
            return False
        now = self.combat.now()
        if self.provocations.get((actor.zone, str(actor.behaviour.get("spawner")), other.id), 0) > now:
            return True
        player = self.game.players.get(other.id)
        if actor.faction == "wardens" and player:
            if other.marked or (player.warden_heat_until and datetime.fromisoformat(player.warden_heat_until).timestamp() > now):
                return True
        explicit = any(b.params.get("hostile_all") for b in template.behaviours)
        return explicit or relation(self.content, actor.faction, other.faction) == "H"

    def armour(self, actor: Actor, kind: str) -> int:
        template = self.content.npcs.get(actor.behaviour.get("template"))
        item = self.content.items.get(template.armour) if template else None
        return int(getattr(item.armour.armour, kind)) if item and item.armour else 0

    def provoked(self, source: Actor, target: Actor) -> None:
        if (source.kind != "player" and not source.behaviour.get("player_drone")
                or target.kind == "player" or target.behaviour.get("player_drone") or target.behaviour.get("training")):
            return
        group = str(target.behaviour.get("spawner"))
        self.provocations[target.zone, group, source.id] = self.combat.now() + PROVOCATION_SECONDS
        controller = self.game.progression.controller(source)
        if controller:
            self.provocations[target.zone,group,controller.id] = self.combat.now()+PROVOCATION_SECONDS
        target.target = source.id
        target.behaviour.update(last_seen=self.clock.now_tick(), last_position=source.position, state="hunt")
        # Local faction guards protect their residents, without summoning
        # rival police into a district. The same safety checks still apply.
        for actor in self.world.zones[target.zone].actors.values():
            if actor.kind != "player" and actor.faction == target.faction and actor.faction:
                template = self.content.npcs.get(actor.behaviour.get("template"))
                if template and any(b.kind in ("guard", "warden") for b in template.behaviours):
                    self.provocations[actor.zone, str(actor.behaviour.get("spawner")), source.id] = self.combat.now() + PROVOCATION_SECONDS
                    if controller:
                        self.provocations[actor.zone,str(actor.behaviour.get("spawner")),controller.id] = self.combat.now()+PROVOCATION_SECONDS
                    actor.target = source.id
                    actor.behaviour.update(last_seen=self.clock.now_tick(), last_position=source.position, state="hunt")

    def refused(self, source: Actor, target: Actor) -> None:
        zone = self.world.zones.get(source.zone)
        player = self.game.players.get(source.id)
        if not player or not zone or zone.allows_hostile(source.position):
            return
        self.dispatch(source, "Wardens: lower your weapon.")

    def dispatch(self, source: Actor | None, warning: str = "Wardens: your body location is reported.") -> None:
        """Game 5.5/6.7: trace dispatch uses the same nonrewarding response."""
        if source is None:
            return
        zone = self.world.zones.get(source.zone)
        player = self.game.players.get(source.id)
        if player is None or zone is None:
            return
        until = self.combat.now() + HEAT_SECONDS * max(self.heat_multiplier, 2 if self.curfew(zone.id) else 1)
        previous = datetime.fromisoformat(player.warden_heat_until).timestamp() if player.warden_heat_until else 0
        player.warden_heat_until = datetime.fromtimestamp(max(previous, until), timezone.utc).isoformat()
        if self.combat.now()-self.heat_saved_at.get(player.id, -HEAT_SAVE_SECONDS) < HEAT_SAVE_SECONDS:
            return
        self.heat_saved_at[player.id] = self.combat.now()
        self.game.queue("save", player.bbs_user_id, player, immediate=True)
        self.combat.log(source, f"{warning} Heat for {ceil((max(previous, until)-self.combat.now())/60)} minutes; patrols pursue outside safety.", True)
        # Responders enter on nearby legal floor, never on a player or exit.
        for index in range(RESPONSE_COUNT):
            aid = f"response:{source.id}:{index}"
            existing = self.world.actors.get(aid)
            if existing:
                if existing.zone == source.zone:
                    existing.behaviour["expires"] = until
                continue
            template = self.content.npcs.get("npc-warden-response")
            if not template:
                continue
            candidates = sorted(((x, y) for x in range(max(0, source.x-RESPONSE_RADIUS), min(zone.template.width, source.x+RESPONSE_RADIUS+1))
                for y in range(max(0, source.y-RESPONSE_RADIUS), min(zone.template.height, source.y+RESPONSE_RADIUS+1))),
                key=lambda tile: (distance(source.position, tile), tile))
            occupied = {a.position for a in zone.actors.values()} | self.spawners.reserved(zone)
            tile = next((p for p in candidates if p not in occupied and zone.can_enter(None, p) and not zone.tiles[zone.tile_id(p)].hazard), None)
            if tile:
                actor = make_actor(template, aid, {"home": tile, "response": source.id, "expires": until, "phase": index})
                self.world.enter(actor, zone.id, tile)

    def died(self, source: Actor, actor: Actor) -> None:
        if actor.behaviour.get("player_drone"):
            self.game.progression.drones.destroy(actor)
            return
        if actor.id in self.pending_deaths or actor.zone is None:
            return
        actor.stance = "dead"
        self.pending_deaths.add(actor.id)
        def propose() -> None:
            template = self.content.npcs[actor.behaviour["template"]]
            progression = self.game.progression
            player = progression.controller(source)
            if player and player.id in self.game.deleting:
                player = None
            patch, identity, reward = {}, None, None
            grant = None
            before_standing = deepcopy(player.standing) if player else {}
            eligible = (player and template.xp > 0 and not template.training and self.reward_permit(source, actor)
                        and progression.permit_combat(player.id, actor.id))
            if (player and template.xp > 0
                    and not template.training and self.reward_permit(source, actor)
                    and progression.permit_combat(player.id, actor.id)):
                # xp is an eligibility flag inherited from S11. Game 3.5
                # pays the opponent-grade formula, not that old hook value.
                scope = str(actor.behaviour.get("slot") or "mission-npc:"+template.id)
                grant = Grant("combat", actor.id, True, scope=scope, opponent_grade=template.grade)
                patch, identity, reward = progression.reward_patch(player, grant)
            if eligible:
                from blacksite.server.factions import npc_kill
                patch.update(self.game.factions.standing_patch(player,
                    npc_kill(self.content.factions, actor.faction), "explicit"))
            items, caches = deepcopy(self.commerce.items), deepcopy(self.commerce.caches)
            serial = max(self.commerce.serial, max((int(i.rsplit(":", 1)[-1]) for i in items), default=0))
            cache_id = "npc-cache:" + actor.id
            loot: list[str] = []
            zone = self.world.zones[actor.zone]
            for entry in template.loot:
                if zone.rng.random() >= entry.chance:
                    continue
                remaining = entry.count
                while remaining:
                    serial += 1
                    iid = f"{self.game.sessions.origin}:item:{serial}"
                    count = min(remaining, self.content.items[entry.item].stack_max)
                    items[iid] = make_item(iid, self.content.items[entry.item], cache_id, self.clock.now_utc().isoformat(), count)
                    loot.append(iid)
                    remaining -= count
            if loot:
                caches[cache_id] = {"zone": actor.zone, "tile": list(actor.position), "items": loot,
                    "killer": player.id if player else source.id, "victim": actor.id, "private_until": self.combat.now()+LOOT_PRIVATE_SECONDS,
                    "expires": self.combat.now()+CACHE_SECONDS}
            def committed(success: bool) -> None:
                self.pending_deaths.discard(actor.id)
                if not success:
                    # A failed receipt retains one retryable body and no loot.
                    actor.health, actor.stance = 1, "normal"
                    return
                self.spawners.removed(actor, self.combat.now())
                self.world.leave(actor)
                if player:
                    progression.notify_reward(player, reward)
                    self.game.factions.notify_standing(player, before_standing, "NPC kill")
            self.commerce.settle(player, patch, items, caches, serial, committed, identity)
            receipt = deepcopy(self.spawners.record())
            slot = receipt["slots"].get(str(actor.behaviour.get("slot")))
            if slot is not None:
                slot.update(until=self.combat.now()+int(actor.behaviour.get("respawn", 0)))
                slot.pop("actor", None)
            self.commerce.outbox[-1]["npc_state"] = receipt
            if player and hasattr(self.game, 'crews'):
                self.game.crews.stage_cache(self.commerce.outbox[-1], cache_id, player.id)
            if grant and hasattr(self.game, 'crews'):
                self.game.crews.add_rewards(self.commerce.outbox[-1], player, grant)
        self.commerce.enqueue_system(propose)

    def training(self, player: Player, actor: Actor, tick: int) -> None:
        if player.progress.get("wake_combat") in ("done","skipped"): return
        zone = self.world.zones[actor.zone]
        sp = next((sp for sp in zone.template.meta.spawners if sp.condition == "per_player"), None)
        anchor = next((o for o in zone.objects.values() if sp and o.spec.params.get("training_npc") == sp.npc),None)
        drone = next((a for a in self.world.actors.values() if a.owner==player.id and a.behaviour.get("training")),None)
        tile = tuple(anchor.spec.params.get("training_tile",anchor.spec.tile)) if anchor else None
        if not anchor or distance(actor.position,tile)>6:
            if drone: self.world.leave(drone)
            return
        if drone is None:
            if distance(actor.position,tile)>2: return
            template = self.content.npcs[anchor.spec.params["training_npc"]]
            tile = self.world.free_tile(actor.zone,tile)
            drone = Actor(player.id+":training",template.name,kind="drone",owner=player.id,
                health=template.health,health_max=template.health,behaviour={"training":True,"template":template.id,"warned":tick})
            self.world.enter(drone,actor.zone,tile)
            self.combat.warnings.pop((player.id,drone.id),None)
            self.combat.log(actor,"Your training drone wakes. Tab targets; F fires; B skips. Its shots cannot kill.",True)
        template = self.content.npcs[drone.behaviour["template"]]
        if tick>=int(drone.behaviour["warned"])+ticks(WARNING_SECONDS) and tick>=drone.cooldowns.get("weapon",0):
            if self.combat.visible(drone,actor) and distance(drone.position,actor.position)<=template.attack.range:
                self.combat.shot(drone,actor,template.attack)
                drone.cooldowns["weapon"] = tick+ticks(template.attack.cooldown)

    def evaluate(self, actor: Actor, zone: ZoneInstance, tick: int) -> None:
        template = self.content.npcs[actor.behaviour["template"]]
        if template.training:
            return
        candidates = [other for other in zone.actors.values() if other is not actor
            and other.stance not in ("down", "dead") and self.hostile(actor, other)
            and self.combat.legal(actor, other) and self.combat.visible(actor, other)]
        candidates.sort(key=lambda a: (distance(actor.position, a.position), a.id))
        target = self.world.actors.get(actor.target)
        if candidates:
            target = candidates[0]
            actor.target = target.id
            actor.behaviour["last_seen"] = tick
            actor.behaviour["last_position"] = target.position
        elif target and (not self.combat.legal(actor, target) or not self.hostile(actor, target)
                or tick-int(actor.behaviour.get("last_seen", tick)) >= ticks(LOST_SIGHT_SECONDS)):
            actor.target = None
            target = None
        state = "flee" if target and (actor.health < actor.health_max * FLEE_FRACTION or weapon(self.content, template) is None) else "hunt" if target else "base"
        actor.behaviour["state"] = state
        actor.behaviour["evaluated"] = tick

    def act(self, actor: Actor, zone: ZoneInstance, tick: int, avoid: set[tuple[int,int]]) -> None:
        if actor.behaviour.get("powered") is False:
            return
        if destination := actor.behaviour.get("interlock_diversion"):
            step_toward(actor, zone, destination, tick, avoid=avoid)
            return
        if tick < actor.cooldowns.get("knockdown", 0):
            return
        template = self.content.npcs[actor.behaviour["template"]]
        state = actor.behaviour.get("state", "base")
        target = self.world.actors.get(actor.target)
        escort = self.world.actors.get(actor.behaviour.get("escort"))
        if escort and escort.zone == actor.zone and actor.behaviour.get("willing"):
            if distance(actor.position, escort.position) > 1.5:
                step_toward(actor, zone, escort.position, tick, avoid=avoid)
            return
        if target and state in ("hunt", "flee"):
            if not self.combat.legal(actor, target):
                actor.target = None
                return
            if state == "flee":
                destinations = [ex.tile for ex in zone.template.meta.exits] + [o.spec.tile for o in zone.objects.values() if o.spec.kind == "vat"]
                destinations.sort(key=lambda p: (distance(actor.position, p)-distance(target.position, p), p))
                away = (actor.x + (1 if actor.x >= target.x else -1), actor.y + (1 if actor.y >= target.y else -1))
                step_toward(actor, zone, destinations[0] if destinations else away, tick)
                return
            arm = weapon(self.content, template)
            if arm and self.combat.visible(actor, target) and distance(actor.position, target.position) <= (1.5 if arm.melee else arm.range):
                if tick >= actor.cooldowns.get("weapon", 0) and self.combat.warn(actor, target, tick):
                    jam = max((float(e.get("weapon_multiplier", 1)) for e in actor.effects), default=1)
                    actor.cooldowns["weapon"] = tick + ticks(action_seconds(arm.cooldown, actor.shock, jam))
                    self.combat.shot(actor, target, arm)
            else:
                step_toward(actor, zone, tuple(actor.behaviour.get("last_position", actor.position)), tick, avoid=avoid)
            return
        for behaviour in template.behaviours:
            params = behaviour.params
            if behaviour.kind == "wander":
                if tick < int(actor.behaviour.get("pause", 0)):
                    return
                tile = actor.x+zone.rng.choice((-1, 0, 1)), actor.y+zone.rng.choice((-1, 0, 1))
                step_toward(actor, zone, tile, tick, actor.behaviour.get("region"), avoid)
                actor.behaviour["pause"] = tick + zone.rng.randint(*WANDER_PAUSE_TICKS)
                return
            if behaviour.kind == "patrol":
                points = params.get("waypoints", [])
                patrol(actor, zone, [tuple(p) for p in points], tick, bool(params.get("bounce")), avoid)
                return
            if behaviour.kind in ("guard", "warden"):
                step_toward(actor, zone, tuple(actor.behaviour["home"]), tick, avoid=avoid)

    def input(self, session: Session, frame: Frame, tick: int) -> bool:
        if session.id in self.menus:
            if (frame.type == "intent" and frame.data.get("name") == "menu_close") or (frame.type == "key" and frame.data.get("k") in ("b", "B", "escape")):
                self.menus.discard(session.id)
                self.sim.external_views.pop(session.id, None)
                self.sim.reset_view(session, self.sim.avatars[session.user_id])
            return True
        if not self.commerce.ready(session) or session.id in self.sim.external_views:
            return False
        if not ((frame.type == "key" and frame.data.get("k") in ("e", "E")) or (frame.type == "intent" and frame.data.get("name") == "interact")):
            return False
        actor = self.sim.avatars[session.user_id].actor
        zone = self.world.zones[actor.zone]
        for other in sorted(zone.actors.values(), key=lambda a: (a.id != actor.target, a.id)):
            template = self.content.npcs.get(other.behaviour.get("template"))
            if other is actor or template is None or distance(actor.position, other.position) > 1.5 or other.stance == "dead":
                continue
            if template.vendor:
                counter = next((o for o in zone.objects.values() if o.spec.params.get("vendor") == template.vendor and distance(actor.position, o.spec.tile) <= 1.5), None)
                if counter:
                    self.commerce.menus[session.id] = CommerceMenu("vendor", counter.spec.id, opened=tick)
                    return True
            if any(b.kind == "talker" for b in template.behaviours):
                self.menus.add(session.id)
                self.sim.external_views[session.id] = "text", {"title": template.name, "lines": ["Not yet."], "hint": "Esc/B returns"}
                return True
        return False

    def tick(self, ctx: TickContext) -> None:
        now = self.combat.now()
        for sid in tuple(self.menus):
            session = self.game.sessions.active.get(sid)
            if session is None or session.closed:
                self.menus.discard(sid)
                self.sim.external_views.pop(sid, None)
        if ctx.tick % EVALUATION_TICKS == 0:
            self.combat.warnings = {pair: tick for pair, tick in self.combat.warnings.items()
                if pair[0] in self.world.actors and pair[1] in self.world.actors}
        for source_id, channel in tuple(self.restraints.items()):
            source = self.world.actors.get(source_id)
            target = self.world.actors.get(channel["target"])
            if (not source or not target or source.position != channel["position"]
                    or source.cooldowns.get("last_hit") != channel["last_hit"]
                    or not self.combat.legal(source, target) or distance(source.position, target.position) > 1.5):
                self.restraints.pop(source_id, None)
            elif ctx.tick >= channel["until"]:
                target.behaviour["resolution"] = "subdued"
                target.stance = "restrained"
                self.world.leave(target)
                self.restraints.pop(source_id, None)
        self.provocations = {key: until for key, until in self.provocations.items() if until > now}
        for zone in self.world.zones.values():
            if zone.dormant:
                self.dormant.setdefault(zone.id, now)
                if now-self.dormant[zone.id] >= DORMANT_SECONDS:
                    for actor in tuple(zone.actors.values()):
                        template = self.content.npcs.get(actor.behaviour.get("template"))
                        if template and not any(b.params.get("anchor") for b in template.behaviours):
                            self.world.leave(actor)
                continue
            dormant_since = self.dormant.pop(zone.id, None)
            if dormant_since is not None and now-dormant_since >= DORMANT_SECONDS:
                for actor in tuple(zone.actors.values()):
                    template = self.content.npcs.get(actor.behaviour.get("template"))
                    if template and not any(b.params.get("anchor") for b in template.behaviours):
                        self.world.leave(actor)
            self.spawners.process(zone, now)
            avoid = self.spawners.reserved(zone)
            for actor in tuple(zone.actors.values()):
                if actor.kind == "player" or actor.behaviour.get("training") or actor.behaviour.get("player_drone") or actor.stance in ("down", "dead"):
                    continue
                if actor.behaviour.get("expires", now+1) <= now:
                    self.world.leave(actor)
                    continue
                if actor.shock and ctx.tick-actor.cooldowns.get("last_hit", ctx.tick) >= ticks(SHOCK_DELAY):
                    actor.shock = max(0, actor.shock-SHOCK_DECAY/TICK_HZ)
                if ctx.tick % EVALUATION_TICKS == actor.behaviour.get("phase", 0):
                    self.evaluate(actor, zone, ctx.tick)
                self.act(actor, zone, ctx.tick, avoid)
