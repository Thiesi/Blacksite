"""Game 12: durable, seeded event plans without I/O or wall-clock reads.

The adapter proposes on a fork and publishes it only after storage commits.
Forecasts and effect consumers read the same committed Plan. A late tick
reconciles expiry once, never replaying missed starts or reward waves.
"""

from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from random import Random
from typing import Any, Literal

from blacksite.content.schema import Effect, EventTemplate, Route
from blacksite.server.rules.events import (
    ADVANCE_SECONDS, MAX_RESERVED, ROLL_SECONDS, WARNING_SECONDS,
)

PlanState = Literal['planned', 'active', 'complete', 'cancelled']
TransitionKind = Literal['start', 'mid', 'end', 'cancel', 'warning']


@dataclass
class Plan:
    id: str
    template: str
    where: tuple[str, ...]
    announced_at: float
    starts_at: float
    ends_at: float
    seed: int
    variant_ids: tuple[str, ...] = ()
    state: PlanState = 'planned'
    revision: int = 1
    cancel_reason: str = ''
    reward_receipts: list[str] = field(default_factory=list)
    milestones: list[str] = field(default_factory=list)
    allocations: dict[str, Any] = field(default_factory=dict)
    forced: bool = False

    @property
    def live(self) -> bool:
        return self.state in ('planned', 'active')

    def claim(self, source: str) -> bool:
        """Reserve a reward/source in the enclosing proposal, once."""
        if self.state != 'active' or source in self.reward_receipts:
            return False
        self.reward_receipts.append(source)
        return True


@dataclass(frozen=True)
class Transition:
    plan: str
    kind: TransitionKind


class Scheduler:
    def __init__(self, origin: str, templates: Mapping[str, EventTemplate],
                 routes: Mapping[str, Route], saved: dict[str, Any] | None = None) -> None:
        self.origin, self.templates, self.routes = origin, templates, routes
        saved = saved or {}
        self.serial = int(saved.get('serial', 0))
        self.last_roll = saved.get('last_roll')
        self.cooldowns: dict[str, float] = dict(saved.get('cooldowns', {}))
        self.plans: dict[str, Plan] = {}
        for row in saved.get('plans', []):
            record = deepcopy(row)
            record['where'] = tuple(record['where'])
            record['variant_ids'] = tuple(record.get('variant_ids', ()))
            plan = Plan(**record)
            self.plans[plan.id] = plan
        self._live = {pid: plan for pid, plan in self.plans.items() if plan.live}

    def fork(self) -> 'Scheduler':
        draft = Scheduler(self.origin, self.templates, self.routes)
        draft.serial, draft.last_roll = self.serial, self.last_roll
        draft.cooldowns = dict(self.cooldowns)
        draft.plans = {pid: deepcopy(plan) if plan.live else plan for pid, plan in self.plans.items()}
        draft._live = {pid: draft.plans[pid] for pid in self._live}
        return draft

    def reserved(self) -> tuple[Plan, ...]:
        """Derived bounded index; persisted plans remain the only authority."""
        return tuple(self._live.values())

    def record(self) -> dict[str, Any]:
        return {'serial': self.serial, 'last_roll': self.last_roll,
                'cooldowns': dict(self.cooldowns),
                'plans': [asdict(plan) for plan in self.plans.values()]}

    def discard_unpublished(self, pid: str) -> None:
        """An unusable candidate consumes its roll, never a paid forecast."""
        if self.plans[pid].state != 'planned':
            raise ValueError('Only an unpublished candidate can be discarded.')
        self._live.pop(pid)
        del self.plans[pid]

    def effects(self, plan: Plan) -> tuple[Effect, ...]:
        template = self.templates[plan.template]
        selected = [effect for variant in template.variants if variant.id in plan.variant_ids
                    for effect in variant.effects]
        return tuple(effect for effect in (*template.effects, *selected)
                     if (not effect.zone or effect.zone in plan.where)
                     and (not effect.sector or effect.sector in plan.where))

    def scope(self, template: EventTemplate, where: tuple[str, ...]) -> set[str]:
        reserved = set(where)
        route = self.routes.get(template.route or '')
        if route:
            reserved.update(point.zone for point in route.waypoints)
        return reserved

    def choices(self, template: EventTemplate) -> tuple[tuple[str, ...], ...]:
        return (tuple((place,) for place in template.where)
                if template.selection == 'one' else (template.where,))

    def available(self, template: EventTemplate, now: float,
                  eligible: Callable[[EventTemplate, tuple[str, ...]], bool]) -> list[tuple[str, ...]]:
        reserved = self.reserved()
        if (len(reserved) >= MAX_RESERVED or self.cooldowns.get(template.id, 0) > now
                or any(plan.template == template.id for plan in reserved)):
            return []
        occupied = set().union(*(self.scope(self.templates[p.template], p.where) for p in reserved))
        return [where for where in self.choices(template)
                if eligible(template, where) and not (self.scope(template, where) & occupied)]

    def reserve(self, template: EventTemplate, now: float, seed: int,
                eligible: Callable[[EventTemplate, tuple[str, ...]], bool], *,
                forced: bool = False, where: tuple[str, ...] | None = None) -> Plan:
        choices = self.available(template, now, eligible)
        if where is not None:
            choices = [choice for choice in choices if choice == where]
        if not choices:
            raise ValueError('That event has no available commissioned scope.')
        rng = Random(seed)
        scope = rng.choice(choices)
        variants = [variant for variant in template.variants if all(
            (not effect.zone or effect.zone in scope) and (not effect.sector or effect.sector in scope)
            for effect in variant.effects)]
        chosen = (rng.choice(variants).id,) if variants else ()
        self.serial += 1
        warning = max((effect.warning_seconds for effect in template.effects), default=0)
        warning = max(warning, *(effect.warning_seconds for variant in template.variants
                                if variant.id in chosen for effect in variant.effects), WARNING_SECONDS)
        starts = now + (warning if forced else max(ADVANCE_SECONDS, warning))
        plan = Plan(f'{self.origin}:event:{self.serial}', template.id, scope, now,
                    starts, starts+template.duration_seconds, seed, chosen, forced=forced)
        self.plans[plan.id] = plan
        self._live[plan.id] = plan
        return plan

    def roll(self, now: float, eligible: Callable[[EventTemplate, tuple[str, ...]], bool],
             weights: Mapping[str, int] | None = None) -> Plan | None:
        slot = int(now // ROLL_SECONDS)
        if self.last_roll is not None and slot <= self.last_roll:
            return None
        self.last_roll = slot
        # Seed material is stable across Python processes and restarts.
        rng = Random(f'{self.origin}:events:{slot}:{self.serial}')
        candidates = sorted((template for template in self.templates.values()
                             if self.available(template, now, eligible)), key=lambda t: t.id)
        amounts = [max(0, (weights or {}).get(template.id, template.weight)) for template in candidates]
        if not candidates or not any(amounts):
            return None
        template = rng.choices(candidates, weights=amounts)[0]
        return self.reserve(template, now, rng.randrange(2**63), eligible)

    def cancel(self, pid: str, now: float, reason: str) -> Transition:
        plan = self.plans[pid]
        if not plan.live:
            raise ValueError('That plan is already closed.')
        if plan.state == 'active':
            self.cooldowns[plan.template] = now+self.templates[plan.template].cooldown_seconds
        plan.state, plan.cancel_reason = 'cancelled', reason
        self._live.pop(pid)
        plan.revision += 1
        return Transition(pid, 'cancel')

    def advance(self, now: float,
                eligible: Callable[[EventTemplate, tuple[str, ...]], bool]) -> list[Transition]:
        transitions: list[Transition] = []
        for plan in self.reserved():
            template = self.templates.get(plan.template)
            if (template is None or not eligible(template, plan.where)
                    or plan.where not in self.choices(template)
                    or not set(plan.variant_ids) <= {variant.id for variant in template.variants}):
                # Removed content cannot silently move a published plan.
                if template is None:
                    plan.state, plan.cancel_reason = 'cancelled', 'Event content is unavailable.'
                    self._live.pop(plan.id)
                    plan.revision += 1
                    transitions.append(Transition(plan.id, 'cancel'))
                else:
                    transitions.append(self.cancel(plan.id, now, 'The announced scope is unavailable.'))
                continue
            if now >= plan.ends_at:
                plan.state = 'complete'
                self._live.pop(plan.id)
                plan.revision += 1
                self.cooldowns[plan.template] = plan.ends_at+template.cooldown_seconds
                transitions.append(Transition(plan.id, 'end'))
                continue
            warning = max([WARNING_SECONDS, *(effect.warning_seconds for effect in self.effects(plan))])
            if now >= plan.starts_at-warning and 'warning' not in plan.milestones:
                plan.milestones.append('warning')
                transitions.append(Transition(plan.id, 'warning'))
            if now >= plan.starts_at and plan.state == 'planned':
                plan.state = 'active'
                plan.revision += 1
                transitions.append(Transition(plan.id, 'start'))
            if now >= (plan.starts_at+plan.ends_at)/2 and 'mid' not in plan.milestones:
                plan.milestones.append('mid')
                transitions.append(Transition(plan.id, 'mid'))
        return transitions

    def active(self, now: float) -> tuple[Plan, ...]:
        return tuple(plan for plan in self._live.values()
                     if plan.state == 'active' and plan.starts_at <= now < plan.ends_at)
