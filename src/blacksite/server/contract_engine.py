"""Game 9 adapter: consenting rosters and atomic contract transactions."""

from collections.abc import Callable, Iterator
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from blacksite.content.schema import StageTarget
from blacksite.server.clock import TICK_HZ
from blacksite.server.contracts.engine import Fact, Instance, Offer, Participant, Payout, Progress, matches, target_record
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
        from blacksite.server.contracts.scenes import Scenes
        self.scenes = Scenes(self)
        from blacksite.server.contracts.actions import Actions
        self.actions = Actions(self)
        self.lat.encounters.mission_of = self.mission_of
        permission = self.lat.interlock.permit
        self.lat.interlock.permit = lambda player, core, action: (
            permission(player, core, action) or self.control_permit(player, core, action))

    def input(self, session: Session, frame: Frame, tick: int) -> bool:
        return self.actions.input(session, frame, tick) or self.panels.input(session, frame, tick)

    def now(self) -> float:
        return self.clock.now_utc().timestamp()

    def record(self) -> dict[str, Any]:
        if not self.commerce.pending:
            self.scenes.checkpoint()
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

    @staticmethod
    def obsolete(item: ItemInstance, draft: Ledger) -> bool:
        if item.mission is None:
            return False
        instance = draft.engine.instances.get(item.mission)
        if instance is None:
            return True
        return (instance.failure in ('expired', 'abandoned') or instance.state == 'turned_in'
            or item.owner in instance.withdrawn or bool(item.mission_stage and item.mission_stage not in {
                f'{p.stage.id}:{p.attempt}' for p in instance.stages[:instance.index+1]}))

    def write(self, draft: Ledger, patches: dict[str, dict[str, Any]] | None = None,
              identities: dict[str, dict[str, Any]] | None = None,
              items: dict[str, ItemInstance] | None = None, serial: int | None = None,
              callback: Callable[[bool], None] | None = None) -> None:
        patches = deepcopy(patches or {})
        items = deepcopy(self.commerce.items if items is None else items)
        for key, item in tuple(items.items()):
            if item.mission is None:
                continue
            if not self.obsolete(item, draft):
                continue
            items.pop(key)
            if item.owner in self.game.players:
                patch = patches.setdefault(item.owner, {})
                carried = patch.get('inventory', self.game.players[item.owner].inventory)
                patch['inventory'] = [iid for iid in carried if iid != key]
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
        draft = Ledger(self.origin, self.content, effect.get('contracts_state') or self.record())
        changed = draft.observe(fact, self.now())
        if changed:
            join_state(effect, draft.record(), self.install)
        return changed

    def current_jobs(self, player: str) -> Iterator[tuple[Instance, Progress]]:
        for instance in self.state.engine.instances.values():
            if (instance.state == 'active' and player in {p.player for p in instance.roster} - instance.withdrawn
                    and (instance.expires_at is None or self.now() < instance.expires_at)):
                yield instance, instance.stages[instance.index]

    def mission_of(self, player: str, data: str) -> str | None:
        presence = self.lat.presences.get(player)
        if not presence:
            return None
        for instance, progress in self.current_jobs(player):
            if any(target.kind == 'core_room' and target.core == presence.core
                    and target.room == presence.room and target.data == data for target in progress.targets):
                return f'{instance.id}:{progress.stage.id}:{progress.attempt}'
        return None

    def control_permit(self, player: str, core: str, control: str) -> bool:
        if self.state.permits_target(player, 'maintenance_credential',
                StageTarget('core_control', core=core, control=control), self.now()):
            return True
        return any(target.kind == 'core_control' and target.core == core and target.control == control
            for _, progress in self.current_jobs(player) for target in progress.targets)

    def network_fact(self, effect: dict[str, Any], player: str, target: StageTarget,
                     completion: str, receipt: str) -> tuple[str, ...]:
        for instance, progress in self.current_jobs(player):
            if progress.stage.completion == completion and any(matches(t, target) for t in progress.targets):
                return self.source_fact(effect, Fact(player, progress.stage.verb, completion, target,
                    receipt, receipt, instance=instance.id, stage=progress.stage.id, attempt=progress.attempt))
        return ()

    def lifted(self, effect: dict[str, Any], presence: Any, data: Any, unit: str) -> None:
        target = StageTarget('core_room', core=presence.core, room=presence.room, data=data.id)
        self.network_fact(effect, presence.player_id, target, 'lifted', unit)
        if data.kind == 'evidence' and data.asset in self.content.evidence:
            draft = Ledger(self.origin, self.content, effect.get('contracts_state') or self.record())
            if draft.acquire(presence.player_id, self.content.evidence[data.asset], target, self.now()):
                join_state(effect, draft.record(), self.install)

    def entered(self, presence: Any) -> None:
        if not presence.core or not presence.room:
            return
        target = StageTarget('core_room', core=presence.core, room=presence.room)
        if not any(progress.stage.completion == 'entered' and any(matches(t, target) for t in progress.targets)
                   for _, progress in self.current_jobs(presence.player_id)):
            return
        def propose() -> None:
            # No write for ordinary exploration without a matching objective.
            draft = self.state.fork()
            for instance, progress in self.current_jobs(presence.player_id):
                if progress.stage.completion != 'entered' or not any(matches(t, target) for t in progress.targets):
                    continue
                if draft.observe(Fact(presence.player_id, progress.stage.verb, 'entered', target,
                    f'{target.core}:{target.room}', f'{instance.id}:{progress.stage.id}:entered',
                    instance=instance.id, stage=progress.stage.id, attempt=progress.attempt), self.now()):
                    self.write(draft)
                break
        self.commerce.enqueue_system(propose)

    def npc_fact(self, effect: dict[str, Any], source: Any, actor: Any, resolution: str) -> tuple[str, ...]:
        iid = actor.behaviour.get('mission')
        if iid not in self.state.engine.instances or not actor.behaviour.get('contract_target'):
            return ()
        player = self.progression.controller(source)
        target = target_record(actor.behaviour['contract_target'])
        escort = bool(actor.behaviour.get('willing'))
        fact = Fact(player.id if player else source.id, 'escort' if escort else 'clear',
            'arrived' if escort else 'subdued' if resolution == 'subdue' else 'defeated',
            target, actor.id, actor.id+':'+resolution, instance=iid,
            stage=str(actor.behaviour.get('contract_stage', '')),
            attempt=int(actor.behaviour.get('contract_attempt', 0)), resolution=resolution,
            failure='The willing escort was lost.' if escort else '')
        return self.source_fact(effect, fact)

    def subdued(self, source: Any, actor: Any) -> None:
        def propose() -> None:
            if actor.zone is None or source.zone != actor.zone or not self.game.combat.legal(source, actor):
                return
            def committed(success: bool) -> None:
                if success:
                    actor.behaviour['resolution'] = 'subdued'
                    actor.stance = 'restrained'
                    self.world.leave(actor)
            self.commerce.settle(None, {}, self.commerce.items, self.commerce.caches,
                                 self.commerce.serial, committed)
            self.npc_fact(self.commerce.outbox[-1], source, actor, 'subdue')
        self.commerce.enqueue_system(propose)

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
        self.actions.cancel(session)
        self.panels.close(session)
        self.proposals = {key: p for key, p in self.proposals.items() if session.player_id not in p.roster}

    def tick(self, ctx: TickContext) -> None:
        self.panels.tick(ctx.tick)
        self.actions.tick(ctx.tick)
        # Checkpointed uptime is independent of live social crew membership.
        # Receipt-bearing changes wait for the current source write to finish.
        if self.commerce.pending:
            return
        elapsed = (ctx.tick - self.last_tick) / TICK_HZ
        self.last_tick = ctx.tick
        self.state.expire(self.now(), elapsed)
        self.scenes.reconcile()
        self.scenes.escorts(ctx.tick)
        if not self.commerce.pending and any(self.obsolete(item, self.state) for item in self.commerce.items.values()):
            self.write(self.state.fork())
