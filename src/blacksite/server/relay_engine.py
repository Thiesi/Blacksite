"""Game 7.4/7.7: committed relay ownership and explicit live channels."""

from blacksite.server.interaction import Interaction
from blacksite.server.protocol import Frame
from collections.abc import Callable
from copy import deepcopy
from typing import Any

from blacksite.server.clock import TICK_HZ
from blacksite.server.loop import TickContext
from blacksite.server.players import Player
from blacksite.server.progression import Grant, award
from blacksite.server.relays import CAPTURE_STANDING, SOLO_HOLD_SECONDS, Claims, Ledger, Participant
from blacksite.server.sessions import Session

HOLD_PERIOD_SECONDS = 600  # Game 3.5: 10 XP per active ten minutes.
INFLUENCE_CHECK_SECONDS = 60  # Checkpoint cadence; exact points use UTC.
CAPTURE_RETRY_SECONDS = 1  # Game 7.4: one save retry per second after failure.


class Relays:
    def __init__(self, core: Any, state: dict[str, Any]) -> None:
        self.core = core
        progression = core.progression
        self.progression, self.game = progression, progression.game
        self.commerce, self.content, self.clock = progression.commerce, progression.content, progression.clock
        self.sim, self.world, self.lat = progression.sim, self.game.world, progression.lattice
        self.ledger = Ledger(state)
        self.claims = Claims()
        self.paid_holds: dict[str, int] = {}
        self.capture_retry_at: dict[str, int] = {}
        self.last_settle = self.clock.now_tick()
        self.curfew: Callable[[str], bool] = lambda zone: core.factions.curfew(zone)  # S24's shared provider.
        self.level_open: Callable[[], bool] = lambda: False  # S26.
        self.game.relays = self
        self.lat.interlock.claim_of = self.claim_of
        self.lat.interlock.control_committed = self.control_committed
        attached = self.game.attached
        def on_attach(session: Session, player: Player) -> None:
            attached(session, player)
            self.commerce.enqueue_system(lambda: self.login_share(player.id))
        self.game.attached = on_attach
        from blacksite.server.relay_views import Views
        self.views = Views(self)
        from blacksite.server.relay_benefits import Benefits
        self.benefits = Benefits(self)
        self.benefits.refresh()
        from blacksite.server.relay_passages import Passages
        self.passages = Passages(self)

    def now(self) -> float:
        return self.clock.now_utc().timestamp()

    def record(self) -> dict[str, Any]:
        return self.ledger.record()

    def active(self, rid: str) -> bool:
        relay = self.content.relays.get(rid)
        return bool(relay and self.content.active('relays', rid)
                    and (not relay.requires_level or self.level_open()))

    def rates(self) -> dict[str, int]:
        return {rid: relay.rate for rid, relay in self.content.relays.items()}

    def participant(self, player: Player) -> Participant:
        return Participant(player.id, player.bbs_user_id, player.faction)

    def log(self, pid: str, message: str) -> None:
        session = self.game.combat.session(pid)
        if session:
            self.sim.log(session, message)
            self.commerce.toast(session, message)

    def near(self, pid: str, rid: str) -> bool:
        relay = self.content.relays.get(rid)
        actor = self.world.actors.get(pid)
        zone = self.world.zones.get(relay.zone) if relay else None
        terminal = zone.objects.get(relay.terminal) if zone else None
        return bool(actor and terminal and actor.zone == relay.zone
                    and max(abs(actor.x-terminal.spec.tile[0]), abs(actor.y-terminal.spec.tile[1])) <= 1)

    def owner(self, rid: str, at: float | None = None) -> str | None:
        return self.ledger.owner(rid, at)

    def benefit(self, player: Player, kind: str, zone: str | None = None, at: float | None = None) -> float | None:
        for rid, relay in self.content.relays.items():
            if (not self.active(rid) or relay.benefit.kind != kind or not player.faction
                    or self.owner(rid, at) != player.faction):
                continue
            if zone is not None:
                spec = self.world.zones.get(zone)
                if relay.benefit.district:
                    if not spec or spec.template.meta.district != relay.benefit.district:
                        continue
                elif zone != relay.zone:
                    continue
            return float(relay.benefit.amount)
        return None

    def start(self, session: Session, rid: str) -> None:
        actor = self.world.actors.get(session.player_id)
        if (not self.active(rid) or not self.near(session.player_id, rid)
                or not self.commerce.ready(session) or not actor or actor.stance != 'normal'
                or actor.behaviour.get('channel')):
            raise ValueError('Stand beside the relay, out of stealth and free of other channels, to hold it.')
        relay = self.content.relays[rid]
        if self.curfew(relay.zone):
            raise ValueError('Curfew pauses relay claims. Return when it ends.')
        player = self.game.players[session.player_id]
        claim = self.claims.start(rid, self.participant(player))
        actor = self.world.actors[player.id]
        actor.behaviour['channel'] = {'owner': 'relay', 'label': relay.name, 'remaining': SOLO_HOLD_SECONDS}
        self.world.zones[actor.zone].revision += 1
        self.log(player.id, f'You hold {relay.name}. 8 min alone; 3 min with a named runner. B withdraws.')

    def support(self, session: Session, cid: str) -> None:
        claim = self.claims.active.get(cid)
        if not claim or not self.near(session.player_id, claim.relay) or not self.commerce.ready(session):
            raise ValueError('Read the named claim beside its relay before supporting it.')
        self.claims.support(cid, self.participant(self.game.players[session.player_id]))
        self.log(session.player_id, 'Runner support accepted. Complete relay_open in this core for this claim.')

    def withdraw(self, pid: str, rid: str | None = None) -> None:
        holder = next((c for c in self.claims.active.values() if c.holder.player == pid), None)
        clears_channel = rid is None or holder is not None and holder.relay == rid
        self.claims.withdraw(pid, rid)
        actor = self.world.actors.get(pid)
        if clears_channel and actor and actor.behaviour.get('channel', {}).get('owner') == 'relay':
            actor.behaviour.pop('channel')
            if actor.zone:
                self.world.zones[actor.zone].revision += 1

    def disconnect(self, pid: str) -> None:
        # A completed runner action stays attributed through disconnect.
        # The physical holder cannot keep a channel alive while absent.
        self.cancel_hold(pid)

    def cancel_hold(self, pid: str) -> None:
        for cid, claim in tuple(self.claims.active.items()):
            if claim.holder.player == pid:
                self.claims.active.pop(cid)
        actor = self.world.actors.get(pid)
        if actor and actor.behaviour.get('channel', {}).get('owner') == 'relay':
            actor.behaviour.pop('channel')
            if actor.zone:
                self.world.zones[actor.zone].revision += 1

    def claim_of(self, pid: str, core: str, control: str) -> str:
        if control != 'relay_open':
            return ''
        return next((c.id for c in self.claims.active.values() if pid in c.supporters
                     and self.content.relays[c.relay].core == core), '')

    def control_committed(self, pid: str, core: str, control: str, cid: str) -> None:
        claim = self.claims.active.get(cid)
        if (claim and control == 'relay_open' and self.content.relays[claim.relay].core == core
                and self.claims.hack(cid, pid)):
            self.log(claim.holder.player, 'Your named runner opens the core. The three-minute hold now applies.')
            self.log(pid, 'Core opening committed to your named claim.')

    def write(self, draft: Ledger, patches: dict[str, dict[str, Any]] | None = None,
              identities: dict[str, dict[str, Any]] | None = None,
              interlock: dict[str, Any] | None = None,
              callback: Callable[[bool], None] = lambda success: None) -> bool:
        def finished(success: bool) -> None:
            if success:
                self.ledger = draft
                if interlock is not None:
                    self.lat.interlock.state = interlock
                    self.lat.interlock.compose()
                    self.benefits.refresh()
                for pid in patches or {}:
                    self.progression.sync_actor(self.game.players[pid])
                for relay in self.content.relays.values():
                    if relay.zone in self.world.zones:
                        self.world.zones[relay.zone].revision += 1
            callback(success)
        if not self.commerce.settle(None, {}, self.commerce.items, self.commerce.caches,
                                    self.commerce.serial, finished):
            return False
        effect = self.commerce.outbox[-1]
        effect['relays_state'] = draft.record()
        effect['player_patches'] = deepcopy(patches or {})
        effect['identities'] = deepcopy(identities or {})
        if interlock is not None:
            effect['interlock_state'] = deepcopy(interlock)
        return True

    def ownership_patch(self, rid: str, faction: str | None) -> dict[str, Any]:
        core = self.content.relays[rid].core
        proposal = deepcopy(self.lat.interlock.state)
        proposal['cores'].setdefault(core, {})['owner_faction'] = faction
        if self.owner(rid) != faction:
            proposal['effects'] = {key: effect for key, effect in proposal['effects'].items()
                if effect['core'] != core or effect['expires'] is not None}
        return proposal

    def capture(self, cid: str) -> bool:
        claim = self.claims.active.get(cid)
        if (not claim or claim.elapsed < claim.required
                or self.owner(claim.relay) == claim.faction or self.commerce.pending
                or self.clock.now_tick() < self.capture_retry_at.get(cid, 0)):
            return False
        draft = self.ledger.fork()
        capture = draft.capture(claim, self.now(), self.rates())
        patches, identities = {}, {}
        receipt = str(draft.state['serial'])
        for person in capture.rewarded:
            player = self.game.players.get(person.player)
            if not player or player.id in self.game.deleting:
                continue
            avatar = self.sim.avatars.get(player.bbs_user_id)
            if avatar:
                self.game.snapshot(player, avatar)
            recipient = deepcopy(player)
            identity = identities.setdefault(player.bbs_user_id, deepcopy(self.game.identity(player.bbs_user_id)))
            award(recipient, identity, Grant('relay_capture', receipt, eligible=True, scope=claim.relay), self.clock.now_utc(), self.progression.modifiers(recipient))
            changes = {claim.faction: CAPTURE_STANDING} if person.faction == claim.faction else {}
            if person.player == claim.holder.player and capture.former:
                changes[capture.former] = changes.get(capture.former, 0)-CAPTURE_STANDING
            if self.game.factions:
                recipient.standing = self.game.factions.standing_patch(recipient, changes, 'explicit').get('standing', recipient.standing)
            recipient.stats['relays'] = recipient.stats.get('relays', 0)+1
            patches[player.id] = {key: deepcopy(getattr(recipient, key)) for key in
                                 ('xp', 'grade', 'attributes', 'health', 'legal_at', 'progress', 'standing', 'stats')
                                 if getattr(recipient, key) != getattr(player, key)}
        draft.state['captures'][-1]['rewarded'] = list(patches)
        def finished(success: bool) -> None:
            if success:
                self.capture_retry_at.pop(cid, None)
                audience = {person.player for person in capture.participants}
                audience.update(player.id for player in self.game.players.values()
                    if player.faction == capture.faction
                    or capture.former is not None and player.faction == capture.former)
                relay_name = self.content.relays[claim.relay].name
                faction_name = self.content.factions[claim.faction].short
                for pid in audience:
                    player = self.game.players.get(pid)
                    message = (f'Your faction loses {relay_name} to {faction_name}.'
                        if player and capture.former and player.faction == capture.former
                        else f'{relay_name} belongs to {faction_name}.')
                    self.log(pid, message)
                claim.supporters.clear()
            else:
                first_failure = cid not in self.capture_retry_at
                self.capture_retry_at[cid] = self.clock.now_tick()+CAPTURE_RETRY_SECONDS*TICK_HZ
                if first_failure:
                    self.log(claim.holder.player, 'Capture cannot be saved. Keep holding; retries follow once a second.')
        return self.write(draft, patches, identities, self.ownership_patch(claim.relay, claim.faction), finished)

    def hold_xp(self) -> bool:
        for claim in self.claims.active.values():
            periods = claim.elapsed//(HOLD_PERIOD_SECONDS*TICK_HZ)
            paid = self.paid_holds.get(claim.id, 0)
            if periods <= paid:
                continue
            player = self.game.players[claim.holder.player]
            avatar = self.sim.avatars.get(player.bbs_user_id)
            if avatar:
                self.game.snapshot(player, avatar)
            recipient = deepcopy(player)
            identity = deepcopy(self.game.identity(player.bbs_user_id))
            source = f'{self.now():.6f}:{claim.id}:{periods}'
            grant = award(recipient, identity, Grant('relay_hold', source, eligible=True, scope=claim.relay,
                periods=periods-paid), self.clock.now_utc(), self.progression.modifiers(recipient))
            if grant is None:
                self.paid_holds[claim.id] = periods
                continue
            patches = {player.id: {key: deepcopy(getattr(recipient, key)) for key in
                                  ('xp', 'grade', 'attributes', 'health', 'legal_at', 'progress')
                                  if getattr(recipient, key) != getattr(player, key)}}
            def finished(success: bool, cid: str = claim.id, count: int = periods,
                         pid: str = player.id, xp: int = grant.xp) -> None:
                if success:
                    self.paid_holds[cid] = count
                    self.log(pid, f'Active relay hold: {xp} XP.')
            return self.write(self.ledger.fork(), patches, {player.bbs_user_id: identity}, callback=finished)
        return False

    def login_share(self, pid: str) -> None:
        player = self.game.players.get(pid)
        if not player or not player.faction or player.id in self.game.deleting:
            return
        draft = self.ledger.fork()
        draft.settle(self.rates(), self.now())
        amount = draft.daily_share(player.bbs_user_id, player.faction, self.clock.now_utc().date().isoformat())
        if amount:
            self.write(draft, {pid: {'chits_hand': player.chits_hand+amount}}, callback=lambda success:
                self.log(pid, f'Your faction treasury pays your daily share: {amount} chits.') if success else None)

    def tick(self, context: TickContext) -> None:
        conscious, present = set(), set()
        for claim in self.claims.active.values():
            player = self.game.players.get(claim.holder.player)
            actor = self.world.actors.get(claim.holder.player)
            session = self.game.combat.session(claim.holder.player)
            if (not player or not actor or not session or session.closed or player.faction != claim.faction
                    or actor.stance != 'normal' or actor.health <= 0):
                continue
            conscious.add(player.id)
            if self.near(player.id, claim.relay) and actor.behaviour.get('channel', {}).get('owner') == 'relay':
                present.add(player.id)
        before = {c.holder.player for c in self.claims.active.values()}
        ready = self.claims.step(context.tick, conscious, present,
            {rid for rid, relay in self.content.relays.items() if self.active(rid) and self.curfew(relay.zone)})
        self.capture_retry_at = {cid: deadline for cid, deadline in self.capture_retry_at.items()
                                 if cid in self.claims.active}
        after = {c.holder.player for c in self.claims.active.values()}
        for pid in before-after:
            self.cancel_hold(pid)
            self.log(pid, 'Your relay claim ends.')
        for claim in self.claims.active.values():
            actor = self.world.actors.get(claim.holder.player)
            if actor and actor.behaviour.get('channel', {}).get('owner') == 'relay':
                actor.behaviour['channel']['remaining'] = max(0, (claim.required-claim.elapsed)/TICK_HZ)
        self.views.tick(context.tick)
        if not self.commerce.pending:
            for claim in ready:
                if self.owner(claim.relay) != claim.faction and self.capture(claim.id):
                    return
            if self.hold_xp():
                return
            if context.tick-self.last_settle >= INFLUENCE_CHECK_SECONDS*TICK_HZ:
                draft = self.ledger.fork()
                draft.settle(self.rates(), self.now())
                if draft.record() == self.record() or self.write(draft):
                    self.last_settle = context.tick

    def interaction(self, session: Session, frame: Frame) -> Interaction | None:
        return self.views.interaction(session, frame) if True else None

    def input(self, session: Session, frame: Any, tick: int, *, interaction: Interaction | None = None) -> bool:
        return self.views.input(session, frame, tick, interaction=interaction)

    def admin(self, command: str, data: dict[str, Any], reply: Callable[[Any], None]) -> None:
        if command == 'relay.list':
            reply({'ok': True, 'relays': [{'id': rid, 'zone': relay.zone, 'active': self.active(rid),
                'faction': self.owner(rid), 'rate': relay.rate,
                'held_seconds': max(0, self.now()-self.ledger.state['relays'].get(rid, {}).get('captured_at', self.now()))}
                for rid, relay in self.content.relays.items()], 'factions': deepcopy(self.ledger.state['factions'])})
            return
        if self.commerce.pending:
            self.commerce.enqueue_system(lambda: self.admin(command, data, reply))
            return
        try:
            rid, faction = data.get('relay', ''), data.get('faction')
            if command != 'relay.set' or not self.active(rid):
                raise ValueError('Choose a commissioned relay; future authoring entries cannot be owned.')
            faction = None if faction == 'neutral' else faction
            if faction is not None and faction not in self.content.factions:
                raise ValueError('Choose a faction ID or neutral.')
            if self.owner(rid) == faction:
                reply({'ok': True, 'relay': rid, 'faction': faction, 'changed': False})
                return
            draft = self.ledger.fork()
            draft.set_owner(rid, faction, None, self.now(), self.rates())
            def finished(success: bool) -> None:
                if success:
                    for claim in tuple(self.claims.active.values()):
                        if claim.relay == rid:
                            self.cancel_hold(claim.holder.player)
                reply({'ok': success, 'relay': rid, 'faction': faction if success else self.owner(rid),
                       'changed': success})
            self.write(draft, interlock=self.ownership_patch(rid, faction), callback=finished)
        except ValueError as exc:
            reply({'ok': False, 'error': str(exc)})

    def reset_season(self, season: int, cutoff: float) -> bool:
        draft = self.ledger.fork()
        draft.reset_season(season, cutoff, self.rates())
        interlock = deepcopy(self.lat.interlock.state)
        cores = {relay.core for relay in self.content.relays.values()}
        for core in cores:
            interlock['cores'].setdefault(core, {})['owner_faction'] = None
        interlock['effects'] = {key: effect for key, effect in interlock['effects'].items()
            if effect['core'] not in cores or effect['expires'] is not None}
        def finished(success: bool) -> None:
            if success:
                for claim in tuple(self.claims.active.values()):
                    self.withdraw(claim.holder.player)
        return self.write(draft, interlock=interlock, callback=finished)
