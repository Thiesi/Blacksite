"""Round 4 demo posts, errands and atomic swaps; one budget for all steps.

The simulation supplies actors, seeded zone RNG and ticks. Holding consumes
neither movement work nor RNG. Hunt/flee/watch remain the ordinary NPC rules.
"""

from collections import deque
from typing import TYPE_CHECKING

from karst41.content.schema import Post, Tile
from karst41.server.clock import TICK_HZ
from karst41.server.world.actors import Actor
from karst41.server.world.movement import move
from karst41.server.world.zone import ZoneInstance

if TYPE_CHECKING:
    from karst41.server.npcs.engine import Npcs


class Posts:
    def __init__(self, npcs: 'Npcs') -> None:
        self.npcs = npcs
        self.ledger: dict[str, tuple[int, set[str]]] = {}

    @staticmethod
    def ordinary(actor: Actor) -> bool:
        return bool(actor.behaviour.get('posts') and actor.health > 0
                    and actor.stance not in ('down', 'dead')
                    and actor.behaviour.get('state') not in ('hunt', 'flee'))

    def reserved_ids(self, zone: ZoneInstance, tick: int) -> set[str]:
        """Union of live trip reservations and this tick's accepted movements."""
        active = {a.id for a in zone.actors.values()
                  if self.ordinary(a) and a.behaviour.get('post_trip')}
        previous_tick, accepted = self.ledger.get(zone.id, (-1, set()))
        accepted = accepted if previous_tick == tick else set()
        self.ledger[zone.id] = tick, accepted
        return active | accepted

    def can_reserve(self, zone: ZoneInstance, tick: int, actors: tuple[Actor, ...],
                    *, swap: bool = False) -> bool:
        ids = self.reserved_ids(zone, tick) | {a.id for a in actors}
        if len(ids) > zone.template.meta.moving_budget:
            return False
        for actor in actors:
            crowd = actor.behaviour['post_crowd']
            members = {a.id for a in zone.actors.values()
                       if a.behaviour.get('post_crowd') == crowd}
            cap = 2 if swap else int(actor.behaviour['post_cap'])
            if len(ids & members) > cap:
                return False
        return True

    def reserve(self, zone: ZoneInstance, tick: int, actors: tuple[Actor, ...],
                *, swap: bool = False) -> bool:
        if not self.can_reserve(zone, tick, actors, swap=swap):
            return False
        self.ledger[zone.id][1].update(a.id for a in actors)
        return True

    @staticmethod
    def home(actor: Actor) -> Tile:
        return tuple(actor.behaviour['home'])

    @staticmethod
    def post_at(actor: Actor, tile: Tile) -> Post | None:
        return next((p for p in actor.behaviour['posts'] if p.tile == tile), None)

    def hold(self, actor: Actor, zone: ZoneInstance, tick: int) -> None:
        post = self.post_at(actor, actor.position) or self.post_at(actor, self.home(actor))
        actor.behaviour['post_until'] = tick + zone.rng.randint(*post.hold_seconds) * TICK_HZ
        actor.behaviour['post_trip'] = False
        actor.behaviour.pop('post_path', None)
        actor.behaviour.pop('post_goal', None)

    def interrupt(self, actor: Actor) -> None:
        """A real reaction cancels the errand, without changing home ownership."""
        if actor.behaviour.get('posts'):
            partner = self.npcs.world.actors.get(actor.behaviour.pop('post_swap_partner', None))
            if partner:
                partner.behaviour.pop('post_wait', None)
            actor.behaviour.update(post_trip=False, post_until=0)
            actor.behaviour.pop('post_goal', None)
            actor.behaviour.pop('post_path', None)
            actor.behaviour.pop('post_swap_final', None)
            actor.behaviour.pop('post_wait', None)

    def free(self, actor: Actor, zone: ZoneInstance, tile: Tile) -> bool:
        return not any(a.id != actor.id and (a.position == tile
            or a.behaviour.get('posts') and (self.home(a) == tile
                or a.behaviour.get('post_trip') and a.behaviour.get('post_goal') == tile))
            for a in zone.actors.values() if not a.behaviour.get('training'))

    def route(self, actor: Actor, zone: ZoneInstance, goal: Tile, avoid: set[Tile]) -> list[Tile]:
        """Plan this authored trip; don't alter hunt/guard/#187 navigation."""
        occupied = {a.position for a in zone.actors.values()
                    if a.id != actor.id and not a.behaviour.get('training')}
        partner = zone.actors.get(actor.behaviour.get('post_swap_partner'))
        if partner and partner.position == goal:
            occupied.discard(goal)  # Staggered partner vacates before our last step.
        blocked = occupied | avoid
        pending = deque([actor.position])
        before: dict[Tile, Tile | None] = {actor.position: None}
        while pending:
            x, y = pending.popleft()
            for tile in ((x + 1, y), (x, y + 1), (x - 1, y), (x, y - 1)):
                if (tile in before or tile in blocked or not zone.can_enter(actor, tile)
                        or zone.tiles[zone.tile_id(tile)].hazard):
                    continue
                before[tile] = (x, y)
                if tile == goal:
                    path = [tile]
                    while before[path[-1]] != actor.position:
                        path.append(before[path[-1]])
                    return list(reversed(path))
                pending.append(tile)
        return []

    def walk(self, actor: Actor, zone: ZoneInstance, tick: int, avoid: set[Tile],
             *, ignore_holder: Tile | None = None) -> None:
        if waiting := actor.behaviour.get('post_wait'):
            leader = zone.actors.get(waiting)
            if leader and self.ordinary(leader) and leader.behaviour.get('post_trip'):
                return
            actor.behaviour.pop('post_wait', None)
        if actor.position == actor.behaviour['post_goal']:
            self.arrive(actor, zone, tick)
            return
        if (tick < actor.cooldowns.get('move', 0) or tick < actor.behaviour.get('post_retry', 0)
                or any(tile != ignore_holder for tile in self.npcs.reach_holders(actor, zone, tick))):
            return
        goal = actor.behaviour['post_goal']
        path = actor.behaviour.get('post_path', [])
        occupied = {a.position for a in zone.actors.values()
                    if a.id != actor.id and not a.behaviour.get('training')}
        if (not path or path[0] in occupied or not zone.can_enter(actor, path[0])
                or actor.behaviour.get('post_geometry') != zone.geometry_revision):
            path = self.route(actor, zone, goal, avoid)
            actor.behaviour.update(post_path=path, post_geometry=zone.geometry_revision)
        if not path:
            actor.behaviour['post_retry'] = tick + TICK_HZ
            return
        dx, dy = path[0][0] - actor.x, path[0][1] - actor.y
        direction = {(1, 0): 'right', (-1, 0): 'left', (0, 1): 'down', (0, -1): 'up'}.get((dx, dy))
        if direction and move(actor, zone, direction, tick):
            self.reserved_ids(zone, tick)
            self.ledger[zone.id][1].add(actor.id)
            path.pop(0)
        else:
            actor.behaviour.pop('post_path', None)
        if actor.position == goal:
            self.arrive(actor, zone, tick)

    def arrive(self, actor: Actor, zone: ZoneInstance, tick: int) -> None:
        if final := actor.behaviour.pop('post_swap_final', None):
            partner = zone.actors.get(actor.behaviour.get('post_swap_partner'))
            if partner:
                partner.behaviour.pop('post_wait', None)
            self.start(actor, final)
        else:
            actor.behaviour.pop('post_swap_partner', None)
            self.hold(actor, zone, tick)

    def start(self, actor: Actor, goal: Tile) -> None:
        actor.behaviour.update(post_goal=goal, post_trip=True, post_retry=0)
        actor.behaviour.pop('post_path', None)

    def act(self, actor: Actor, zone: ZoneInstance, tick: int, avoid: set[Tile]) -> bool:
        if not actor.behaviour.get('posts'):
            return False
        if seen := actor.behaviour.get('post_shied'):
            seen.intersection_update(a.id for a in zone.actors.values() if a.behaviour.get('drawn'))
        if actor.behaviour.get('post_trip'):
            self.walk(actor, zone, tick, avoid)
            return True
        if actor.position == self.home(actor) and all(p.home and not p.swap for p in actor.behaviour['posts']):
            return True  # Fixed extras do no scheduling, budget scan or RNG work.
        if 'post_until' not in actor.behaviour:
            if actor.position == self.home(actor):
                self.hold(actor, zone, tick)
            else:
                actor.behaviour['post_until'] = 0
        if tick < actor.behaviour['post_until'] or self.npcs.reach_holders(actor, zone, tick):
            return True
        if actor.position != self.home(actor):
            if self.reserve(zone, tick, (actor,)):
                self.start(actor, self.home(actor))
                self.walk(actor, zone, tick, avoid)
            return True
        if not self.can_reserve(zone, tick, (actor,)):
            return True
        choices: list[tuple[Post, Actor | None]] = [
            (p, None) for p in actor.behaviour['posts'] if not p.home and self.free(actor, zone, p.tile)]
        own = self.post_at(actor, self.home(actor))
        if own.swap and own.seated:
            for partner in zone.actors.values():
                if (partner is actor or not self.ordinary(partner)
                        or partner.behaviour['post_crowd'] != actor.behaviour['post_crowd']
                        or partner.behaviour.get('post_trip') or partner.position != self.home(partner)
                        or self.npcs.reach_holders(partner, zone, tick)):
                    continue
                other = self.post_at(partner, partner.position)
                if other.swap and not other.seated and self.can_reserve(zone, tick, (actor, partner), swap=True):
                    choices.append((Post(other.tile, other.hold_seconds, weight=30), partner))
        if not choices:
            return True
        # A swap and a free doorway errand share the authored doorway weight,
        # rather than doubling its 30 against counter 50 / table 20.
        doorways = sum(p.weight == 30 for p, _ in choices) if any(a for _, a in choices) else 1
        weights = [p.weight / doorways if p.weight == 30 else p.weight for p, _ in choices]
        post, partner = zone.rng.choices(choices, weights=weights)[0]
        if partner is not None:
            # Clear the one-tile door before the other person starts. The
            # drinker waits one tile beside the street approach, then takes
            # its doorway home once the partner has vacated it.
            actor.behaviour['post_swap_partner'] = partner.id
            route = self.route(actor, zone, partner.position, avoid)
            actor.behaviour.pop('post_swap_partner')
            if len(route) < 2:
                return True
            approach = route[-2]
            staging = next((tile for tile in ((approach[0], approach[1]+1),
                (approach[0]+1, approach[1]), (approach[0]-1, approach[1]),
                (approach[0], approach[1]-1)) if tile not in route[-3:]
                and tile not in avoid and zone.can_enter(actor, tile)
                and not zone.tiles[zone.tile_id(tile)].hazard and self.free(actor, zone, tile)), None)
            if staging is None:
                return True
            if self.reserve(zone, tick, (actor, partner), swap=True):
                actor.behaviour['home'], partner.behaviour['home'] = self.home(partner), self.home(actor)
                self.start(actor, staging)
                self.start(partner, self.home(partner))
                actor.behaviour['post_swap_partner'] = partner.id
                actor.behaviour['post_swap_final'] = self.home(actor)
                partner.behaviour['post_wait'] = actor.id
        elif self.reserve(zone, tick, (actor,)):
            self.start(actor, post.tile)
        if actor.behaviour.get('post_trip'):
            self.walk(actor, zone, tick, avoid)
        return True

    def shy(self, actor: Actor, zone: ZoneInstance, tick: int, drawer: Actor, avoid: set[Tile]) -> bool:
        """Drawn hook's only entry: use the ordinary-trip ledger for shy steps."""
        if not actor.behaviour.get('posts'):
            return False
        own = self.post_at(actor, actor.position)
        if own and own.seated:
            return True
        if actor.behaviour.get('post_trip') or own and not own.home:
            actor.behaviour.setdefault('post_shied', set()).add(drawer.id)
            if actor.behaviour.get('post_goal') != self.home(actor) or actor.behaviour.get('post_swap_final'):
                self.interrupt(actor)
                self.start(actor, self.home(actor))
            if self.reserve(zone, tick, (actor,)):
                self.walk(actor, zone, tick, avoid, ignore_holder=drawer.position)
            else:
                actor.behaviour['post_trip'] = False
            return True
        seen = actor.behaviour.setdefault('post_shied', set())
        seen.intersection_update(a.id for a in zone.actors.values() if a.behaviour.get('drawn'))
        if drawer.id in seen or any(tile != drawer.position for tile in self.npcs.reach_holders(actor, zone, tick)):
            return True
        distance = lambda tile: max(abs(tile[0] - drawer.x), abs(tile[1] - drawer.y))
        options = [(actor.x + 1, actor.y), (actor.x, actor.y + 1),
                   (actor.x - 1, actor.y), (actor.x, actor.y - 1)]
        options.sort(key=lambda tile: (-distance(tile), tile))
        for tile in options:
            if (distance(tile) <= distance(actor.position) or tile in avoid
                    or not zone.can_enter(actor, tile) or zone.tiles[zone.tile_id(tile)].hazard
                    or not self.free(actor, zone, tile)):
                continue
            if tick < actor.cooldowns.get('move', 0) or not self.reserve(zone, tick, (actor,)):
                return True
            direction = {(1, 0): 'right', (-1, 0): 'left', (0, 1): 'down', (0, -1): 'up'}[
                tile[0] - actor.x, tile[1] - actor.y]
            if move(actor, zone, direction, tick):
                seen.add(drawer.id)
                self.hold(actor, zone, tick)
            return True
        return True
