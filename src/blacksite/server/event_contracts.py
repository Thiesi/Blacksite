"""Game 12 public jobs, bound to one committed world-event source."""

from copy import deepcopy
from dataclasses import asdict, replace
from typing import Any

from blacksite.server.contracts.engine import Fact, Offer
from blacksite.server.contracts.ledger import Ledger
from blacksite.server.contracts.transactions import join_state
from blacksite.server.events import Plan, Scheduler, Transition
from blacksite.server.rules.events import ESCORT_RADIUS
from blacksite.server.world.actors import Actor


class EventContracts:
    def __init__(self, owner: Any) -> None:
        self.owner = owner

    def bind(self) -> None:
        contracts = self.owner.core.contracts
        previous = contracts.additional_offers
        contracts.additional_offers = lambda handler: (*previous(handler), *self.offers(handler))
        validate = contracts.validate_offer
        def checked(offer: Offer) -> None:
            validate(offer)
            if offer.event_plan and not any(current.id == offer.id for current in self.offers('vesper')):
                raise ValueError('That event offer closes or changes. Read the current board.')
        contracts.validate_offer = checked
        prepare = contracts.prepare_accept
        def prepared(offer: Offer, instance: Any) -> None:
            prepare(offer, instance)
            if offer.event_plan:
                convoy = next((actor for actor in self.owner.world.actors.values()
                               if actor.behaviour.get('convoy') == offer.event_plan), None)
                instance.runtime['event_escort_start'] = [person.player for person in instance.roster
                    if convoy is not None and self.near(person.player, convoy)]
        contracts.prepare_accept = prepared
        npc_fact = self.owner.core.npcs.event_fact
        def joined(effect: dict[str, Any], source: Actor, actor: Actor) -> None:
            npc_fact(effect, source, actor)
            self.npc_fact(effect, source, actor)
        self.owner.core.npcs.event_fact = joined

    def allocate(self, scheduler: Scheduler, plan: Plan) -> None:
        engine = self.owner.core.contracts.state.engine
        offers = []
        for index, effect in enumerate(scheduler.effects(plan)):
            if effect.type != 'event_contract':
                continue
            template = self.owner.content.contracts[str(effect.params['contract'])]
            if not template.event_only or not self.owner.content.active('contracts', template.id):
                raise ValueError('Event jobs need a commissioned event-only template.')
            oid = f'{plan.id}:job:{index}'
            offer = replace(engine.offer(template, oid, plan.ends_at), event_plan=plan.id)
            offers.append(asdict(offer))
        plan.allocations['offers'] = offers

    def offers(self, handler: str) -> tuple[Offer, ...]:
        offers = []
        for plan in self.owner.active():
            if plan.allocations.get('convoy_lost') or 'convoy-arrived' in plan.reward_receipts:
                continue
            for row in plan.allocations.get('offers', []):
                template = self.owner.content.contracts[row['template']]
                if handler in (template.giver, 'vesper'):
                    offers.append(Offer.read(row))
        return tuple(offers)

    def stage(self, effect: dict[str, Any], scheduler: Scheduler,
              transitions: list[Transition], facts: tuple[Fact, ...]) -> None:
        contracts = self.owner.core.contracts
        for fact in facts:
            contracts.source_fact(effect, fact)
        ended = {transition.plan for transition in transitions if transition.kind in ('end', 'cancel')}
        if ended:
            draft = Ledger(contracts.origin, self.owner.content, effect.get('contracts_state') or contracts.record())
            changed = False
            for instance in draft.engine.instances.values():
                if instance.state == 'active' and instance.runtime.get('event_plan') in ended:
                    instance.state, instance.failure = 'failed', 'The event window closes.'
                    changed = True
            if changed:
                draft.engine.revision += 1
                join_state(effect, draft.record(), contracts.install)

    def near(self, pid: str, actor: Actor) -> bool:
        other = self.owner.world.actors.get(pid)
        return bool(other and other.zone == actor.zone and other.stance == 'normal'
            and sum((a-b)**2 for a, b in zip(other.position, actor.position)) <= ESCORT_RADIUS**2
            and self.owner.core.combat.visible(other, actor))

    def checkpoint(self, plan: Plan, actor: Actor, *, final: bool) -> tuple[Fact, ...]:
        """Credit a completed leg, not an incidental appearance at arrival."""
        records = plan.allocations.setdefault('escort_legs', {})
        facts = []
        for instance in self.owner.core.contracts.state.engine.instances.values():
            if instance.state != 'active' or instance.runtime.get('event_plan') != plan.id:
                continue
            progress = instance.stages[instance.index]
            if progress.stage.verb != 'escort':
                continue
            nearby = {person.player for person in instance.roster
                      if person.player not in instance.withdrawn and self.near(person.player, actor)}
            previous = records.get(instance.id, {'start': instance.runtime.get('event_escort_start', []), 'credited': []})
            credited = set(previous['credited']) | (set(previous['start']) & nearby)
            records[instance.id] = {'start': sorted(nearby), 'credited': sorted(credited)}
            current = sorted(nearby & credited)
            if final and current:
                facts.append(Fact(current[0], 'escort', 'arrived', progress.stage.target,
                    actor.id, f'{plan.id}:arrived:{instance.id}', instance=instance.id,
                    stage=progress.stage.id, attempt=progress.attempt, contributors=tuple(current[1:])))
        return tuple(facts)

    def npc_fact(self, effect: dict[str, Any], source: Actor, actor: Actor) -> None:
        owner = self.owner
        pid = actor.behaviour.get('convoy')
        plan = owner.scheduler.plans.get(pid)
        if plan is None or not plan.live:
            return
        draft = owner.scheduler.fork()
        target = draft.plans[pid]
        if not target.claim('convoy-lost'):
            return
        target.allocations['convoy_lost'] = True
        facts = []
        attacker = owner.core.progression.controller(source)
        attacker_id = attacker.id if attacker else source.id
        for instance in owner.core.contracts.state.engine.instances.values():
            if instance.state != 'active' or instance.runtime.get('event_plan') != pid:
                continue
            progress = instance.stages[instance.index]
            escort = progress.stage.verb == 'escort'
            facts.append(Fact(attacker_id, progress.stage.verb,
                'arrived' if escort else 'defeated', progress.stage.target,
                actor.id, f'{pid}:lost:{instance.id}', instance=instance.id,
                stage=progress.stage.id, attempt=progress.attempt, resolution='lethal',
                failure='The public convoy is lost.' if escort else ''))
        self.stage(effect, draft, [], tuple(facts))
        effect['events_state'] = draft.record()
        previous = effect.get('callback')
        def committed(success: bool) -> None:
            if previous:
                previous(success)
            if success:
                owner.scheduler = draft
                owner.refresh()
                owner.notify('The public convoy is lost. Its escort offers close.')
        effect['callback'] = committed
