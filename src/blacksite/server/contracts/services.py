"""Game 7.5: public work orders, driven by supplied UTC and uptime.

The adapter drafts this state with the contract engine and joins both to
the same source transaction. Disconnects do not constitute withdrawal.
"""

from copy import deepcopy
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

from blacksite.content.schema import Effect, ServiceNodeTemplate
from blacksite.server.contracts.engine import Instance
from blacksite.server.crews import CREW_MAX

FAULT_INTERVAL = 60 * 60  # Game 7.5, server uptime only.
FAULT_SECONDS = 20 * 60  # UTC deadlines continue during maintenance.
RESERVATION_SECONDS = 10 * 60
ALLOCATION_SECONDS = 20 * 60
RESERVE_CACHE_UNITS = 2  # One shared stock per order, not per worker.


@dataclass
class Node:
    id: str
    state: str = 'normal'
    revision: int = 0
    next_fault_uptime: float = FAULT_INTERVAL
    generation: int = 0
    fault_expires: float = 0
    order: str = ''
    roster: tuple[str, ...] = ()
    withdrawn: set[str] = field(default_factory=set)
    reserved_until: float = 0
    allocation: str = ''
    allocation_expires: float = 0
    cache_taken: int = 0

    @property
    def workers(self) -> frozenset[str]:
        return frozenset(self.roster) - self.withdrawn

    def record(self) -> dict[str, Any]:
        return {**asdict(self), 'withdrawn': sorted(self.withdrawn)}

    @classmethod
    def read(cls, row: dict[str, Any]) -> 'Node':
        return cls(**{**row, 'roster': tuple(row.get('roster', ())),
                      'withdrawn': set(row.get('withdrawn', ()))})


class Services:
    def __init__(self, origin: str, templates: Mapping[str, ServiceNodeTemplate],
                 state: dict[str, Any] | None = None) -> None:
        saved = state or {}
        self.origin, self.templates = origin, templates
        self.uptime = float(saved.get('uptime', 0))
        self.serial = int(saved.get('serial', 0))
        self.nodes = {sid: Node.read(saved['nodes'][sid]) if sid in saved.get('nodes', {}) else Node(sid)
                      for sid, template in templates.items() if template.contract is not None}

    def record(self) -> dict[str, Any]:
        return {'uptime': self.uptime, 'serial': self.serial,
                'nodes': {sid: node.record() for sid, node in self.nodes.items()}}

    def fork(self) -> 'Services':
        return Services(self.origin, self.templates, deepcopy(self.record()))

    @staticmethod
    def _release(node: Node) -> None:
        node.state = 'fault'
        node.order, node.allocation = '', ''
        node.roster, node.withdrawn = (), set()
        node.reserved_until = 0
        node.revision += 1

    @staticmethod
    def _normal(node: Node) -> None:
        Services._release(node)
        node.state = 'normal'
        node.fault_expires = node.allocation_expires = 0
        node.cache_taken = 0

    def advance(self, now: float, elapsed_uptime: float = 0) -> tuple[str, ...]:
        """Reconcile deadlines before views. Startup passes zero uptime.

        Return released order IDs so the owner can clean mission assets
        in the same draft. Large time steps offer at most one new fault.
        """
        if elapsed_uptime < 0:
            raise ValueError('Server uptime cannot go backwards.')
        self.uptime += elapsed_uptime
        released = []
        for node in self.nodes.values():
            if node.state == 'allocated' and now >= node.allocation_expires:
                self._normal(node)
            if node.state in ('fault', 'repairing') and now >= node.fault_expires:
                if node.order:
                    released.append(node.order)
                self._normal(node)  # NPC repair; no player reward.
            elif node.state == 'repairing' and now >= node.reserved_until:
                released.append(node.order)
                self._release(node)
            if self.uptime >= node.next_fault_uptime:
                node.next_fault_uptime = (self.uptime // FAULT_INTERVAL + 1) * FAULT_INTERVAL
                if node.state == 'normal':
                    node.state, node.fault_expires = 'fault', now + FAULT_SECONDS
                    node.generation += 1
                    node.revision += 1
        return tuple(released)

    def reserve(self, sid: str, allocation: str, roster: tuple[str, ...],
                now: float, revision: int) -> Node:
        node = self.nodes[sid]
        if node.state != 'fault' or now >= node.fault_expires or node.revision != revision:
            raise ValueError('That work order changed. Read its current terms.')
        if allocation not in {a.id for a in self.templates[sid].allocations}:
            raise ValueError('Choose a listed allocation.')
        if not roster or len(roster) > CREW_MAX or len(set(roster)) != len(roster):
            raise ValueError('Choose one to five consenting participants.')
        self.serial += 1
        node.order = f'{self.origin}:service:{sid}:{node.generation}:{self.serial}'
        node.state, node.allocation, node.roster = 'repairing', allocation, roster
        node.withdrawn.clear()
        node.reserved_until = min(now + RESERVATION_SECONDS, node.fault_expires)
        node.revision += 1
        return node

    def withdraw(self, sid: str, order: str, player: str) -> bool:
        node = self.nodes[sid]
        if node.state != 'repairing' or order != node.order or player not in node.roster:
            return False
        node.withdrawn.add(player)
        if not node.workers:
            self._release(node)
        else:
            node.revision += 1
        return True

    def complete(self, sid: str, instance: Instance, now: float) -> bool:
        node = self.nodes[sid]
        if node.state == 'allocated' and node.order == instance.offer:
            return False
        if (node.state != 'repairing' or node.order != instance.offer
                or now >= node.reserved_until or now >= node.fault_expires):
            raise ValueError('That reservation ended. Read the current work order.')
        if (not instance.service or instance.template != self.templates[sid].contract
                or instance.state not in ('complete', 'turned_in')
                or tuple(p.player for p in instance.roster) != node.roster
                or instance.withdrawn != node.withdrawn):
            raise ValueError('Finish the reserved work order first.')
        node.state = 'allocated'
        node.allocation_expires = now + ALLOCATION_SECONDS
        node.revision += 1
        return True

    def effects(self, sid: str, player: str, now: float) -> tuple[Effect, ...]:
        """Return only this owner's live layer, never mutate another layer."""
        node, template = self.nodes[sid], self.templates[sid]
        if node.state in ('fault', 'repairing') and now < node.fault_expires:
            return template.fault_effects
        if node.state == 'allocated' and now < node.allocation_expires:
            effects = next(a.effects for a in template.allocations if a.id == node.allocation)
            return tuple(effect for effect in effects
                         if effect.audience == 'public' or player in node.workers)
        return template.normal_effects

    def take_cache(self, sid: str, order: str, player: str, quantity: int, now: float) -> int:
        node = self.nodes[sid]
        if (node.state != 'allocated' or node.allocation != 'reserve' or node.order != order
                or player not in node.workers or now >= node.allocation_expires or quantity <= 0):
            return 0
        # A reserve allocation without an authored cache cannot mint salvage.
        if not any(effect.type == 'cache' for effect in self.effects(sid, player, now)):
            return 0
        count = min(quantity, RESERVE_CACHE_UNITS - node.cache_taken)
        if count:
            node.cache_taken += count
            node.revision += 1
        return count
