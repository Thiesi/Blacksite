"""Game 9: deterministic contract drafts; no I/O or clock reads.

The owning adapter forks this state, joins its record to the source
transaction and installs the draft only after that transaction commits.
Facts come from verified server actions, never directly from a frame.
"""

from collections import Counter
from copy import deepcopy
from dataclasses import asdict, dataclass, field, replace
from fractions import Fraction
from math import ceil
from random import Random
from typing import Any, Iterable, Mapping
import json

from blacksite.content.schema import (
    ContractTemplate, Permit, Reward, Stage, StageTarget,
)
from blacksite.server.crews import CREW_MAX

BOARD_OFFERS = 5  # Game 9.1.
BOARD_SECONDS = 30 * 60
GENERATED_SECONDS = 60 * 60
ACTIVE_GENERATED = 3
OBJECTIVE_INCREMENT = Fraction(1, 2)
REWARD_INCREMENT = Fraction(1, 4)
OPERATOR_CHITS = Fraction(11, 10)  # Game 3.2 and 9.1, applied last.


def objective_count(base: int, size: int, scaling: bool = True) -> int:
    if base < 1 or not 1 <= size <= CREW_MAX:
        raise ValueError('A job needs positive targets and one to five participants.')
    return ceil(base * (1 + OBJECTIVE_INCREMENT * (size - 1))) if scaling else base


def target_record(raw: dict[str, Any]) -> StageTarget:
    data = dict(raw)
    if data.get('tile') is not None:
        data['tile'] = tuple(data['tile'])
    return StageTarget(**data)


def stage_record(raw: dict[str, Any]) -> Stage:
    return Stage(**{**raw, 'target': target_record(raw['target']),
                    'destination': target_record(raw['destination']) if raw.get('destination') else None,
                    'linked_control': target_record(raw['linked_control']) if raw.get('linked_control') else None,
                    'target_pool': tuple(target_record(t) for t in raw.get('target_pool', ()))})


def permit_record(raw: dict[str, Any] | None) -> Permit | None:
    if raw is None:
        return None
    return Permit(**{**raw, 'binding': target_record(raw['binding']) if raw.get('binding') else None})


def target_key(target: StageTarget) -> str:
    return json.dumps({key: value for key, value in asdict(target).items() if value is not None},
                      sort_keys=True, separators=(',', ':'))


def matches(expected: StageTarget, actual: StageTarget) -> bool:
    return all(value is None or value == getattr(actual, name)
               for name, value in asdict(expected).items() if name != 'tile') and (
                   expected.tile is None or expected.tile == actual.tile)


@dataclass(frozen=True)
class Participant:
    player: str
    identity: str
    grade: int = 1
    archetype: str = 'ghost'
    rewardable: bool = True


@dataclass(frozen=True)
class Payment:
    chits: int
    xp: int
    standing: dict[str, int]
    standing_mode: str
    items: tuple[str, ...] = ()
    programs: tuple[str, ...] = ()

    @classmethod
    def roll(cls, reward: Reward, rng: Random) -> 'Payment':
        return cls(rng.randint(*reward.chits), reward.xp, dict(reward.standing),
                   reward.standing_mode, (rng.choice(reward.items),) if reward.items else (),
                   reward.programs)

    @classmethod
    def read(cls, row: dict[str, Any]) -> 'Payment':
        return cls(**{**row, 'items': tuple(row.get('items', ())),
                      'programs': tuple(row.get('programs', ()))})

    def scaled(self, size: int, scaling: bool, operator: bool = False) -> 'Payment':
        factor = 1 + REWARD_INCREMENT * (size - 1) if scaling else Fraction(1)
        chits = int(self.chits * factor)
        if operator:
            chits = int(chits * OPERATOR_CHITS)
        return replace(self, chits=chits, xp=int(self.xp * factor),
                       standing={key: int(value * factor) for key, value in self.standing.items()})


@dataclass(frozen=True)
class Offer:
    id: str
    template: str
    until: float | None
    reward: Payment
    options: dict[str, dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def read(cls, row: dict[str, Any]) -> 'Offer':
        return cls(**{**row, 'reward': Payment.read(row['reward'])})


@dataclass(frozen=True)
class Fact:
    actor: str
    verb: str
    completion: str
    target: StageTarget
    subject: str
    receipt: str
    instance: str | None = None
    stage: str = ''
    attempt: int = 0
    quantity: int = 1
    resolution: str | None = None
    contributors: tuple[str, ...] = ()
    failure: str = ''


@dataclass
class Progress:
    stage: Stage
    targets: tuple[StageTarget, ...]
    attempt: int = 0
    counts: dict[str, int] = field(default_factory=dict)
    receipts: set[str] = field(default_factory=set)
    subjects: set[str] = field(default_factory=set)
    started_at: float | None = None

    def window_closed(self, now: float) -> bool:
        return bool(self.stage.window_seconds and self.started_at is not None
                    and now >= self.started_at+self.stage.window_seconds)

    @property
    def complete(self) -> bool:
        return sum(self.counts.values()) >= len(self.targets)

    def accept(self, fact: Fact) -> bool:
        if (fact.attempt != self.attempt or not fact.receipt or not fact.subject
                or fact.receipt in self.receipts or fact.subject in self.subjects
                or fact.quantity < 1 or fact.target.kind != 'item' and fact.quantity != 1):
            return False
        quotas = Counter(target_key(t) for t in self.targets)
        target = next((t for t in self.targets if matches(t, fact.target)
                       and self.counts.get(target_key(t), 0) < quotas[target_key(t)]), None)
        if target is None:
            return False
        key = target_key(target)
        self.counts[key] = self.counts.get(key, 0) + min(
            fact.quantity, quotas[key] - self.counts.get(key, 0))
        self.receipts.add(fact.receipt)
        self.subjects.add(fact.subject)
        return True

    def record(self) -> dict[str, Any]:
        return {**asdict(self), 'receipts': sorted(self.receipts), 'subjects': sorted(self.subjects)}

    @classmethod
    def read(cls, row: dict[str, Any]) -> 'Progress':
        return cls(**{**row, 'stage': stage_record(row['stage']),
                      'targets': tuple(target_record(t) for t in row['targets']),
                      'receipts': set(row['receipts']), 'subjects': set(row['subjects'])})


@dataclass
class Instance:
    id: str
    offer: str
    template: str
    giver: str
    roster: tuple[Participant, ...]
    stages: tuple[Progress, ...]
    reward: Payment
    accepted_at: float
    expires_at: float | None
    story: bool = False
    scaling: bool = True
    approach: str = 'default'
    params: dict[str, Any] = field(default_factory=dict)
    options: dict[str, dict[str, Any]] = field(default_factory=dict)
    branch_group: str | None = None
    branch: str | None = None
    permit: Permit | None = None
    index: int = 0
    state: str = 'active'
    contributions: set[str] = field(default_factory=set)
    withdrawn: set[str] = field(default_factory=set)
    paid: set[str] = field(default_factory=set)
    failure: str = ''
    runtime: dict[str, Any] = field(default_factory=dict)
    service: bool = False
    season: int | None = None

    def record(self) -> dict[str, Any]:
        return {**asdict(self), 'stages': [stage.record() for stage in self.stages],
                'contributions': sorted(self.contributions),
                'withdrawn': sorted(self.withdrawn), 'paid': sorted(self.paid)}

    @classmethod
    def read(cls, row: dict[str, Any]) -> 'Instance':
        return cls(**{**row, 'roster': tuple(Participant(**p) for p in row['roster']),
                      'stages': tuple(Progress.read(s) for s in row['stages']),
                      'reward': Payment.read(row['reward']),
                      'permit': permit_record(row.get('permit')),
                      'contributions': set(row['contributions']),
                      'withdrawn': set(row['withdrawn']), 'paid': set(row['paid'])})


@dataclass(frozen=True)
class Payout:
    player: str
    identity: str
    receipt: str
    payment: Payment
    permit: Permit | None
    option: str | None


class Engine:
    def __init__(self, origin: str, templates: Mapping[str, ContractTemplate],
                 state: dict[str, Any] | None = None) -> None:
        saved = state or {}
        self.origin, self.templates = origin, templates
        self.serial = int(saved.get('serial', 0))
        self.revision = int(saved.get('revision', 0))
        self.boards: dict[str, dict[str, Any]] = deepcopy(saved.get('boards', {}))
        self.instances = {key: Instance.read(row) for key, row in saved.get('instances', {}).items()}
        self.claims: dict[str, float] = dict(saved.get('claims', {}))
        self.branches: dict[str, str] = dict(saved.get('branches', {}))
        self.completed = {pid: set(ids) for pid, ids in saved.get('completed', {}).items()}

    def record(self) -> dict[str, Any]:
        return {'serial': self.serial, 'revision': self.revision, 'boards': deepcopy(self.boards),
                'instances': {key: instance.record() for key, instance in self.instances.items()},
                'claims': dict(self.claims), 'branches': dict(self.branches),
                'completed': {pid: sorted(ids) for pid, ids in self.completed.items()}}

    def fork(self) -> 'Engine':
        return Engine(self.origin, self.templates, self.record())

    def offer(self, template: ContractTemplate, oid: str, until: float | None) -> Offer:
        rng = Random(oid)
        options = {option.id: {'label': option.label, 'audience': option.audience,
            'reward': asdict(Payment.roll(option.reward, rng)),
            'permit': asdict(option.permit) if option.permit else None}
            for option in template.publication_options}
        return Offer(oid, template.id, until, Payment.roll(template.reward, rng), options)

    def board(self, handler: str, now: float) -> tuple[Offer, ...]:
        epoch = int(now // BOARD_SECONDS)
        saved = self.boards.get(handler)
        if saved and saved['epoch'] == epoch:
            return tuple(Offer.read(row) for row in saved['offers'])
        pool = sorted((t for t in self.templates.values()
                       if (t.giver == handler or handler == 'vesper') and not t.story and not t.service),
                      key=lambda template: (template.min_grade, template.id))
        rng = Random(f'{self.origin}:board:{handler}:{epoch}')
        offers = []
        if pool:
            # Keep at least one entry from the handler's earliest grade.
            own = [t for t in pool if t.giver == handler] or pool
            first = rng.choice([t for t in own if t.min_grade == min(t.min_grade for t in own)])
            bag = [t for t in pool if t.id != first.id]
            rng.shuffle(bag)
            for index in range(BOARD_OFFERS):
                if index == 0:
                    template = first
                else:
                    if not bag:
                        bag = list(pool)
                        rng.shuffle(bag)
                    template = bag.pop()
                offers.append(self.offer(template, f'{self.origin}:board:{handler}:{epoch}:{index}',
                                         (epoch + 1) * BOARD_SECONDS))
        self.boards[handler] = {'epoch': epoch, 'offers': [asdict(offer) for offer in offers]}
        self.revision += 1
        return tuple(offers)

    def story_offer(self, template: str, player: str) -> Offer:
        job = self.templates[template]
        if not job.story:
            raise ValueError('Choose a current board offer.')
        return self.offer(job, f'{self.origin}:story:{template}:{player}', None)

    @staticmethod
    def claim_key(identity: str, offer: str) -> str:
        return json.dumps((identity, offer), separators=(',', ':'))

    @staticmethod
    def branch_key(player: str, group: str) -> str:
        return json.dumps((player, group), separators=(',', ':'))

    def active_count(self, player: str) -> int:
        return sum(instance.state in ('active', 'complete') and not instance.story and not instance.service
                   and player in {p.player for p in instance.roster} - instance.withdrawn
                   for instance in self.instances.values())

    def helper_for(self, template: ContractTemplate, player: str) -> bool:
        if not template.story:
            return False
        if template.id in self.completed.get(player, set()):
            return True
        chosen = self.branches.get(self.branch_key(player, template.branch_group)) if template.branch_group else None
        return bool(template.branch and chosen is not None and chosen != template.branch)

    def accept(self, offer: Offer, roster: tuple[Participant, ...], now: float,
               approach: str = 'default') -> Instance:
        if not roster or len(roster) > CREW_MAX or len({p.player for p in roster}) != len(roster):
            raise ValueError('Choose one to five consenting participants.')
        if len({p.identity for p in roster}) != len(roster):
            raise ValueError('One reward recipient per BBS identity.')
        template = self.templates[offer.template]
        if template.service and offer.until is None:
            raise ValueError('A work order needs its original reservation deadline.')
        if offer.until is not None and now >= offer.until:
            raise ValueError('That offer refreshed. Read the current board.')
        if any(p.grade < template.min_grade for p in roster):
            raise ValueError('Every participant must meet the listed grade.')
        for instance in self.instances.values():
            if instance.offer == offer.id and instance.state != 'turned_in':
                if tuple(p.player for p in instance.roster) == tuple(p.player for p in roster):
                    return instance  # Duplicate accept cannot reroll targets or a reward.
                if {p.identity for p in roster} & {p.identity for p in instance.roster}:
                    raise ValueError('That identity already accepted this offer.')
        roster = tuple(replace(p, rewardable=p.rewardable and not self.helper_for(template, p.player)) for p in roster)
        if not any(p.rewardable for p in roster):
            if template.branch_group and template.branch and any(self.branches.get(
                    self.branch_key(p.player, template.branch_group)) not in (None, template.branch) for p in roster):
                raise ValueError('A participant already chose the other branch.')
            raise ValueError('Every participant already completed this story.')
        for participant in roster:
            if not template.story and not template.service and self.active_count(participant.player) >= ACTIVE_GENERATED:
                raise ValueError('A participant already has three active generated jobs.')
            if participant.rewardable and self.claim_key(participant.identity, offer.id) in self.claims:
                raise ValueError('That identity already received this offer.')
            if template.branch_group and template.branch and participant.rewardable:
                chosen = self.branches.get(self.branch_key(participant.player, template.branch_group))
                if chosen is not None and chosen != template.branch:
                    raise ValueError('A participant already chose the other branch.')
        stages = template.stages
        if approach != 'default':
            chosen = next((a for a in template.approaches if a.id == approach), None)
            if chosen is None:
                raise ValueError('Choose a listed approach.')
            stages = chosen.stages
        if not stages:
            raise ValueError('This job has no commissioned stages.')
        scaling = template.crew_scaling and not template.story and not template.service
        rng = Random(f'{offer.id}:{approach}:targets:{len(roster)}')
        resolved = []
        for stage in stages:
            count = objective_count(stage.quantity, len(roster), scaling)
            pool = (stage.target, *stage.target_pool)
            if stage.target.kind in ('npc', 'item'):
                targets = tuple(rng.choice(pool) for _ in range(count))
            elif len(pool) >= count:
                targets = tuple(rng.sample(pool, count))
            else:
                raise ValueError('The authored target pool cannot fit this roster.')
            resolved.append(Progress(stage, targets))
        self.serial += 1
        instance = Instance(f'{self.origin}:contract:{self.serial}', offer.id, template.id,
            template.giver, roster, tuple(resolved), offer.reward, now,
            None if template.story else offer.until if template.service else now + GENERATED_SECONDS,
            template.story, scaling,
            approach, deepcopy(template.params), deepcopy(offer.options), template.branch_group,
            template.branch, template.permit_scope)
        instance.service = template.service
        instance.season = template.season
        instance.stages[0].started_at = now
        for participant in roster:
            if template.branch_group and template.branch and participant.rewardable:
                self.branches[self.branch_key(participant.player, template.branch_group)] = template.branch
        self.instances[instance.id] = instance
        self.revision += 1
        return instance

    def observe(self, fact: Fact, now: float) -> tuple[str, ...]:
        changed = []
        for instance in self.instances.values():
            if (instance.state != 'active' or instance.expires_at is not None and now >= instance.expires_at
                    or fact.instance is not None and fact.instance != instance.id):
                continue
            progress = instance.stages[instance.index]
            stage = progress.stage
            if fact.attempt != progress.attempt or fact.stage and fact.stage != stage.id:
                continue
            if progress.window_closed(now):
                continue
            if fact.failure and fact.instance == instance.id:
                instance.state, instance.failure = 'failed', fact.failure
                changed.append(instance.id)
                continue
            if (fact.actor not in {p.player for p in instance.roster} - instance.withdrawn
                    or stage.verb != fact.verb
                    or stage.verb != 'survey' and fact.instance != instance.id):
                continue
            if (stage.verb == 'clear' and stage.resolution == 'subdue'
                    and fact.resolution == 'lethal' and any(matches(t, fact.target) for t in progress.targets)):
                instance.state, instance.failure = 'failed', 'A restraint target was killed.'
                changed.append(instance.id)
                continue
            if stage.completion != fact.completion or stage.verb == 'clear' and stage.resolution != fact.resolution:
                continue
            if not progress.accept(fact):
                continue
            participants = {p.player for p in instance.roster} - instance.withdrawn
            instance.contributions.update(participants & {fact.actor, *fact.contributors})
            if progress.complete:
                instance.index += 1
                if instance.index == len(instance.stages):
                    instance.state = 'complete'
                else:
                    instance.stages[instance.index].started_at = now
            changed.append(instance.id)
        if changed:
            self.revision += 1
        return tuple(changed)

    def withdraw(self, iid: str, player: str) -> None:
        instance = self.instances[iid]
        if player not in {p.player for p in instance.roster}:
            raise ValueError('That contract is not yours.')
        instance.withdrawn.add(player)
        instance.contributions.discard(player)
        if instance.withdrawn >= {p.player for p in instance.roster}:
            instance.state = 'turned_in' if instance.state == 'complete' else 'failed'
            instance.failure = 'abandoned'
        self.revision += 1

    def retry(self, iid: str, player: str, now: float) -> None:
        instance = self.instances[iid]
        if player not in {p.player for p in instance.roster}:
            raise ValueError('That contract is not yours.')
        if (player in instance.withdrawn and instance.state == 'active' and not instance.service
                and (instance.expires_at is None or now < instance.expires_at)):
            if not instance.story and self.active_count(player) >= ACTIVE_GENERATED:
                raise ValueError('A participant already has three active generated jobs.')
            instance.withdrawn.remove(player)
            self.revision += 1
            return  # Rejoin the original roster without resetting anyone's progress.
        if instance.state != 'failed' or instance.expires_at is not None and now >= instance.expires_at:
            raise ValueError('That stage cannot be retried now.')
        progress = instance.stages[instance.index]
        if not progress.stage.retry:
            raise ValueError('That stage does not permit a retry.')
        if not instance.story and not instance.service and any(self.active_count(p.player) >= ACTIVE_GENERATED
                for p in instance.roster if p.player not in instance.withdrawn or p.player == player):
            raise ValueError('A participant already has three active generated jobs.')
        if progress.stage.retry_from:
            instance.index = next(i for i,p in enumerate(instance.stages) if p.stage.id == progress.stage.retry_from)
        for reset in instance.stages[instance.index:]:
            reset.counts.clear()
            reset.receipts.clear()
            reset.subjects.clear()
            reset.attempt += 1
            reset.started_at = None
        instance.stages[instance.index].started_at = now
        instance.withdrawn.discard(player)
        instance.state, instance.failure = 'active', ''
        self.revision += 1

    def helper(self, instance: Instance, participant: Participant) -> bool:
        return not participant.rewardable or (instance.story and participant.player not in instance.paid
            and instance.template in self.completed.get(participant.player, set()))

    def quote(self, instance: Instance, participant: Participant, option: str | None = None) -> Payment:
        if self.helper(instance, participant):
            return Payment(0, 0, {}, 'explicit')
        if option is None and participant.player in instance.paid and instance.branch_group:
            recorded = self.branches.get(self.branch_key(participant.player, instance.branch_group))
            if recorded in instance.options:
                option = recorded
        payment = instance.reward
        if option is not None:
            payment = Payment.read(instance.options[option]['reward'])
        return payment.scaled(len(instance.roster), instance.scaling, participant.archetype == 'operator')

    def claim(self, iid: str, caller: str, now: float, option: str | None = None,
              excluded: Iterable[str] = ()) -> tuple[Payout, ...]:
        instance = self.instances[iid]
        if caller not in {p.player for p in instance.roster} - instance.withdrawn:
            raise ValueError('That contract is not yours.')
        if instance.state == 'turned_in':
            return ()
        if instance.state != 'complete' or instance.expires_at is not None and now >= instance.expires_at:
            raise ValueError('Finish the current objective before its deadline.')
        blocked = instance.withdrawn | instance.paid | set(excluded)
        eligible = {p.player for p in instance.roster if not self.helper(instance, p)} & instance.contributions - blocked
        if not eligible:
            instance.state = 'turned_in'
            self.revision += 1
            return ()
        if bool(instance.options) != (option is not None) or option is not None and option not in instance.options:
            raise ValueError('Choose a disclosed publication option.')
        recipients = [p for p in instance.roster if p.player in eligible and (option is None or p.player == caller)]
        if option is not None and instance.branch_group:
            key = self.branch_key(caller, instance.branch_group)
            old = self.branches.get(key)
            if old is not None and old != option:
                raise ValueError('That branch already has a committed choice.')
        if option is not None and caller not in eligible:
            return ()
        payouts = []
        for participant in recipients:
            key = self.claim_key(participant.identity, instance.offer)
            if key in self.claims:
                continue
            permit = instance.permit
            if option is not None:
                record = instance.options[option].get('permit')
                permit = permit_record(record)
            payouts.append(Payout(participant.player, participant.identity,
                f'contract:{instance.id}:{participant.identity}', self.quote(instance, participant, option),
                permit, option))
        if not payouts:
            return ()
        for payout in payouts:
            self.claims[self.claim_key(payout.identity, instance.offer)] = instance.expires_at or 0
            instance.paid.add(payout.player)
            if not instance.service:
                self.completed.setdefault(payout.player, set()).add(instance.template)
            if option is not None and instance.branch_group:
                self.branches[self.branch_key(payout.player, instance.branch_group)] = option
        if eligible <= instance.paid:
            instance.state = 'turned_in'
        self.revision += 1
        return tuple(payouts)

    def expire(self, now: float) -> tuple[str, ...]:
        expired = []
        pruned = False
        for iid, instance in tuple(self.instances.items()):
            if instance.state == 'active' and instance.stages[instance.index].window_closed(now):
                instance.state, instance.failure = 'failed', 'The field window closed. Resume at the listed checkpoint.'
                expired.append(iid)
            if instance.expires_at is None or now < instance.expires_at:
                continue
            if instance.state == 'turned_in' or instance.failure == 'expired':
                self.instances.pop(iid)
                pruned = True
            elif instance.failure != 'expired':
                instance.state, instance.failure = 'failed', 'expired'
                expired.append(iid)
        stale = [key for key, until in self.claims.items() if until and now >= until]
        for key in stale:
            self.claims.pop(key)
        if expired or stale or pruned:
            self.revision += 1
        return tuple(expired)
