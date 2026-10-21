"""Game design 5.2 movement and 3.1 stamina; integer ticks only."""

from blacksite.server.world.actors import Actor
from blacksite.server.world.zone import ZoneInstance

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
    if vector is None or actor.stance in ("down", "dead", "sleeper") or tick < actor.cooldowns.get("move", 0):
        return False
    target = actor.x + vector[0], actor.y + vector[1]
    if forced and (not zone.allows_hostile(actor.position) or not zone.allows_hostile(target)):
        return False
    if not zone.passable(target) or any(a.id != actor.id and a.position == target for a in zone.actors.values()):
        return False
    # A diagonal cannot bypass a closed corner or another player's body.
    if vector[0] and vector[1]:
        for side in ((actor.x + vector[0], actor.y), (actor.x, actor.y + vector[1])):
            if not zone.passable(side) or any(a.id != actor.id and a.position == side for a in zone.actors.values()):
                return False
    sprint = sprint and actor.stamina >= SPRINT_COST
    actor.x, actor.y = target
    actor.facing = name
    # Game design 3.1 / S12: excess carry weight doubles tile time.
    actor.cooldowns["move"] = tick + (SPRINT_TICKS if sprint else WALK_TICKS) * (2 if actor.overweight else 1)
    if sprint:
        actor.stamina -= SPRINT_COST
        actor.last_sprint_tick = tick
    zone.revision += 1
    return True


def regenerate(actor: Actor, elapsed: int, tick: int) -> bool:
    before = actor.stamina
    skipped = int(tick - elapsed < actor.last_sprint_tick <= tick)
    actor.stamina = min(actor.stamina_max, actor.stamina + max(0, elapsed - skipped) * STAMINA_REGEN)
    return actor.stamina != before
