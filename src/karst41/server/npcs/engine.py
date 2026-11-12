"""NPC lifecycle, relations, legal combat and service interactions (5.5)."""

from karst41.server.interaction import Focus, Interaction, interact, object_interaction
from karst41.content.schema import Spawner
from collections.abc import Callable
from copy import deepcopy
from datetime import datetime, timezone
from math import ceil
from typing import Any

from karst41.server.combat.engine import Combat
from karst41.server.commerce import CommerceMenu
from karst41.server.clock import TICK_HZ
from karst41.server.items import make_item
from karst41.server.loop import TickContext
from karst41.server.npcs.behaviours import Route, patrol, route_toward, step_toward
from karst41.server.npcs.spawn import Spawners
from karst41.server.npcs.templates import (
    DORMANT_SECONDS, EVALUATION_TICKS, FLEE_FRACTION, HEAT_SECONDS,
    LOST_SIGHT_SECONDS, PROVOCATION_SECONDS, WANDER_PAUSE_TICKS,
    SUBDUE_SECONDS, SUBDUE_SHOCK, make_actor, relation, weapon,
    RESPONSE_COUNT, RESPONSE_RADIUS,
    HEAT_SAVE_SECONDS, REACH_ACTIVE_TICKS,
)
from karst41.server.players import Player
from karst41.server.progression import Grant
from karst41.server.protocol import Frame
from karst41.server.rules.combat import (
    CACHE_SECONDS, LOOT_PRIVATE_SECONDS, WARNING_SECONDS, SHOCK_DELAY,
    SHOCK_DECAY, action_seconds, distance, ticks,
)
from karst41.server.sessions import Session
from karst41.server.world.actors import Actor
from karst41.server.world.sight import detection_limit, sight_radius
from karst41.server.world.zone import ZoneInstance
from karst41.server.views import presentation
from karst41.server import truce as truce_rules


class Npcs:
    def __init__(self, combat: Combat, state: dict[str, Any]) -> None:
        self.combat, self.commerce = combat, combat.commerce
        self.game, self.world, self.clock = combat.game, combat.world, combat.clock
        self.content, self.sim = combat.content, combat.sim
        self.game.npcs = self
        self.spawners = Spawners(self.world, deepcopy(state), self.game.sessions.origin)
        self.dormant: dict[str, float] = {}
        self.provocations: dict[tuple[str, str, str], float] = {}
        # S44: zone -> player -> expiry of the keeper's stored answer. A
        # mirror of Player.keeper_answer, so a guard that spawns or wakes
        # while it is live takes it up; `hunted` reads only the record.
        self.answers: dict[str, dict[str, float]] = {}
        self.routes: dict[str, Route] = {}  # S44: hunt routes by actor id.
        self.answer_saved_at: dict[str, float] = {}
        self.menus: set[str] = set()
        self.talking: Callable[[str, str], bool] = lambda sid, aid: False
        self.pending_deaths: set[str] = set()
        self.restraints: dict[str, dict[str, Any]] = {}
        self.heat_saved_at: dict[str, float] = {}
        self.heat_multiplier: float = 1
        self.curfew: Callable[[str], bool] = lambda zone: False  # S24 committed event.
        self.event_fact: Callable[[dict[str, Any], Actor, Actor], None] = lambda effect, source, actor: None
        self.keep_awake: Callable[[str], bool] = lambda zone: False
        self.event_motion: Callable[[Actor, ZoneInstance, int, set[tuple[int, int]]], bool] = lambda actor, zone, tick, avoid: False
        self.reward_permit: Callable[[Actor, Actor], bool] = lambda source, target: not any(
            target.behaviour.get(key) for key in ("nonlethal", "willing", "escort"))
        combat.refused_hook = self.refused
        combat.hostile_hook = self.provoked
        combat.npc_death_hook = self.died
        combat.training_provider = self.training
        combat.npc_armour = self.armour
        combat.relation_provider = self.actor_relation
        combat.cover_relation_provider = self.public_relation
        combat.keeper_settles = self.keeper_settles
        combat.settle_hook = self.settle
        self.restore_answers()

    def keeper_groups(self, zone: ZoneInstance, keeper: str) -> set[str]:
        """The keeper's guard spawners in a zone, live or not.

        The answer is the keeper's, not one guard's: a breach with every
        guard dead still provokes the groups their respawns come from.
        """
        groups = set()
        for spawner in zone.template.meta.spawners:
            template = self.content.npcs.get(spawner.npc)
            if (template and template.faction == keeper and not spawner.poses_as
                    and any(b.kind == "guard" for b in template.behaviours)):
                groups.add(spawner.id)
        for guard in self.keeper_guards(zone, keeper):
            groups.add(str(guard.behaviour.get("spawner")))
        return groups

    def keeper_guards(self, zone: ZoneInstance, keeper: str) -> list[Actor]:
        guards = []
        for guard in zone.actors.values():
            template = self.content.npcs.get(guard.behaviour.get("template"))
            if (guard.kind != "player" and guard.faction == keeper and template
                    and not self.covered_unarmed(guard)
                    and any(b.kind == "guard" for b in template.behaviours)):
                guards.append(guard)
        return guards

    def keeper_guard(self, actor: Actor, zone: ZoneInstance) -> bool:
        keeper = zone.template.meta.truce
        template = self.content.npcs.get(actor.behaviour.get("template"))
        return bool(keeper and actor.kind != "player" and actor.faction == keeper and template
                    and not self.covered_unarmed(actor)
                    and any(b.kind == "guard" for b in template.behaviours))

    def restore_answers(self) -> None:
        """S44 ruling: a live stored answer restores the guards' provocation."""
        now = self.combat.now()
        for player in self.game.players.values():
            until = truce_rules.answer_until(player)
            record = player.keeper_answer or {}
            zone = self.world.zones.get(str(record.get("zone", "")))
            if until <= now or zone is None or not zone.template.meta.truce:
                if until <= now:
                    player.keeper_answer = None  # An expired answer is dropped.
                continue
            for group in self.keeper_groups(zone, zone.template.meta.truce):
                self.provocations[zone.id, group, player.id] = until
            self.answers.setdefault(zone.id, {})[player.id] = until

    def keeper_settles(self, player: Player) -> str | None:
        """The keeper's short name when a death would settle a live answer."""
        if not truce_rules.hunted(player, self.combat.now()):
            return None
        return truce_rules.keeper_name(self.content, str((player.keeper_answer or {}).get("keeper", "")))

    def settle(self, player: Player) -> None:
        """Game 5.5: any death settles the debt with the keeper.

        Clears the keeper's provocation and stands down every keeper guard
        holding the player, in the tick the death commits. The stored
        record is cleared by the death's own durable patch.
        """
        player.keeper_answer = None
        for answers in self.answers.values():
            answers.pop(player.id, None)
        for zone in self.world.zones.values():
            keeper = zone.template.meta.truce
            if not keeper:
                continue
            for group in self.keeper_groups(zone, keeper):
                self.provocations.pop((zone.id, group, player.id), None)
            for guard in self.keeper_guards(zone, keeper):
                guard.behaviour.get("answered", {}).pop(player.id, None)
                if guard.target == player.id:
                    guard.target = None
                    guard.behaviour["state"] = "base"
                    guard.behaviour.pop("last_position", None)

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
        if (not target.behaviour.get('mission') or not target.behaviour.get('willing')
                or source.id not in target.behaviour.get('mission_roster', (target.owner,))):
            return False
        target.behaviour["escort"] = source.id
        return True

    def subdue(self, source: Actor, target: Actor) -> bool:
        if (not target.behaviour.get("mission") or source.id not in target.behaviour.get('mission_roster', (target.owner,))
                or target.shock < SUBDUE_SHOCK or distance(source.position, target.position) > 1.5
                or not self.combat.legal(source, target)):
            return False
        self.restraints[source.id] = {"target": target.id, "until": self.clock.now_tick()+ticks(SUBDUE_SECONDS),
            "position": source.position, "last_hit": source.cooldowns.get("last_hit")}
        source.behaviour['channel'] = {'owner': 'restraint', 'label': 'Restrain '+target.name,
                                       'remaining': SUBDUE_SECONDS}
        self.world.zones[source.zone].revision += 1
        return True

    def actor_relation(self, source: Actor, target: Actor) -> str:
        if target.behaviour.get("training"):
            return "hostile" if target.owner == source.id else "neutral"
        if target.marked or self.hostile(target, source) or self.hostile(source, target):
            return "hostile"
        zone = self.world.zones.get(target.zone)
        if zone and zone.template.meta.truce and (source.kind != "player" or target.kind != "player"):
            return "neutral"
        return {"H": "hostile", "N": "neutral", "A": "allied"}[relation(self.content, source.faction, target.faction)]

    def hostile(self, actor: Actor, other: Actor) -> bool:
        if actor is other or actor.kind == "player" or actor.zone != other.zone:
            return False
        if actor.behaviour.get("training"):
            return actor.owner == other.id
        group = actor.behaviour.get("spawner")
        if group and group == other.behaviour.get("spawner"):
            return False  # Game 5.5: packs and cohorts do not hunt siblings.
        template = self.content.npcs.get(actor.behaviour.get("template"))
        if template is None:
            return False
        now = self.combat.now()
        if self.provocations.get((actor.zone, self.reaction_group(actor), other.id), 0) > now:
            return True
        if self.covered_unarmed(actor):
            return False  # Game 5.5: the cover enforces nothing while unarmed.
        player = self.game.players.get(other.id)
        if actor.faction == "wardens" and player:
            if other.marked or (player.warden_heat_until and datetime.fromisoformat(player.warden_heat_until).timestamp() > now):
                return True
        if self.world.zones[actor.zone].template.meta.truce:
            return False  # Game 5.5: only provocation/heat breaks the truce.
        explicit = any(b.params.get("hostile_all") for b in template.behaviours)
        return explicit or relation(self.content, actor.faction, other.faction) == "H"

    def armour(self, actor: Actor, kind: str) -> int:
        template = self.content.npcs.get(actor.behaviour.get("template"))
        item = self.content.items.get(template.armour) if template else None
        return int(getattr(item.armour.armour, kind)) if item and item.armour else 0

    def covered_unarmed(self, actor: Actor) -> bool:
        template = self.content.npcs.get(actor.behaviour.get('template'))
        return bool(template and template.presents and weapon(self.content, template) is None)

    def posed_spawner(self, actor: Actor) -> Spawner | None:
        if not self.covered_unarmed(actor):
            return None
        spawners = self.world.zones[actor.zone].template.meta.spawners
        own = next((sp for sp in spawners if sp.id == actor.behaviour.get('spawner')), None)
        return next((sp for sp in spawners if own and sp.id == own.poses_as), None)

    def reaction_group(self, actor: Actor) -> str:
        posed = self.posed_spawner(actor)
        return posed.id if posed else str(actor.behaviour.get('spawner'))

    def public_relation(self, viewer: Actor, actor: Actor, nearby: bool) -> str | None:
        """S42/#182 ruling: show the declared crowd's public reaction only."""
        posed = self.posed_spawner(actor)
        if posed is None or not presentation.covered(actor, viewer, self.content):
            return None
        provoked = self.provocations.get((actor.zone, posed.id, viewer.id), 0) > self.combat.now()
        # TARGET/Tab use disposition; NEARBY's ordinary marker names a
        # current pursuer. Preserve those existing surface semantics.
        hostile = provoked and (not nearby or actor.target == viewer.id)
        return 'hostile' if hostile else 'neutral'

    def shared_crowd(self, actor: Actor) -> bool:
        group = self.reaction_group(actor)
        return any(sp.poses_as == group for sp in self.world.zones[actor.zone].template.meta.spawners)

    def reach_holders(self, actor: Actor, zone: ZoneInstance, tick: int) -> list[tuple[int, int]]:
        """Game 5.5: only active, talk-capable callers constrain wandering."""
        holders = []
        for session in self.game.sessions.active.values():
            body = zone.actors.get(session.player_id)
            if (session.closed or body is None or body.kind != 'player' or body.health <= 0
                    or body.stance in ('down', 'dead', 'sleeper', 'jacked')
                    or max(abs(body.x-actor.x), abs(body.y-actor.y)) > 1):
                continue
            if tick-session.last_action_tick <= REACH_ACTIVE_TICKS or self.talking(session.id, actor.id):
                holders.append(body.position)
        return holders

    def truce_keeper(self, source: Actor, target: Actor) -> str | None:
        """Game 5.5/7.3: one predicate for the warning and keeper response."""
        victim = (self.game.progression.drones.controller_body(target, acting=False)
                  if target.behaviour.get("player_drone") else target)
        zone = self.world.zones.get(victim.zone) if victim else None
        controller = self.game.progression.controller(source)
        if (not zone or not zone.template.meta.truce or not controller
                or target.behaviour.get("training")
                or not self.combat.permits_indirect(source, target)):
            return None
        body = self.combat.actor(controller)
        if body is None:
            return None
        if victim.kind == "player":
            breaks = self.combat.would_mark(body, victim, indirect=True)
        else:
            attackers = {source.id, body.id}
            provoked = any(self.provocations.get(
                (target.zone, self.reaction_group(target), attacker), 0) > self.combat.now()
                for attacker in attackers)
            breaks = not (provoked or target.target in attackers and target.behaviour.get("state") == "hunt")
        return zone.template.meta.truce if breaks else None

    def keep_truce(self, source: Actor, target: Actor, keeper: str) -> None:
        """Alert the target zone's guards; remote controllers are not chased out.

        S44: every breach writes the keeper's stored answer against the
        responsible player's body, whether or not a guard is present.
        """
        if target.behaviour.get("player_drone"):
            target = self.game.progression.drones.controller_body(target, acting=False)
            if target is None:
                return
        zone = self.world.zones[target.zone]
        controller = self.game.progression.controller(source)
        body = self.combat.actor(controller) if controller else None
        if body is None:
            return
        now = self.combat.now()
        until = now + PROVOCATION_SECONDS
        player = self.game.players.get(body.id)
        guards = self.keeper_guards(zone, keeper)
        if player is not None:
            already_provoked = truce_rules.hunted(player, now)
        else:
            already_provoked = any(self.provocations.get(
                (zone.id, str(guard.behaviour.get("spawner")), body.id), 0) > now for guard in guards)
        groups = self.keeper_groups(zone, keeper)
        for group in groups:
            for attacker in {source.id, body.id}:
                self.provocations[zone.id, group, attacker] = until
        for guard in guards:
            guard.behaviour.setdefault("answered", {})[body.id] = until
            if source.zone == zone.id:
                guard.target = source.id
                self.combat.reveal(guard, source)
                guard.behaviour.update(last_seen=self.clock.now_tick(),
                                       last_position=source.position, state="hunt")
        if player is not None:
            previous = player.keeper_answer or {}
            player.keeper_answer = {"keeper": keeper, "zone": zone.id, "until": truce_rules.iso(until)}
            self.answers.setdefault(zone.id, {})[body.id] = until
            # A new answer saves at once. Refreshes of `until` from repeated
            # hits coalesce to one save a second, as heat refreshes do; a
            # crash can shorten the final refresh by less than a second.
            fresh = not already_provoked or (previous.get("keeper"), previous.get("zone")) != (keeper, zone.id)
            if fresh or now-self.answer_saved_at.get(player.id, -HEAT_SAVE_SECONDS) >= HEAT_SAVE_SECONDS:
                self.answer_saved_at[player.id] = now
                self.game.queue("save", player.bbs_user_id, player, immediate=True)
        name = self.content.factions[keeper].short
        line = (f"{name} is coming for you." if body.zone == zone.id else
                f"{name} is waiting for you on {zone.template.meta.name}.")
        # The line names guards who will come: live ones, or a spawner's.
        if groups and not already_provoked:
            self.combat.log(body, line, True)

    def provoked(self, source: Actor, target: Actor) -> None:
        if keeper := self.truce_keeper(source, target):
            self.keep_truce(source, target, keeper)
        if (source.kind != "player" and not source.behaviour.get("player_drone")
                or target.kind == "player" or target.behaviour.get("player_drone") or target.behaviour.get("training")):
            return
        group = self.reaction_group(target)
        self.provocations[target.zone, group, source.id] = self.combat.now() + PROVOCATION_SECONDS
        controller = self.game.progression.controller(source)
        if controller:
            self.provocations[target.zone,group,controller.id] = self.combat.now()+PROVOCATION_SECONDS
        crowd = self.shared_crowd(target)
        if source.zone == target.zone:
            members = [actor for actor in self.world.zones[target.zone].actors.values()
                       if crowd and self.reaction_group(actor) == group] if crowd else [target]
            for member in members:
                template = self.content.npcs[member.behaviour['template']]
                state = 'flee' if (crowd or self.covered_unarmed(member)) and weapon(self.content, template) is None else 'hunt'
                member.target = source.id
                if state == 'hunt':
                    self.combat.reveal(member, source)
                member.behaviour.update(last_seen=self.clock.now_tick(), last_position=source.position, state=state)
        # Local faction guards protect their residents, without summoning
        # rival police into a district. The same safety checks still apply.
        posed = self.posed_spawner(target)
        faction = self.content.npcs[posed.npc].faction if posed else target.faction
        for actor in self.world.zones[target.zone].actors.values():
            if (actor.kind != "player" and actor.faction == faction and actor.faction
                    and not self.covered_unarmed(actor)):
                template = self.content.npcs.get(actor.behaviour.get("template"))
                if template and any(b.kind in ("guard", "warden") for b in template.behaviours):
                    self.provocations[actor.zone, str(actor.behaviour.get("spawner")), source.id] = self.combat.now() + PROVOCATION_SECONDS
                    if controller:
                        self.provocations[actor.zone,str(actor.behaviour.get("spawner")),controller.id] = self.combat.now()+PROVOCATION_SECONDS
                    if source.zone == actor.zone:
                        actor.target = source.id
                        self.combat.reveal(actor, source)
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
                from karst41.server.factions import npc_kill
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
            respawn_at = self.spawners.deadline(actor, self.combat.now())
            def committed(success: bool) -> None:
                self.pending_deaths.discard(actor.id)
                if not success:
                    # A failed receipt retains one retryable body and no loot.
                    actor.health, actor.stance = 1, "normal"
                    return
                self.spawners.removed(actor, self.combat.now(), deadline=respawn_at)
                self.world.leave(actor)
                if player:
                    progression.notify_reward(player, reward)
                    self.game.factions.notify_standing(player, before_standing, "NPC kill")
            self.commerce.settle(player, patch, items, caches, serial, committed, identity)
            def npc_snapshot() -> dict[str, Any]:
                receipt = deepcopy(self.spawners.record())
                slot = receipt['slots'].get(str(actor.behaviour.get('slot')))
                if slot is not None:
                    slot.update(until=respawn_at)
                    slot.pop('actor', None)
                return receipt
            self.commerce.outbox[-1]['npc_state'] = npc_snapshot
            if player and hasattr(self.game, 'crews'):
                self.game.crews.stage_cache(self.commerce.outbox[-1], cache_id, player.id)
            if grant and hasattr(self.game, 'crews'):
                self.game.crews.add_rewards(self.commerce.outbox[-1], player, grant)
            if hasattr(self.game, 'contracts'):
                self.game.contracts.npc_fact(self.commerce.outbox[-1], source, actor, 'lethal')
            self.event_fact(self.commerce.outbox[-1], source, actor)
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
        # Compute the observer's radius once. Most full-city candidates
        # are too far away even before hostility, occlusion and body rules.
        hour = self.clock.now_local().hour
        radius = sight_radius(actor, zone, hour >= 20 or hour < 6)
        candidates = [other for other in zone.actors.values() if other is not actor
            and other.stance not in ("down", "dead")
            and (actor.x-other.x)**2+(actor.y-other.y)**2 <= detection_limit(radius, other)**2
            and self.hostile(actor, other)
            and self.combat.visible(actor, other) and self.combat.legal(actor, other)]
        candidates.sort(key=lambda a: (distance(actor.position, a.position), a.id))
        target = self.world.actors.get(actor.target)
        if candidates:
            target = candidates[0]
            actor.target = target.id
            actor.behaviour["last_seen"] = tick
            actor.behaviour["last_position"] = target.position
        elif target is None and (taken := self.take_up_answer(actor, zone, tick)):
            target = taken
        elif target and (not self.combat.legal(actor, target) or not self.hostile(actor, target)
                or not self.shared_crowd(actor)
                and tick-int(actor.behaviour.get("last_seen", tick)) >= ticks(LOST_SIGHT_SECONDS)):
            actor.target = None
            target = None
        state = "flee" if target and (actor.health < actor.health_max * FLEE_FRACTION or weapon(self.content, template) is None) else "hunt" if target else "base"
        actor.behaviour["state"] = state
        if target and state == 'hunt':
            self.combat.reveal(actor, target)
        actor.behaviour["evaluated"] = tick

    def take_up_answer(self, actor: Actor, zone: ZoneInstance, tick: int) -> Actor | None:
        """S44: a keeper guard that spawns or wakes during a live answer goes
        to the answered body's position once; the 20 s give-up then applies."""
        answers = self.answers.get(zone.id)
        if not answers or not self.keeper_guard(actor, zone):
            return None
        now = self.combat.now()
        taken = actor.behaviour.setdefault("answered", {})
        for pid, until in sorted(answers.items()):
            body = zone.actors.get(pid)
            if (until <= now or taken.get(pid) == until or body is None
                    or body.stance in ("down", "dead")
                    or not self.hostile(actor, body) or not self.combat.legal(actor, body)):
                continue
            taken[pid] = until
            actor.target = body.id
            actor.behaviour.update(last_seen=tick, last_position=body.position)
            return body
        return None

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
        if actor.behaviour.get('contract_target') and actor.behaviour.get('willing'):
            # Game 9.3: meet the willing group at its labelled source.
            # A civilian template's ambient wandering must not scatter
            # unassigned escorts or move them while their worker is away.
            return
        if target and state in ("hunt", "flee"):
            if self.shared_crowd(actor) and not self.hostile(actor, target):
                # One declared crowd shares its deadline, independent of
                # each member's five-tick evaluation phase.
                actor.target = None
                actor.behaviour['state'] = 'base'
                return
            if not self.combat.legal(actor, target):
                actor.target = None
                return
            if state == "flee":
                destinations = [ex.tile for ex in zone.template.meta.exits] + [o.spec.tile for o in zone.objects.values() if o.spec.kind == "vat"]
                destinations.sort(key=lambda p: (distance(actor.position, p)-distance(target.position, p), p))
                away = (actor.x + (1 if actor.x >= target.x else -1), actor.y + (1 if actor.y >= target.y else -1))
                step_toward(actor, zone, destinations[0] if destinations else away, tick, avoid=avoid)
                return
            arm = weapon(self.content, template)
            if arm and self.combat.visible(actor, target) and distance(actor.position, target.position) <= (1.5 if arm.melee else arm.range):
                if tick >= actor.cooldowns.get("weapon", 0) and self.combat.warn(actor, target, tick):
                    jam = max((float(e.get("weapon_multiplier", 1)) for e in actor.effects), default=1)
                    actor.cooldowns["weapon"] = tick + ticks(action_seconds(arm.cooldown, actor.shock, jam))
                    self.combat.shot(actor, target, arm)
            else:
                # S44 (#187): hunt follows a bounded, cached shortest path.
                route_toward(actor, zone, tuple(actor.behaviour.get("last_position", actor.position)), tick,
                             self.routes.setdefault(actor.id, Route()), avoid)
            return
        if self.event_motion(actor, zone, tick, avoid):
            return
        for behaviour in template.behaviours:
            params = behaviour.params
            if behaviour.kind == "wander":
                if tick < int(actor.behaviour.get("pause", 0)):
                    return
                tile = actor.x+zone.rng.choice((-1, 0, 1)), actor.y+zone.rng.choice((-1, 0, 1))
                region = actor.behaviour.get("region")
                if region and not region.contains(actor.position):
                    step_toward(actor, zone, tuple(actor.behaviour["home"]), tick, avoid=avoid)
                else:
                    holders = self.reach_holders(actor, zone, tick)
                    step_toward(actor, zone, tile, tick, region, avoid,
                        permit=lambda candidate: all(max(abs(candidate[0]-p[0]), abs(candidate[1]-p[1])) <= 1
                                                     for p in holders))
                actor.behaviour["pause"] = tick + zone.rng.randint(*WANDER_PAUSE_TICKS)
                return
            if behaviour.kind == "patrol":
                points = params.get("waypoints", [])
                patrol(actor, zone, [tuple(p) for p in points], tick, bool(params.get("bounce")), avoid)
                return
            if behaviour.kind in ("guard", "warden"):
                step_toward(actor, zone, tuple(actor.behaviour["home"]), tick, avoid=avoid)

    def interaction(self, session: Session, frame: Frame) -> Interaction | None:
        if session.id in self.menus:
            return Interaction()
        if not self.commerce.ready(session) or session.id in self.sim.external_views or not interact(frame):
            return None
        actor = self.sim.avatars[session.user_id].actor
        zone = self.world.zones[actor.zone]
        for other in sorted(zone.actors.values(), key=lambda a: (a.id != actor.target, a.id)):
            template = self.content.npcs.get(other.behaviour.get('template'))
            if other is actor or template is None or distance(actor.position, other.position) > 1.5 or other.stance == 'dead':
                continue
            if template.vendor:
                counter = next((o for o in zone.objects.values() if o.spec.params.get('vendor') == template.vendor
                                and distance(actor.position, o.spec.tile) <= 1.5), None)
                if counter:
                    choice = object_interaction(counter)
                    return Interaction(choice.focus, ('vendor', counter), counter.spec.tile, kind='vendor')
            if any(b.kind == 'talker' for b in template.behaviours):
                return Interaction(Focus(other.id, presentation.name(other, actor, self.content), 'talk to'),
                                   ('talker', other), other.position, other.id, kind='dialogue')
        return None

    def input(self, session: Session, frame: Frame, tick: int, *, interaction: Interaction | None = None) -> bool:
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
        choice = interaction or self.interaction(session, frame)
        if not choice:
            return False
        kind, target = choice.value
        if kind == 'vendor':
            self.commerce.menus[session.id] = CommerceMenu("vendor", target.spec.id, opened=tick)
        else:
            self.menus.add(session.id)
            self.sim.external_views[session.id] = "text", {"title": presentation.name(target, actor, self.content), "lines": ["Not yet."], "hint": "Esc/B returns"}
        return True

    def tick(self, ctx: TickContext) -> None:
        now = self.combat.now()
        for sid in tuple(self.menus):
            session = self.game.sessions.active.get(sid)
            if session is None or session.closed:
                self.menus.discard(sid)
                self.sim.external_views.pop(sid, None)
        if ctx.tick % EVALUATION_TICKS == 0:
            self.routes = {aid: route for aid, route in self.routes.items()
                           if (actor := self.world.actors.get(aid)) and actor.behaviour.get("state") == "hunt"}
            self.combat.warnings = {pair: tick for pair, tick in self.combat.warnings.items()
                if pair[0] in self.world.actors and pair[1] in self.world.actors}
        for source_id, channel in tuple(self.restraints.items()):
            source = self.world.actors.get(source_id)
            target = self.world.actors.get(channel["target"])
            if source and source.behaviour.get('channel', {}).get('owner') == 'restraint':
                source.behaviour['channel']['remaining'] = max(0, (channel['until']-ctx.tick)/TICK_HZ)
            if (not source or not target or source.position != channel["position"]
                    or source.cooldowns.get("last_hit") != channel["last_hit"]
                    or not self.combat.legal(source, target) or distance(source.position, target.position) > 1.5):
                self.restraints.pop(source_id, None)
                if source and source.behaviour.get('channel', {}).get('owner') == 'restraint':
                    source.behaviour.pop('channel')
            elif ctx.tick >= channel["until"]:
                if source.behaviour.get('channel', {}).get('owner') == 'restraint':
                    source.behaviour.pop('channel')
                if (hasattr(self.game, 'contracts') and target.behaviour.get('mission')
                        in self.game.contracts.state.engine.instances):
                    self.restraints.pop(source_id, None)
                    self.game.contracts.subdued(source, target)
                    continue
                target.behaviour["resolution"] = "subdued"
                target.stance = "restrained"
                self.world.leave(target)
                self.restraints.pop(source_id, None)
        self.provocations = {key: until for key, until in self.provocations.items() if until > now}
        for zone in self.world.zones.values():
            if zone.dormant and not self.keep_awake(zone.id):
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
            self.calm_crowds(zone, ctx.tick)

    def calm_crowds(self, zone: ZoneInstance, tick: int) -> None:
        """Game 5.5: a declared crowd shares its last sight and calm tick.

        Finish after every member's ordinary five-tick observation. Actor
        iteration order must not give the covered member an earlier close.
        The existing twenty-second lost-sight interval remains unchanged.
        """
        groups: dict[tuple[str, str], list[Actor]] = {}
        for actor in zone.actors.values():
            if (actor.kind == 'npc' and actor.target and actor.stance not in ('down', 'dead')
                    and actor.behaviour.get('state') in ('hunt', 'flee') and self.shared_crowd(actor)):
                groups.setdefault((self.reaction_group(actor), actor.target), []).append(actor)
        for members in groups.values():
            last_seen = max(int(actor.behaviour.get('last_seen', tick)) for actor in members)
            for actor in members:
                actor.behaviour['last_seen'] = last_seen
                if tick-last_seen >= ticks(LOST_SIGHT_SECONDS):
                    actor.target = None
                    actor.behaviour['state'] = 'base'
