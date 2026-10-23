"""Architecture 15: one durable draft for objectives, evidence and permits."""

from copy import deepcopy
from dataclasses import asdict
from typing import Any

from blacksite.content.loader import ContentTree
from blacksite.content.schema import EvidenceRecord, StageTarget
from blacksite.server.contracts.engine import Engine, Fact, Payout, matches, permit_record
from blacksite.server.contracts.services import Services


class Ledger:
    def __init__(self, origin: str, content: ContentTree, state: dict[str, Any] | None = None) -> None:
        saved = state or {}
        self.origin, self.content = origin, content
        self.engine = Engine(origin, {cid: job for cid, job in content.contracts.items()
                                     if content.active('contracts', cid)}, saved.get('engine'))
        self.services = Services(origin, {sid: node for sid, node in content.services.items()
                                         if content.active('services', sid)}, saved.get('services'))
        self.journal: dict[str, dict[str, dict[str, Any]]] = deepcopy(saved.get('journal', {}))
        self.permits: dict[str, dict[str, dict[str, Any]]] = deepcopy(saved.get('permits', {}))

    def record(self) -> dict[str, Any]:
        return {'engine': self.engine.record(), 'services': self.services.record(),
                'journal': deepcopy(self.journal), 'permits': deepcopy(self.permits)}

    def fork(self) -> 'Ledger':
        return Ledger(self.origin, self.content, self.record())

    def acquire(self, player: str, evidence: EvidenceRecord, location: StageTarget,
                now: float, instance: str = '', season: int | None = None) -> bool:
        """The verified action supplies location; opening prose grants nothing."""
        journal = self.journal.setdefault(player, {})
        if evidence.id in journal:
            return False
        journal[evidence.id] = {**asdict(evidence), 'location': asdict(location),
            'observed_at': now, 'instance': instance, 'publication': '',
            'season': self.engine.instances[instance].season if instance in self.engine.instances else season}
        return True

    def observe(self, fact: Fact, now: float) -> tuple[str, ...]:
        before = {iid: instance.stages[instance.index].stage.id
                  for iid, instance in self.engine.instances.items() if instance.state == 'active'}
        changed = self.engine.observe(fact, now)
        for iid in changed:
            instance = self.engine.instances[iid]
            if instance.state == 'failed':
                continue
            template = self.content.contracts.get(instance.template)
            if template is None:
                continue
            recipients = {p.player for p in instance.roster} - instance.withdrawn
            recipients &= {fact.actor, *fact.contributors}
            for eid in template.evidence_assets:
                evidence = self.content.evidence[eid]
                if evidence.related_objective and evidence.related_objective != instance.template:
                    continue
                if evidence.related_stage and evidence.related_stage != before[iid]:
                    continue
                for pid in recipients:
                    self.acquire(pid, evidence, fact.target, now, iid)
        return changed

    def claim(self, iid: str, player: str, now: float, option: str | None = None,
              excluded: tuple[str, ...] = ()) -> tuple[Payout, ...]:
        payouts = self.engine.claim(iid, player, now, option, excluded)
        instance = self.engine.instances[iid]
        for payout in payouts:
            if payout.permit:
                public = payout.permit.audience == 'public' or (
                    option is not None and instance.options[option]['audience'] == 'public')
                holder, key = ('*', f'{iid}:{option}') if public else (payout.player, payout.receipt)
                self.permits.setdefault(holder, {}).setdefault(key, {
                    'permit': asdict(payout.permit), 'until': now + payout.permit.expiry_seconds,
                    'instance': iid})
            for record in self.journal.get(payout.player, {}).values():
                if record['instance'] == iid and option is not None:
                    record['publication'] = option
        return payouts

    def permits_target(self, player: str, kind: str, target: StageTarget, now: float) -> bool:
        """A credential matches its actual declared binding, never an ID prefix."""
        rows = [*self.permits.get(player, {}).values(), *self.permits.get('*', {}).values()]
        for row in rows:
            permit = permit_record(row['permit'])
            if (now < row['until'] and permit and permit.kind == kind
                    and permit.binding is not None and matches(permit.binding, target)):
                return True
        return False

    def expire(self, now: float, elapsed_uptime: float = 0) -> tuple[str, ...]:
        cleanup = list(self.engine.expire(now))
        released = set(self.services.advance(now, elapsed_uptime))
        for instance in self.engine.instances.values():
            if instance.service and instance.offer in released and instance.state != 'turned_in':
                instance.state, instance.failure = 'failed', 'expired'
                cleanup.append(instance.id)
                self.engine.revision += 1
        for player, permits in tuple(self.permits.items()):
            self.permits[player] = {key: row for key, row in permits.items() if now < row['until']}
            if not self.permits[player]:
                self.permits.pop(player)
        return tuple(dict.fromkeys(cleanup))
