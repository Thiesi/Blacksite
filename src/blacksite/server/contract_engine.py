"""Game 9 adapter: consenting rosters and atomic contract transactions."""

from collections.abc import Callable, Iterator
from copy import deepcopy
from dataclasses import dataclass, field, replace
from math import ceil
from typing import Any

from blacksite.content.schema import Stage, StageTarget
from blacksite.server.clock import TICK_HZ
from blacksite.server.contracts.engine import Fact, Instance, Offer, Participant, Payout, Progress, matches, target_record
from blacksite.server.contracts.ledger import Ledger
from blacksite.server.contracts.transactions import join_state
from blacksite.server.crews import PARTICIPATION_SECONDS
from blacksite.server.inventory import Inventory
from blacksite.server.items import ItemInstance, make_item
from blacksite.server.lattice.programs import can_acquire
from blacksite.server.loop import TickContext
from blacksite.server.progression import Grant, award
from blacksite.server.factions import apply_vector
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
        from blacksite.server.contracts.effects import ServiceEffects
        self.effects = ServiceEffects(self)
        clinic_fee = self.progression.clinics.service_multiplier
        self.progression.clinics.service_multiplier = lambda player, vendor: min(
            clinic_fee(player, vendor), self.effects.fee(player, vendor))
        budget_factor = self.commerce.budget_multiplier
        self.commerce.budget_multiplier = lambda vendor, counter: budget_factor(vendor, counter)*self.effects.budget(vendor, counter)
        vendor_open = self.commerce.vendor_available
        self.commerce.vendor_available = lambda vendor, counter: vendor_open(vendor, counter) and self.effects.vendor_open(
            counter.partition(':')[0], vendor.id, counter.partition(':')[2])
        decorate = self.sim.crew_view
        def decorated(session: Session, body: dict[str, Any]) -> None:
            decorate(session, body)
            self.decorate(session, body)
        self.sim.crew_view = decorated
        lattice_view = self.lat.encounters.view
        def network_view(session: Session, presence: Any, body: dict[str, Any]) -> tuple[str, dict[str, Any]]:
            kind, document = lattice_view(session, presence, body)
            if kind == 'lattice':
                self.decorate(session, document)
            return kind, document
        self.lat.encounters.view = network_view
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
        participants = {p.player for instance in self.state.engine.instances.values() for p in instance.roster}
        self.state = Ledger(self.origin, self.content, state)
        participants |= {p.player for instance in self.state.engine.instances.values() for p in instance.roster}
        for zone in {actor.zone for pid in participants if (actor := self.world.actors.get(pid)) and actor.zone}:
            self.world.zones[zone].revision += 1

    def decorate(self, session: Session, body: dict[str, Any]) -> None:
        if self.effects.patrols(session.player_id):
            body['published_patrol'] = True
        jobs = list(self.current_jobs(session.player_id))
        actor = self.world.actors.get(session.player_id)
        if jobs:
            presence = self.lat.presences.get(session.player_id)
            relevant = next(((job, progress) for job, progress in jobs if presence
                and any(presence.core and target.core == presence.core
                    or presence.descent and target.kind == 'silt_data' and target.sector == presence.sector
                    for target in progress.targets)), None)
            instance, progress = relevant or (next(((job, stage) for job, stage in jobs
                if any(target.zone == actor.zone for target in stage.targets)), jobs[0]) if actor else jobs[0])
            stage = progress.stage
            from blacksite.server.npcs.templates import SUBDUE_SECONDS, SUBDUE_SHOCK
            restraint = stage.verb == 'clear' and stage.resolution == 'subdue'
            seconds = self.duration(session.player_id, stage)
            cost = f'{SUBDUE_SHOCK} shock' if restraint else stage.cost
            body['objective'] = {'next_action': stage.label or stage.verb,
                'cost': f'{seconds:g}s {cost}', 'progress': f'{sum(progress.counts.values())}/{len(progress.targets)}',
                'target': stage.target.object or stage.target.npc or stage.target.data or stage.target.core or stage.target.zone,
                'retry': stage.retry}
            if 'viewport' in body:
                body['objective']['compact_hint'] = True
                if not body.get('me', {}).get('channel'):
                    body['hint'] = f"Next: {stage.label or stage.verb} {body['objective']['progress']} | {seconds:g}s {cost} | E act Q jobs"
        if actor:
            for sid, node in self.state.services.nodes.items():
                template = self.content.services[sid]
                if template.zone == actor.zone:
                    deadline = node.allocation_expires if node.state == 'allocated' else node.fault_expires
                    left = max(0, ceil(deadline-self.now()))
                    status = node.allocation if node.state == 'allocated' else node.state
                    body['service'] = {'id': sid, 'name': template.name, 'state': node.state,
                        'allocation': node.allocation, 'expiry': left,
                        'summary': f'{template.name} {status}'+(f' {left}s' if node.state != 'normal' else ''),
                        'escape': template.safe_return}
                    break

    def duration(self, player: str, stage: Stage) -> float:
        presence = self.lat.presences.get(player)
        if stage.linked_control and presence and presence.core == stage.linked_control.core:
            from blacksite.server.interlock import FLIP_SECONDS
            return FLIP_SECONDS
        if stage.verb == 'clear' and stage.resolution == 'subdue':
            from blacksite.server.npcs.templates import SUBDUE_SECONDS
            return SUBDUE_SECONDS
        if stage.input == 'flip' and stage.target.kind == 'core_control':
            from blacksite.server.interlock import FLIP_SECONDS
            return FLIP_SECONDS
        if stage.input == 'lift' and stage.target.kind in ('core_room', 'silt_data'):
            from blacksite.server.lattice.encounters import LIFT_SECONDS
            ledger = self.content.programs['prg_ledger']
            multiplier = float(ledger.effect.params['lift_multiplier']) if presence and 'prg_ledger' in presence.rig else 1
            return LIFT_SECONDS*multiplier
        return stage.seconds

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
        return Contracts.obsolete_mission(draft, item.owner, item.mission, item.mission_stage)

    @staticmethod
    def obsolete_mission(draft: Ledger, owner: str, mission: str, stage: str | None) -> bool:
        instance = draft.engine.instances.get(mission)
        if instance is None:
            return True
        return (instance.failure in ('expired', 'abandoned') or instance.state == 'turned_in'
            or owner in instance.withdrawn or bool(stage and stage not in {
                f'{p.stage.id}:{p.attempt}' for p in instance.stages[:instance.index+1]}))

    def clean_mission_data(self, draft: Ledger, patches: dict[str, Any],
                           identities: dict[str, Any]) -> set[str]:
        """Remove expired payloads and their source metadata in the same write."""
        removed: set[str] = set()
        for player in self.game.players.values():
            progress = deepcopy(player.progress)
            progress.update(deepcopy(patches.get(player.id, {}).get('progress', {})))
            records = progress.get('mission_sources', {})
            dead = {key: row for key, row in records.items()
                    if self.obsolete_mission(draft, player.id, row['mission'], row['mission_stage'])}
            if not dead:
                continue
            identity = deepcopy(identities.get(player.bbs_user_id, self.game.identity(player.bbs_user_id)))
            for key, row in dead.items():
                unit = row['unit']
                records.pop(key)
                progress.get('lattice_units', {}).pop(unit, None)
                if progress.get('lattice_receipts', {}).get(key) == unit:
                    progress['lattice_receipts'].pop(key)
                if identity.get('lattice_receipts', {}).get(key) == unit:
                    identity['lattice_receipts'].pop(key)
                for asset, recorded in tuple(progress.get('lattice_records', {}).items()):
                    if recorded == unit:
                        progress['lattice_records'].pop(asset)
                removed.add(key)
            patch = patches.setdefault(player.id, {}).setdefault('progress', {})
            for key in ('mission_sources', 'lattice_units', 'lattice_receipts', 'lattice_records'):
                if key in progress:
                    patch[key] = progress[key]
            identities[player.bbs_user_id] = identity
        return removed

    def write(self, draft: Ledger, patches: dict[str, dict[str, Any]] | None = None,
              identities: dict[str, dict[str, Any]] | None = None,
              items: dict[str, ItemInstance] | None = None, serial: int | None = None,
              callback: Callable[[bool], None] | None = None,
              linked_control: tuple[str, StageTarget] | None = None) -> None:
        staged = {'player_id': None, 'patch': {}, 'player_patches': deepcopy(patches or {}),
                  'identities': deepcopy(identities or {}), 'callback': callback or (lambda success: None)}
        self.finish_services(staged, draft)
        if linked_control:
            self.lat.interlock.join_manual_release(staged, *linked_control)
        patches, identities, callback = staged['player_patches'], staged['identities'], staged['callback']
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
        removed = self.clean_mission_data(draft, patches, identities)
        if removed:
            previous = callback
            def cleaned(success: bool) -> None:
                if success:
                    for key in removed:
                        self.lat.sources.sources.pop(key, None)
                    self.lat.sources.revision += 1
                if previous:
                    previous(success)
            callback = cleaned
        if not self.commerce.settle(None, {}, self.commerce.items if items is None else items,
                self.commerce.caches, self.commerce.serial if serial is None else serial,
                callback or (lambda success: None)):
            raise ValueError('The city is busy. Try again.')
        effect = self.commerce.outbox[-1]
        effect['player_patches'] = deepcopy(patches or {})
        effect['identities'] = deepcopy(identities or {})
        if 'interlock_state' in staged:
            effect['interlock_state'] = staged['interlock_state']
        if removed:
            def source_record() -> dict[str, Any]:
                lattice = self.lat.sources.record(self.clock.now_tick())
                for key in removed:
                    lattice['sources'].pop(key, None)
                return lattice
            effect['lattice_state'] = source_record
        join_state(effect, draft.record(), self.install)

    def source_fact(self, effect: dict[str, Any], fact: Fact) -> tuple[str, ...]:
        """Source owners call this before their own write, never on commit."""
        draft = Ledger(self.origin, self.content, effect.get('contracts_state') or self.record())
        changed = self.observe(draft, fact)
        if changed:
            self.finish_services(effect, draft)
            join_state(effect, draft.record(), self.install)
        return changed

    def observe(self, draft: Ledger, fact: Fact) -> tuple[str, ...]:
        """Count actual nearby guards; the ledger filters the frozen roster."""
        now, crews = self.clock.now_tick(), self.game.crews
        guarded = {pid for (source, pid), tick in crews.guarded_at.items()
                   if source == fact.actor and now-tick <= PARTICIPATION_SECONDS*TICK_HZ
                   and crews.nearby(source, pid)}
        verified = replace(fact, contributors=tuple(sorted({*fact.contributors, *guarded})))
        return draft.observe(verified, self.now())

    def finish_services(self, effect: dict[str, Any], draft: Ledger) -> None:
        """Join allocation, fixed worker rewards and source patches once.

        A final data lift may already award run XP. Apply the work-order
        award to that source's player/identity drafts, preserving both.
        """
        notifications = []
        for instance in draft.engine.instances.values():
            sid = instance.runtime.get('service')
            if not instance.service or instance.state != 'complete' or sid not in draft.services.nodes:
                continue
            node = draft.services.nodes[sid]
            if node.state != 'repairing':
                continue
            draft.services.complete(sid, instance, self.now())
            caller = next(p.player for p in instance.roster if p.player in instance.contributions
                          and p.player not in instance.withdrawn)
            payouts = draft.claim(instance.id, caller, self.now(), excluded=tuple(self.game.deleting))
            for payout in payouts:
                player = self.game.players[payout.player]
                primary = effect.get('player_id') == player.id
                patch = deepcopy(effect['patch'] if primary else effect.get('player_patches', {}).get(player.id, {}))
                recipient = deepcopy(player)
                actor = self.game.combat.actor(player)
                if actor:
                    recipient.health, recipient.stamina, recipient.shock = actor.health, actor.stamina, actor.shock
                for key, value in patch.items():
                    setattr(recipient, key, {**recipient.progress, **deepcopy(value)} if key == 'progress' else deepcopy(value))
                identity = deepcopy(effect.get('identity') if primary and effect.get('identity') is not None else
                    effect.get('identities', {}).get(player.bbs_user_id, self.game.identities[player.bbs_user_id]))
                result = award(recipient, identity, Grant('contract', payout.receipt, True,
                    scope='contract:'+instance.template, amount=payout.payment.xp), self.clock.now_utc(),
                    self.progression.modifiers(recipient))
                recipient.chits_hand += payout.payment.chits
                apply_vector(recipient, self.content.factions, payout.payment.standing, payout.payment.standing_mode)
                for key in ('xp', 'grade', 'attributes', 'health', 'legal_at', 'chits_hand', 'standing'):
                    if getattr(recipient, key) != getattr(player, key):
                        patch[key] = deepcopy(getattr(recipient, key))
                patch['progress'] = {key: value for key, value in recipient.progress.items()
                                     if key not in player.progress or player.progress[key] != value}
                if primary:
                    # settled_patch compares this primary progress against
                    # its original base; retain unchanged source keys too.
                    patch['progress'] = deepcopy(recipient.progress)
                    effect['patch'], effect['identity'] = patch, identity
                else:
                    effect.setdefault('player_patches', {})[player.id] = patch
                    effect.setdefault('identities', {})[player.bbs_user_id] = identity
                notifications.append((player, payout, result))
        if notifications:
            previous = effect.get('callback')
            def committed(success: bool) -> None:
                if previous:
                    previous(success)
                if success:
                    for player, payout, result in notifications:
                        self.game.factions.refresh(player)
                        self.progression.notify_reward(player, result)
                        self.log(player.id, f'Work order settled: {payout.payment.chits} chits, {payout.payment.xp} XP.')
            effect['callback'] = committed

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
            if any(target.data == data and (
                    target.kind == 'core_room' and not presence.descent
                    and target.core == presence.core and target.room == presence.room
                    or target.kind == 'silt_data' and presence.descent
                    and target.sector == presence.sector
                    and target.band == self.content.silt.bands[presence.depth].id)
                    for target in progress.targets):
                return f'{instance.id}:{progress.stage.id}:{progress.attempt}'
        return None

    def control_permit(self, player: str, core: str, control: str) -> bool:
        if self.effects.permits(player, core, control):
            return True
        if self.state.permits_target(player, 'maintenance_credential',
                StageTarget('core_control', core=core, control=control), self.now()):
            return True
        return any(target.kind == 'core_control' and target.core == core and target.control == control
            for _, progress in self.current_jobs(player)
            for target in (*progress.targets, *((progress.stage.linked_control,) if progress.stage.linked_control else ())))

    def network_fact(self, effect: dict[str, Any], player: str, target: StageTarget,
                     completion: str, receipt: str) -> tuple[str, ...]:
        for instance, progress in self.current_jobs(player):
            linked = progress.stage.linked_control
            actual = progress.stage.target if linked and matches(linked, target) else target
            if progress.stage.completion == completion and any(matches(t, actual) for t in progress.targets):
                return self.source_fact(effect, Fact(player, progress.stage.verb, completion, actual,
                    receipt, receipt, instance=instance.id, stage=progress.stage.id, attempt=progress.attempt))
        return ()

    def lifted(self, effect: dict[str, Any], presence: Any, data: Any, unit: str) -> None:
        target = (StageTarget('silt_data', sector=presence.sector,
            band=self.content.silt.bands[presence.depth].id, data=data.id) if presence.descent else
            StageTarget('core_room', core=presence.core, room=presence.room, data=data.id))
        self.network_fact(effect, presence.player_id, target, 'lifted', unit)
        if data.kind == 'evidence' and data.asset in self.content.evidence:
            draft = Ledger(self.origin, self.content, effect.get('contracts_state') or self.record())
            if draft.acquire(presence.player_id, self.content.evidence[data.asset], target, self.now(), season=self.lat.season):
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

    def propose_service(self, player: str, sid: str, allocation: str,
                        roster: tuple[str, ...]) -> Proposal:
        node = self.state.services.nodes[sid]
        if node.state != 'fault' or self.now() >= node.fault_expires:
            raise ValueError('That service has no open fault. Read its current state.')
        template = self.content.services[sid]
        if allocation not in {a.id for a in template.allocations}:
            raise ValueError('Choose a listed service allocation.')
        offer = self.state.engine.offer(self.content.contracts[template.contract],
            f'{self.origin}:service-preview:{sid}:{node.generation}:{node.revision}', node.fault_expires)
        proposal = self.propose(player, offer, roster)
        proposal.service, proposal.allocation, proposal.service_revision = sid, allocation, node.revision
        return proposal

    def queue_user(self, player: str, action: Callable[[], None]) -> None:
        def execute() -> None:
            if player not in self.game.players or player in self.game.deleting:
                return
            try:
                action()
            except (ValueError, KeyError) as exc:
                self.log(player, str(exc) if isinstance(exc, ValueError) else 'That contract changed. Read its current card.')
        self.commerce.enqueue_system(execute)

    def withdraw(self, draft: Ledger, iid: str, player: str) -> None:
        instance = draft.engine.instances[iid]
        draft.engine.withdraw(iid, player)
        if instance.service:
            draft.services.withdraw(instance.runtime['service'], instance.offer, player)

    def retry(self, draft: Ledger, iid: str, player: str) -> None:
        instance = draft.engine.instances[iid]
        if instance.service:
            node = draft.services.nodes[instance.runtime['service']]
            if node.state != 'repairing' or node.order != instance.offer:
                raise ValueError('That reservation ended. Read the current work order.')
        draft.engine.retry(iid, player, self.now())

    def consent(self, proposal: str, player: str) -> None:
        offered = self.proposals[proposal]
        if player not in offered.roster or not self.game.combat.session(player):
            raise ValueError('That proposal is not yours.')
        if offered.offer.until is not None and self.now() >= offered.offer.until:
            raise ValueError('That proposal expired. Read the current board.')
        offered.consent.add(player)

    def start(self, proposal: str, player: str) -> None:
        if self.commerce.pending:
            self.queue_user(player, lambda: self.start(proposal, player)
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
        offer = offered.offer
        if offered.service:
            node = draft.services.reserve(offered.service, offered.allocation, offered.roster,
                                          self.now(), offered.service_revision)
            offer = draft.engine.offer(self.content.contracts[offer.template], node.order, node.reserved_until)
        instance = draft.engine.accept(offer, tuple(self.participant(pid) for pid in offered.roster),
                                       self.now(), offered.approach)
        if instance.season is None:
            instance.season = self.lat.season
        if offered.service:
            instance.runtime['service'] = offered.service
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
                if not can_acquire(program, recipient.archetype, recipient.standing, set(acquired.get(season, ()))):
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
            self.queue_user(player, lambda: self.claim(iid, player, option))
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
        self.effects.compose(ctx.tick)
        self.scenes.reconcile()
        self.scenes.escorts(ctx.tick)
        expired_data = any(self.obsolete_mission(self.state, player.id, row['mission'], row['mission_stage'])
            for player in self.game.players.values() for row in player.progress.get('mission_sources', {}).values())
        if not self.commerce.pending and (expired_data or any(self.obsolete(item, self.state) for item in self.commerce.items.values())):
            self.write(self.state.fork())
