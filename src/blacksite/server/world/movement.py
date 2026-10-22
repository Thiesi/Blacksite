"""Game 5.2 movement and 3.1 stamina on the authoritative tick budget."""

from blacksite.server.world.actors import Actor
from blacksite.server.world.zone import ZoneInstance
from blacksite.server.rules.combat import action_seconds, cooldown_deadline, TICK_SECONDS

WALK_TICKS = 2  # Game design 5.2: 200 ms at 10 Hz.
SPRINT_TICKS = 1  # Game design 5.2: 100 ms.
SPRINT_COST = 2  # Game design 3.1.
STAMINA_REGEN = 1  # Game design 3.1: per non-sprinting tick.


def direction(name: str) -> tuple[int, int] | None:
    return {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0),
            "up_left": (-1, -1), "up_right": (1, -1),
            "down_left": (-1, 1), "down_right": (1, 1)}.get(name)


def move(actor: Actor, zone: ZoneInstance, name: str, tick: int, sprint: bool = False,
         forced: bool = False) -> bool:
    vector = direction(name)
    if vector is None or actor.stance in ("down", "dead", "sleeper", "jacked") or tick < max(actor.cooldowns.get("move", 0),actor.cooldowns.get("knockdown",0)):
        return False
    target = actor.x + vector[0], actor.y + vector[1]
    if forced and (not zone.allows_hostile(actor.position) or not zone.allows_hostile(target)):
        return False
    blocks = lambda a: a.id != actor.id and a.position == target and not (a.behaviour.get("training") and a.owner != actor.id)
    if not zone.can_enter(actor, target) or any(blocks(a) for a in zone.actors.values()):
        return False
    # A diagonal cannot bypass a closed corner or another player's body.
    if vector[0] and vector[1]:
        for side in ((actor.x + vector[0], actor.y), (actor.x, actor.y + vector[1])):
            if not zone.can_enter(actor, side) or any(a.id != actor.id and a.position == side and not (a.behaviour.get("training") and a.owner != actor.id) for a in zone.actors.values()):
                return False
    stamina_multiplier = min((float(e.get("stamina_multiplier",1)) for e in actor.effects),default=1)
    cost = SPRINT_COST*stamina_multiplier*actor.modifiers.get("stamina_cost_multiplier", 1)
    sprint = sprint and actor.stamina >= cost
    actor.x, actor.y = target
    zone.position_update(actor)
    actor.facing = name
    # Game design 3.1 / S12: excess carry weight doubles tile time.
    duration = ((actor.modifiers.get("sprint_ms", SPRINT_TICKS*100)/100) if sprint else WALK_TICKS)
    duration = max(duration, actor.modifiers.get("move_ms", 0)/100)
    duration *= 2 if actor.overweight else 1
    duration = max(duration,max((int(e.get("move_ticks",0)) for e in actor.effects),default=0))
    duration = action_seconds(duration,actor.shock)
    previous = actor.cooldowns.get("move", 0)
    # Keep a bounded fractional budget for Sprint Legs' 80 ms. Inputs
    # still resolve on ticks, sometimes two in one tick; idle time cannot
    # accumulate a burst of free movement.
    actor.cooldowns["move"] = cooldown_deadline(tick, duration*TICK_SECONDS, previous)
    if sprint:
        value = round(max(0, actor.stamina-cost), 6)
        actor.stamina = int(value) if value % 1 == 0 else value
        actor.last_sprint_tick = tick
    zone.revision += 1
    return True


def regenerate(actor: Actor, elapsed: int, tick: int) -> bool:
    before = actor.stamina
    skipped = int(tick - elapsed < actor.last_sprint_tick <= tick)
    value = round(min(actor.stamina_max, actor.stamina + max(0, elapsed - skipped)
                     * STAMINA_REGEN*actor.modifiers.get("stamina_regen_multiplier", 1)), 6)
    actor.stamina = int(value) if value % 1 == 0 else value
    return actor.stamina != before
