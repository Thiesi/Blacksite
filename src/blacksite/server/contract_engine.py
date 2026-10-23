"""Game 9 adapter: consenting rosters and atomic contract transactions."""

from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from blacksite.server.clock import TICK_HZ
from blacksite.server.contracts.engine import Fact, Offer, Participant, Payout
from blacksite.server.contracts.ledger import Ledger
from blacksite.server.contracts.transactions import join_state
from blacksite.server.inventory import Inventory
from blacksite.server.items import ItemInstance, make_item
from blacksite.server.lattice.programs import can_acquire
from blacksite.server.loop import TickContext
from blacksite.server.progression import Grant
from blacksite.server.protocol import Frame
from blacksite.server.sessions import Session


@dataclass
class Proposal:
    id: str
    creator: str
    offer: Offer
    roster: tuple[str, ...]
    approach: str = 'default'
    service: str = ''
    allocation: str = ''
    service_revision: int = 0
    consent: set[str] = field(default_factory=set)


class Contracts:
    def __init__(self, progression: Any, state: dict[str, Any]) -> None:
        self.progression, self.game = progression, progression.game
        self.commerce, self.content, self.clock = progression.commerce, progression.content, progression.clock
        self.sim, self.world, self.lat = progression.sim, self.game.world, progression.lattice
        self.origin = self.game.sessions.origin
        self.state = Ledger(self.origin, self.content, state)
        self.state.expire(self.now())  # UTC reconciliation before caller attachment.
        self.last_tick = self.clock.now_tick()
        self.proposals: dict[str, Proposal] = {}
        self.proposal_serial = 0
        self.game.contracts = self
        from blacksite.server.contracts.panels import Panels
        self.panels = Panels(self)

    def input(self, session: Session, frame: Frame, tick: int) -> bool:
        return self.panels.input(session, frame, tick)

    def now(self) -> float:
        return self.clock.now_utc().timestamp()

    def record(self) -> dict[str, Any]:
        return self.state.record()

    def install(self, state: dict[str, Any]) -> None:
        self.state = Ledger(self.origin, self.content, state)

    def log(self, pid: str, text: str) -> None:
        session = self.game.combat.session(pid)
        if session:
            self.sim.log(session, text)
            self.commerce.toast(session, text)

    def participant(self, pid: str) -> Participant:
        player = self.game.players[pid]
        if pid in self.game.deleting:
            raise ValueError('That character is leaving the city.')
        return Participant(pid, player.bbs_user_id, player.grade, player.archetype)

    def write(self, draft: Ledger, patches: dict[str, dict[str, Any]] | None = None,
              identities: dict[str, dict[str, Any]] | None = None,
              items: dict[str, ItemInstance] | None = None, serial: int | None = None,
              callback: Callable[[bool], None] | None = None) -> None:
        if not self.commerce.settle(None, {}, self.commerce.items if items is None else items,
                self.commerce.caches, self.commerce.serial if serial is None else serial,
                callback or (lambda success: None)):
            raise ValueError('The city is busy. Try again.')
        effect = self.commerce.outbox[-1]
        effect['player_patches'] = deepcopy(patches or {})
        effect['identities'] = deepcopy(identities or {})
        join_state(effect, draft.record(), self.install)

    def source_fact(self, effect: dict[str, Any], fact: Fact) -> tuple[str, ...]:
        """Source owners call this before their own write, never on commit."""
        draft = Ledger(self.origin, self.content, effect.get('contracts_state', self.record()))
        changed = draft.observe(fact, self.now())
        if changed:
            join_state(effect, draft.record(), self.install)
        return changed

    def offer(self, oid: str, player: str, handler: str) -> Offer:
        for offered in self.state.engine.board(handler, self.now()):
            if offered.id == oid:
                return offered
        if oid in self.state.engine.templates and self.state.engine.templates[oid].story:
            job = self.state.engine.templates[oid]
            if job.giver == handler:
                return self.state.engine.story_offer(oid, player)
        raise ValueError('That offer changed. Read the current board.')

    def propose(self, player: str, offer: Offer, roster: tuple[str, ...],
                approach: str = 'default') -> Proposal:
        if not roster or roster[0] != player:
            raise ValueError('The proposer must join the listed roster.')
        crew = self.game.crews.registry.crew_of(player)
        if len(roster) > 1 and (not crew or not set(roster) <= set(crew.members)):
            raise ValueError('Choose participants from your current crew.')
        for pid in roster:
            if not self.game.combat.session(pid):
                raise ValueError('Every proposed participant must be online.')
        # Validate terms without consuming slots, branches, supplies or receipts.
        self.state.engine.fork().accept(offer, tuple(self.participant(pid) for pid in roster), self.now(), approach)
        self.proposal_serial += 1
        proposal = Proposal(f'{self.origin}:proposal:{self.proposal_serial}', player, offer, roster, approach)
        self.proposals[proposal.id] = proposal
        return proposal

    def consent(self, proposal: str, player: str) -> None:
        offered = self.proposals[proposal]
        if player not in offered.roster or not self.game.combat.session(player):
            raise ValueError('That proposal is not yours.')
        if offered.offer.until is not None and self.now() >= offered.offer.until:
            raise ValueError('That proposal expired. Read the current board.')
        offered.consent.add(player)

    def start(self, proposal: str, player: str) -> None:
        if self.commerce.pending:
            self.commerce.enqueue_system(lambda: self.start(proposal, player)
                if proposal in self.proposals else None)
            return
        offered = self.proposals[proposal]
        if offered.creator != player or set(offered.roster) != offered.consent:
            raise ValueError('Every listed participant must accept these terms.')
        if any(not self.game.combat.session(pid) for pid in offered.roster):
            raise ValueError('A participant left before the roster froze.')
        crew = self.game.crews.registry.crew_of(player)
        if len(offered.roster) > 1 and (not crew or not set(offered.roster) <= set(crew.members)):
            raise ValueError('The proposed crew changed. Offer the job again.')
        draft = self.state.fork()
        draft.engine.accept(offered.offer, tuple(self.participant(pid) for pid in offered.roster),
                            self.now(), offered.approach)
        def committed(success: bool) -> None:
            if success:
                self.proposals.pop(proposal, None)
                for pid in offered.roster:
                    self.log(pid, 'Contract accepted. Your objective roster is frozen.')
        self.write(draft, callback=committed)

    def reward(self, draft: Ledger, iid: str, payouts: tuple[Payout, ...]) -> tuple[dict[str, Any], dict[str, Any], dict[str, ItemInstance], int]:
        patches, identities = {}, {}
        items, serial = deepcopy(self.commerce.items), self.commerce.serial
        instance = draft.engine.instances[iid]
        for payout in payouts:
            player = self.game.players[payout.player]
            patch, identity, _ = self.progression.reward_patch(player,
                Grant('contract', payout.receipt, True, scope='contract:'+instance.template,
                      amount=payout.payment.xp))
            patch['chits_hand'] = player.chits_hand + payout.payment.chits
            patch.update(self.game.factions.standing_patch(player, payout.payment.standing,
                                                          payout.payment.standing_mode))
            recipient = deepcopy(player)
            for key, value in patch.items():
                setattr(recipient, key, deepcopy(value))
            acquired = recipient.progress.setdefault('contract_programs', {})
            season = str(instance.season or 1)
            known = recipient.progress.setdefault('known_programs', [])
            for pid in payout.payment.programs:
                program = self.content.programs[pid]
                if pid in known:
                    continue
                if not can_acquire(program, player.archetype, player.standing, set(acquired.get(season, ()))):
                    raise ValueError('You do not meet this program reward\'s acquisition requirements.')
                known.append(pid)
                acquired.setdefault(season, []).append(pid)
            inventory = Inventory(items, self.content.items, self.progression.modifiers(recipient).secured_slots)
            for tid in payout.payment.items:
                serial += 1
                inventory.add(recipient, make_item(f'{self.origin}:item:{serial}', self.content.items[tid],
                                                  player.id, self.clock.now_utc().isoformat()))
            patch['inventory'] = list(recipient.inventory)
            patch['progress'] = {key: value for key, value in recipient.progress.items()
                                 if key not in player.progress or player.progress[key] != value}
            patches[player.id], identities[player.bbs_user_id] = patch, identity
        return patches, identities, items, serial

    def claim(self, iid: str, player: str, option: str | None = None) -> None:
        if self.commerce.pending:
            self.commerce.enqueue_system(lambda: self.claim(iid, player, option)
                if player in self.game.players and player not in self.game.deleting else None)
            return
        draft = self.state.fork()
        payouts = draft.claim(iid, player, self.now(), option, tuple(self.game.deleting))
        if not payouts:
            return
        patches, identities, items, serial = self.reward(draft, iid, payouts)
        def committed(success: bool) -> None:
            for payout in payouts:
                if success:
                    recipient = self.game.players[payout.player]
                    self.game.factions.refresh(recipient)
                    self.progression.sync_actor(recipient)
                self.log(payout.player, f'Contract settled: {payout.payment.chits} chits, {payout.payment.xp} XP.'
                    if success else 'The reward could not be saved. Your turn-in remains available.')
        self.write(draft, patches, identities, items, serial, committed)

    def disconnect(self, session: Session) -> None:
        self.panels.close(session)
        self.proposals = {key: p for key, p in self.proposals.items() if session.player_id not in p.roster}

    def tick(self, ctx: TickContext) -> None:
        self.panels.tick(ctx.tick)
        # Checkpointed uptime is independent of live social crew membership.
        # Receipt-bearing changes wait for the current source write to finish.
        if self.commerce.pending:
            return
        elapsed = (ctx.tick - self.last_tick) / TICK_HZ
        self.last_tick = ctx.tick
        self.state.expire(self.now(), elapsed)
