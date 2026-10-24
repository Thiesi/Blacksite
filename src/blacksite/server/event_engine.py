"""Game 12 adapter: commit plans before forecasts or live effects exist."""

from collections.abc import Callable, Iterator
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
from random import Random
from typing import Any, Literal

from blacksite.content.schema import Effect, EventTemplate, Exit, HymnTemplate
from blacksite.server.clock import TICK_HZ
from blacksite.server.event_effects import beneficial
from blacksite.server.events import Plan, Scheduler, Transition
from blacksite.server.factions import EventOffer, perk
from blacksite.server.loop import TickContext
from blacksite.server.players import Player
from blacksite.server.protocol import Frame
from blacksite.server.rules.events import (
    ADVANCE_SECONDS, CURFEW_HEAT, ROLL_SECONDS, SURGE_MAGNITUDE, WARNING_SECONDS,
)
from blacksite.server.sessions import Session

TuningKind = Literal['weight', 'spawn_rate', 'wave_cap_bonus', 'surge_variants']


class Events:
    def __init__(self, core: Any, saved: dict[str, Any]) -> None:
        self.core, self.game, self.commerce = core, core.characters, core.commerce
        self.content, self.clock = self.commerce.content, core.clock
        self.world, self.sim, self.lat = self.game.world, self.game.sim, core.lattice
        self.scheduler = Scheduler(core.sessions.origin, self.content.events, self.content.routes, saved)
        self.last_tick = -TICK_HZ
        self.warning_until: dict[str, int] = {}
        # S26 supplies typed, bounded values from its committed season state.
        self.tuning: Callable[[str, TuningKind], float | bool | None] = lambda event, kind: None
        from blacksite.server.event_world import WorldEffects
        self.effects = WorldEffects(self)
        self.game.events = self
        self.bind()
        # Reconcile before the listener opens. Server._character_writes commits
        # this source during startup; expired effects are never installed.
        self.process(reconcile=True)
        self.refresh()

    def now(self) -> float:
        return self.clock.now_utc().timestamp()

    def number(self, event: str, kind: TuningKind, default: float,
               minimum: float, maximum: float) -> float:
        value = self.tuning(event, kind)
        return max(minimum, min(maximum, float(value))) if type(value) in (int, float) else default

    def eligible(self, template: EventTemplate, where: tuple[str, ...]) -> bool:
        if not self.content.active('events', template.id) or template.basis != 'wall':
            return False
        if not all(place in self.world.zones or place in self.content.sectors for place in where):
            return False
        route = self.content.routes.get(template.route or '')
        return not template.route or bool(route and self.content.active('routes', route.id)
            and all(point.zone in self.world.zones for point in route.waypoints))

    def active(self) -> tuple[Plan, ...]:
        return tuple(plan for plan in self.scheduler.active(self.now())
                     if plan.template in self.content.events
                     and self.eligible(self.content.events[plan.template], plan.where)
                     and self.clock.now_tick() >= self.warning_until.get(plan.id, 0))

    def each(self, kind: str) -> Iterator[tuple[Plan, Effect]]:
        for plan in self.active():
            for effect in self.scheduler.effects(plan):
                if effect.type == kind:
                    until = plan.starts_at+float(effect.params.get('seconds', plan.ends_at-plan.starts_at))
                    if self.now() < min(plan.ends_at, until):
                        yield plan, effect

    def curfew(self, zone: str) -> bool:
        # The entry boundary is Core-only; relay pause and new Warden heat
        # are city-wide consequences of the same committed event.
        return any(self.each('relay_pause'))

    def bind(self) -> None:
        before = self.core.factions.curfew
        self.core.factions.curfew = lambda zone: before(zone) or self.curfew(zone)
        self.core.factions.preview = self.preview
        self.core.progression.surge_preview = self.surge_preview
        old_active = self.core.contracts.event_active
        self.core.contracts.event_active = lambda eid: old_active(eid) or any(
            plan.template == eid or plan.id == eid for plan in self.active())
        previous = self.sim.travel_refusal
        self.sim.travel_refusal = lambda session, exit: previous(session, exit) or self.travel_refusal(session, exit)
        ability = self.core.combat.ability_effect
        def effect(player: Player, hymn: HymnTemplate) -> dict[str, Any]:
            base = ability(player, hymn)
            if player.archetype == 'cantor' and hymn.kind == 'hymn' and any(self.each('ability_magnitude')):
                return beneficial(base, SURGE_MAGNITUDE)
            return base
        self.core.combat.ability_effect = effect
        self.effects.bind()

    def travel_refusal(self, session: Session, exit: Exit) -> str | None:
        avatar = self.sim.avatars.get(session.user_id)
        player = self.game.players.get(session.player_id)
        if not avatar or not player:
            return None
        for plan, effect in self.each('entry_restriction'):
            if exit.target_zone not in plan.where or avatar.zone in plan.where:
                continue
            actor = avatar.actor
            now = self.now()
            marked = actor.marked or bool(player.marked_until and
                datetime.fromisoformat(player.marked_until).timestamp() > now)
            passes = [self.commerce.items[iid] for iid in player.inventory
                      if iid in self.commerce.items and self.commerce.items[iid].template == 'key_curfew_pass'
                      and self.commerce.items[iid].owner == player.id]
            if not marked and any(self.effects.pass_valid(item, now) for item in passes):
                continue
            return 'Curfew restricts inbound Core entry. Outward routes and other public shelters remain open.'
        for plan, effect in self.each('route_hold'):
            if f'{avatar.zone}/{exit.id}' in effect.exits_closed:
                return 'The event holds this optional route. Follow the other public exit.'
        return None

    def text(self, plan: Plan, *, detailed: bool = False) -> str:
        template = self.content.events.get(plan.template)
        name = template.name if template else plan.template
        when = datetime.fromtimestamp(plan.starts_at, timezone.utc).strftime('%H:%M UTC')
        scope = ', '.join(plan.where)
        if plan.template == 'ring-fall' and not detailed and self.now() < plan.starts_at-WARNING_SECONDS:
            scope = 'ring named by chart; impact warnings remain public'
        variants = ''
        if detailed and plan.variant_ids:
            variants = ' Variants: '+', '.join(plan.variant_ids)+'.'
        correction = ' '+plan.cancel_reason if plan.cancel_reason else ''
        return f'{name}: {plan.state}, {when}, {scope}. Plan {plan.id} r{plan.revision}.{variants}{correction}'

    def preview(self, player: Player, faction: str) -> EventOffer | None:
        if faction not in ('kestrel', 'choir', 'ferrymen') or not perk(player, faction):
            return None
        kind = {'kestrel': 'convoy', 'choir': 'choir-surge', 'ferrymen': 'ring-fall'}[faction]
        plans = sorted((plan for plan in self.scheduler.plans.values()
                        if plan.template == kind and plan.live and plan.ends_at > self.now()),
                       key=lambda plan: (plan.starts_at, plan.id))
        if not plans:
            return None
        plan = plans[0]
        return EventOffer(plan.id, self.text(plan, detailed=True), plan.revision)

    def surge_preview(self, player: Player) -> str | None:
        plans = sorted((plan for plan in self.scheduler.plans.values()
                        if plan.template == 'choir-surge' and plan.live and plan.ends_at > self.now()),
                       key=lambda plan: plan.starts_at)
        return self.text(plans[0], detailed=True) if plans else None

    def notify(self, text: str, *, warning: bool = False) -> None:
        for session in self.core.sessions.active.values():
            if session.closed or session.role != 'caller':
                continue
            session.send(Frame('log', {'lines': [{'channel': 'system', 'text': text,
                'role': 'chan_sys', 'at': self.clock.now_utc().isoformat()}]}))
            if warning:
                session.send(Frame('toast', {'text': text, 'role': 'ui_warn', 'seconds': 5}))

    def announce(self, transition: Transition) -> None:
        plan = self.scheduler.plans[transition.plan]
        template = self.content.events.get(plan.template)
        if transition.kind in ('warning', 'cancel') or template is None:
            self.notify(self.text(plan, detailed=True), warning=True)
            return
        asset = self.content.text.get(getattr(template.announce, transition.kind, '') or '')
        if asset:
            self.notify(asset.body.format(name=template.name, where=', '.join(plan.where),
                plan=plan.id, remaining=max(0, int(plan.ends_at-self.now())),
                route=template.route or '', time=datetime.fromtimestamp(plan.starts_at, timezone.utc).isoformat()))

    def write(self, draft: Scheduler, transitions: list[Transition],
              after: Callable[[bool], None] = lambda success: None) -> bool:
        proposal = self.effects.stage(draft, transitions)
        def finished(success: bool) -> None:
            if success:
                self.scheduler = draft
                for transition in transitions:
                    if transition.kind == 'warning':
                        plan = draft.plans[transition.plan]
                        seconds = max([WARNING_SECONDS, *(effect.warning_seconds
                            for effect in draft.effects(plan))])
                        self.warning_until[plan.id] = self.clock.now_tick()+seconds*TICK_HZ
                self.effects.install(proposal)
                self.refresh()
                for transition in transitions:
                    self.announce(transition)
            after(success)
        accepted = self.commerce.settle(None, {}, proposal.items, proposal.caches, proposal.serial, finished)
        if accepted:
            effect = self.commerce.outbox[-1]
            effect['events_state'] = draft.record()
            if proposal.salvage is not None:
                effect['salvage_state'] = proposal.salvage
        return accepted

    def process(self, *, reconcile: bool = False) -> None:
        if self.commerce.pending:
            return
        now = self.now()
        live = [plan for plan in self.scheduler.plans.values() if plan.live]
        deadlines = [value for plan in live for value in (
            plan.starts_at-max([WARNING_SECONDS, *(effect.warning_seconds for effect in
                self.scheduler.effects(plan))]) if 'warning' not in plan.milestones
                and plan.template in self.content.events else plan.ends_at,
            plan.starts_at if plan.state == 'planned' else plan.ends_at,
            (plan.starts_at+plan.ends_at)/2 if 'mid' not in plan.milestones else plan.ends_at,
            plan.ends_at)]
        if (not reconcile and self.scheduler.last_roll == int(now//ROLL_SECONDS)
                and (not deadlines or min(deadlines) > now)):
            return
        draft = self.scheduler.fork()
        transitions = draft.advance(now, self.eligible)
        weights = {template.id: int(self.number(template.id, 'weight', template.weight, 1, 10))
                   for template in self.content.events.values()}
        plan = draft.roll(now, self.eligible, weights)
        if plan:
            self.effects.allocate(draft, plan)
        if draft.record() != self.scheduler.record():
            self.write(draft, transitions)

    def refresh(self) -> None:
        active = {plan.template for plan in self.active()}
        self.lat.events = active
        self.core.npcs.spawners.enabled_events = active
        self.effects.refresh()

    def admin(self, command: str, args: dict[str, Any], reply: Callable[[Any], None]) -> None:
        if command == 'event.list':
            page = args.get('page', 1)
            if type(page) is not int or page < 1:
                reply({'ok': False, 'error': 'Choose a positive page.'})
                return
            plans = sorted(self.scheduler.plans.values(), key=lambda plan: plan.starts_at, reverse=True)
            pages = max(1, (len(plans)+99)//100)
            reply({'ok': True, 'plans': [asdict(plan) for plan in plans[(page-1)*100:page*100]],
                   'page': page, 'pages': pages, 'total': len(plans)})
            return
        def execute() -> None:
            try:
                draft = self.scheduler.fork()
                now = self.now()
                transitions = draft.advance(now, self.eligible)
                if command == 'event.force':
                    template = self.content.events.get(args.get('event'))
                    if template is None:
                        raise ValueError('Choose an authored event.')
                    seed = Random(f'{self.core.sessions.origin}:force:{now}:{draft.serial}').randrange(2**63)
                    plan = draft.reserve(template, now, seed, self.eligible, forced=True,
                        where=(args['where'],) if args.get('where') else None)
                    self.effects.allocate(draft, plan)
                    transitions.extend(draft.advance(now, self.eligible))
                elif command == 'event.cancel':
                    pid = args.get('plan')
                    if pid not in draft.plans:
                        raise ValueError('Choose a committed plan.')
                    transitions.append(draft.cancel(pid, now, 'Operator cancellation.'))
                    plan = draft.plans[pid]
                else:
                    raise ValueError('Unknown event command.')
                if not self.write(draft, transitions, lambda success: reply(
                        {'ok': success, 'plan': asdict(plan)} if success else
                        {'ok': False, 'error': 'The event could not be saved. Nothing changes.'})):
                    raise ValueError('The city is busy. Try again.')
            except ValueError as exc:
                reply({'ok': False, 'error': str(exc)})
        self.commerce.enqueue_system(execute)

    def tick(self, ctx: TickContext) -> None:
        if ctx.tick-self.last_tick < TICK_HZ:
            return
        self.last_tick = ctx.tick
        self.process()
        self.refresh()
