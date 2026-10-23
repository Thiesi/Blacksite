"""Game 7.7: explicit fare choices and durable, bound prepaid passages."""

from copy import deepcopy
from dataclasses import dataclass
from math import ceil
from typing import Any

from blacksite.content.schema import Exit
from blacksite.server.players import Player
from blacksite.server.sessions import Session
from blacksite.server.wake import menu
from blacksite.server.world.exits import complete_paid_pass, permitted, schedule

GATE_FARE = 25  # Game 7.7: optional fast outbound passage.
CABLE_FARE = 5
GATE_INTERVAL_SECONDS = 300
GATE_OPEN_SECONDS = 60


def gate_departure(now: float) -> float:
    return now if now % GATE_INTERVAL_SECONDS < GATE_OPEN_SECONDS else (
        int(now)//GATE_INTERVAL_SECONDS+1)*GATE_INTERVAL_SECONDS


@dataclass(frozen=True)
class Quote:
    cost: int
    source: str
    token: str = ''

    @property
    def row(self) -> str:
        return f'pass:{self.source}:{self.cost}:{self.token}'


class Passages:
    def __init__(self, owner: Any) -> None:
        self.owner = owner
        previous = owner.sim.fare_menu
        def offer(session: Session, exit: Exit) -> bool:
            if previous(session, exit):
                return True
            if not exit.relay:
                return False
            self.find(session, exit.id)
            from blacksite.server.relay_views import Panel
            owner.views.menus[session.id] = Panel(exit.relay, opened=owner.clock.now_tick(), route=exit.id)
            return True
        owner.sim.fare_menu = offer
        arrival = owner.sim.arrival_hook
        def arrived(session: Session, avatar: Any) -> None:
            player = owner.game.players.get(session.player_id)
            if player and complete_paid_pass(player.progress, avatar.zone):
                owner.game.snapshot(player, avatar)
                owner.game.queue('save', session.user_id, player, immediate=True)
            arrival(session, avatar)
        owner.sim.arrival_hook = arrived
        attached = owner.game.attached
        def on_attach(session: Session, player: Player) -> None:
            attached(session, player)
            if player.progress.get('paid_passes'):
                owner.log(player.id, 'Your prepaid passage remains saved. Inspect that route to use it.')
        owner.game.attached = on_attach

    def find(self, session: Session, eid: str) -> Exit:
        owner = self.owner
        if not owner.commerce.ready(session):
            raise ValueError('Return to the route with your body free to travel.')
        avatar = owner.sim.avatars[session.user_id]
        exit = next((e for e in owner.world.zones[avatar.zone].template.meta.exits if e.id == eid), None)
        if (not exit or exit.hidden or exit.target_zone not in owner.world.zones
                or max(abs(avatar.actor.x-exit.tile[0]), abs(avatar.actor.y-exit.tile[1])) > 1
                or (avatar.zone, exit.id) in owner.sim.locked_exits
                or not permitted(exit, owner.sim.access_provider(session))):
            raise ValueError('Stand beside this open route before choosing passage.')
        if exit.relay and not owner.active(exit.relay):
            raise ValueError('This passage has not been commissioned.')
        return exit

    def near(self, session: Session, eid: str) -> bool:
        try:
            self.find(session, eid)
            return True
        except ValueError:
            return False

    def key(self, session: Session, exit: Exit) -> str:
        return self.owner.sim.avatars[session.user_id].zone+':'+exit.id

    def quote(self, session: Session, exit: Exit) -> Quote:
        owner = self.owner
        player = owner.game.players[session.player_id]
        if player.faction and owner.owner(exit.relay) == player.faction:
            return Quote(0, 'member')
        paid = player.progress.get('paid_passes', {}).get(self.key(session, exit))
        if paid and paid['relay'] == exit.relay:
            return Quote(0, 'prepaid', paid['id'])
        return Quote(GATE_FARE if exit.kind == 'gate' else CABLE_FARE, 'purchase')

    def alternative(self, session: Session, exit: Exit) -> Exit | None:
        zone = self.owner.world.zones[self.owner.sim.avatars[session.user_id].zone]
        return next((e for e in zone.template.meta.exits if not e.relay and not e.hidden
            and e.target_zone == exit.target_zone and e.requirement is None
            and e.kind in ('ladder', 'street', 'door') and self.near(session, e.id)), None)

    def body(self, session: Session, eid: str) -> dict[str, Any]:
        exit = self.find(session, eid)
        quote = self.quote(session, exit)
        target = self.owner.world.zones[exit.target_zone].template.meta.name
        fast = exit.kind == 'gate'
        detail = (f'To {target}. Hand: {self.owner.game.players[session.player_id].chits_hand} chits.\n'
            f'{"Fast passage" if fast else "Cable ride"}: {quote.cost} chits ({quote.source}).\n'
            'A paid pass stays bound to this route until arrival, including through restart.\n')
        actions = [{'key':'f','label':f'{"fast" if fast else "ride"} {quote.cost} chits'}]
        if fast:
            wait = ceil(gate_departure(self.owner.now())-self.owner.now())
            detail += f'Ordinary gate: free; opens in {wait}s. Its public schedule does not change.'
            actions.append({'key':'e','label':'ordinary gate free'})
        else:
            detail += 'The free stair or ladder route remains available.'
            if self.alternative(session, exit):
                actions.append({'key':'s','label':'free stairs'})
        body = menu('PASSAGE', [{'id':quote.row,'cells':[target, str(quote.cost)+' chits']}], 0, detail,
                    'Choose the displayed route  Esc/B closes without payment')
        body['actions'] = actions
        return body

    def choose(self, session: Session, eid: str, row: str, action: str) -> bool:
        owner = self.owner
        exit = self.find(session, eid)
        if action == 'e' and exit.kind == 'gate':
            self.begin(session, exit.id, fast=False)
            return True
        if action == 's' and exit.kind == 'cable' and (alternative := self.alternative(session, exit)):
            self.begin(session, alternative.id, fast=False)
            return True
        if action != 'f':
            return False
        def execute() -> bool:
            try:
                current = self.find(session, eid)
                quote = self.quote(session, current)
                if row != quote.row:
                    raise ValueError('The passage quote changed. Inspect it again before payment.')
                player = owner.game.players[session.player_id]
                if player.chits_hand < quote.cost:
                    raise ValueError('You do not have enough chits for that passage. The free route remains.')
                if quote.cost == 0:
                    self.begin(session, eid, fast=True, token=quote.token)
                    return True
                owner.game.snapshot(player, owner.sim.avatars[session.user_id])
                progress = deepcopy(player.progress)
                serial = progress.get('travel_serial', 0)+1
                progress['travel_serial'] = serial
                token = f'{player.id}:pass:{serial}'
                progress.setdefault('paid_passes', {})[self.key(session, current)] = {
                    'id': token, 'relay': current.relay, 'target': current.target_zone, 'paid': quote.cost}
                def finished(success: bool) -> None:
                    if not success:
                        owner.log(player.id, 'Passage could not be saved. You pay nothing.')
                        return
                    try:
                        self.begin(session, eid, fast=True, token=token)
                    except ValueError:
                        owner.log(player.id, 'Your paid pass is saved. Return to the route to use it.')
                if not owner.commerce.settle(player, {'chits_hand': player.chits_hand-quote.cost, 'progress': progress},
                        owner.commerce.items, owner.commerce.caches, owner.commerce.serial, finished):
                    raise ValueError('The passage is busy. Try again.')
                return True
            except ValueError as exc:
                owner.log(session.player_id, str(exc))
                return False
        if owner.commerce.pending:
            owner.commerce.enqueue_system(execute)
            return True
        return execute()

    def begin(self, session: Session, eid: str, *, fast: bool, token: str = '') -> None:
        owner = self.owner
        exit = self.find(session, eid)
        avatar = owner.sim.avatars[session.user_id]
        if token:
            owner.game.players[session.player_id].progress['paid_trip'] = {
                'key': self.key(session, exit), 'token': token, 'target': exit.target_zone}
        owner.cancel_hold(session.player_id)
        owner.views.close(session)
        now = owner.now()
        avatar.travel = schedule(exit, now)
        if exit.kind == 'gate' and exit.relay and not fast:
            avatar.travel.departure = avatar.travel.arrival = gate_departure(now)
        owner.sim.reset_view(session, avatar)
        owner.sim.transition(session, avatar, now, owner.clock.now_tick())
        if token and avatar.travel and avatar.travel.departed:
            player = owner.game.players[session.player_id]
            owner.game.snapshot(player, avatar)
            owner.game.queue('save', session.user_id, player, immediate=True)
