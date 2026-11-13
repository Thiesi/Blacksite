"""Authoritative talker menus; actions retain their subsystem's checks."""

from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from karst41.content.schema import DialogueNode, Exit, Offer
from karst41.server.ambience import Ambience
from karst41.server.clock import TICK_HZ
from karst41.server.commerce import CommerceMenu
from karst41.server.contracts.panels import Panel as ContractPanel
from karst41.server.dialogue import Facts, eligible_offers, evaluate
from karst41.server.factions import relation
from karst41.server.interaction import Focus, Interaction, interact, key_action
from karst41.server.views import presentation
from karst41.server.loop import TickContext
from karst41.server.protocol import Frame
from karst41.server.sessions import Session
from karst41.server.wake import menu
from karst41.server.world.simulation import MENU_TIMEOUT_SECONDS


@dataclass(frozen=True)
class SeasonFacts:
    stage: str = 'open'
    balance: int = 0
    choices: Mapping[int, str] | None = None


@dataclass(frozen=True)
class Contact:
    talker: str
    target: str
    zone: str
    tile: tuple[int, int]
    lattice: bool = False


@dataclass
class TalkerMenu:
    contact: Contact
    line: str
    opened: int
    caller_zone: str
    caller_tile: tuple[int, int]
    hit_serial: int


class Dialogue:
    def __init__(self, core: Any) -> None:
        self.core, self.game, self.clock = core, core.characters, core.clock
        self.content, self.world, self.commerce = self.game.content, core.world, core.commerce
        self.sim = self.game.sim
        self.menus: dict[str, TalkerMenu] = {}
        if core.npcs:
            core.npcs.talking = lambda sid, aid: (sid in self.menus
                and not self.menus[sid].contact.lattice
                and self.menus[sid].contact.target == aid)
        # S26 binds only its committed settlement. No placement or pending
        # finale proposal supplies a historical outcome.
        self.season_facts: Callable[[Any], SeasonFacts] = lambda player: SeasonFacts()
        # P8: the one ambient emitter (architecture 5.5.3).
        self.ambience = Ambience(self.world, self.content, self.sim, self.clock,
                                 threatened=self.threatened, talking=self.talking)

    def talking(self, actor_id: str) -> bool:
        """Game 13.4: a talker is silent while anyone is interacting with it."""
        return any(screen.contact.target == actor_id and not screen.contact.lattice
                   for screen in self.menus.values())

    def playing(self, session: Session) -> bool:
        return (session.player_id in self.game.players and not self.game.menu_open(session)
                and session.id not in self.game.screens)

    def threatened(self, session: Session, actor: Any) -> bool:
        """The declared danger inputs, read from server state (P5/P12 fields).

        A channel, a hostile target, a hazard warning in sight, or a
        down/dead stage. HUNTED or MARKED alone is not threatened (S44).
        """
        if actor.behaviour.get('channel'):
            return True
        player = self.game.players.get(session.player_id)
        if player and player.progress.get('combat', {}).get('stage') in ('down', 'dead'):
            return True
        zone = self.world.zones.get(actor.zone)
        target = zone.actors.get(actor.target) if zone and actor.target else None
        if target is not None and self.core.combat and self.core.combat.presented_relation(actor, target) == 'hostile':
            return True
        return bool(zone and any(tile in actor.visible for layer in zone.layers.values()
                                 for tile in layer.layout.warning_tiles))

    def facts(self, session: Session, talker: DialogueNode) -> Facts:
        player = self.game.players[session.player_id]
        contracts = self.core.contracts
        assigned = {job.template: job.index for job in contracts.state.engine.instances.values()
                    if job.state in ('active', 'complete', 'failed') and job.failure != 'expired'
                    and player.id in {member.player for member in job.roster}-job.withdrawn}
        completed = frozenset(contracts.state.engine.completed.get(player.id, ()))
        receipts = frozenset(job.branch_group for tid in completed
                             if (job := self.content.contracts.get(tid)) and job.branch_group)
        season = self.season_facts(player)
        marked = bool(player.marked_until and
                      datetime.fromisoformat(player.marked_until) > self.clock.now_utc())
        return Facts(grade=player.grade, archetype=player.archetype, faction=player.faction,
            standing=dict(player.standing), legal=player.legal_at is not None, marked=marked,
            enemy=relation(self.content.factions, player.faction, talker.faction) == 'H',
            balance=season.balance, met=frozenset(player.progress.get('met_talkers', ())),
            items=frozenset(self.commerce.items[iid].template for iid in player.inventory
                            if iid in self.commerce.items and self.commerce.items[iid].owner == player.id),
            contracts=assigned, completed=completed,
            evidence=frozenset(contracts.state.journal.get(player.id, ())), receipts=receipts,
            services={sid: node.state for sid, node in contracts.state.services.nodes.items()},
            season_stage=season.stage, chronicle=dict(season.choices or {}),
            events=frozenset(eid for eid in self.content.events if contracts.event_active(eid)))

    def contacts(self, zone: Any) -> list[Contact]:
        found = []
        for obj in zone.objects.values():
            did = obj.spec.params.get('dialogue')
            if (did in self.content.dialogue and not self.content.dialogue[did].machine_mind
                    and self.content.active('dialogue', did)):
                found.append(Contact(did, obj.spec.id, zone.id, obj.spec.tile))
        for actor in zone.actors.values():
            template = self.content.npcs.get(actor.behaviour.get('template'))
            if template and template.dialogue in self.content.dialogue and actor.health > 0:
                did = template.dialogue
                if (not self.content.dialogue[did].machine_mind and self.content.active('dialogue', did)
                        and actor.stance not in ('down', 'dead')):
                    found.append(Contact(did, actor.id, zone.id, actor.position))
        return found

    def contact(self, session: Session, target: str = '') -> Contact | None:
        if not isinstance(target, str):
            raise ValueError('Choose a nearby talker.')
        presence = self.core.lattice.presences.get(session.player_id)
        if presence is not None:
            if presence.core:
                return None
            cell = self.core.lattice.sectors.cells[presence.sector][presence.cell]
            did = cell.dialogue
            cid = 'cell:'+presence.sector+':'+cell.id
            if (did in self.content.dialogue and not self.content.dialogue[did].machine_mind
                    and self.content.active('dialogue', did)
                    and (not target or target == cid)):
                actor = self.sim.avatars[session.user_id].actor
                return Contact(did, cid, actor.zone, actor.position, True)
            return None
        if not self.commerce.ready(session):
            return None
        actor = self.sim.avatars[session.user_id].actor
        zone = self.world.zones[actor.zone]
        found = [contact for contact in self.contacts(zone)
                 if (not target or contact.target == target)
                 and max(abs(contact.tile[0]-actor.x), abs(contact.tile[1]-actor.y)) <= 1
                  and zone.entry_policy(actor, contact.tile)
                  and (self.core.combat.visible(actor, zone.actors[contact.target])
                       if contact.target in zone.actors
                       else self.world.object_access(actor, zone.objects[contact.target].spec))]
        found.sort(key=lambda contact: (contact.tile != actor.position, contact.target))
        return found[0] if found else None

    def close(self, session: Session) -> None:
        self.menus.pop(session.id, None)
        self.sim.external_views.pop(session.id, None)
        avatar = self.sim.avatars.get(session.user_id)
        if avatar:
            self.sim.reset_view(session, avatar)

    def show(self, session: Session, contact: Contact, text: str, tick: int) -> bool:
        if session.closed or self.contact(session, contact.target) is None:
            return False
        caller = self.sim.avatars[session.user_id].actor
        self.menus[session.id] = TalkerMenu(contact, text, tick, caller.zone,
                                          caller.position, int(caller.behaviour.get('hit_serial', 0)))
        talker = self.content.dialogue[contact.talker]
        actor = self.world.zones[contact.zone].actors.get(contact.target)
        if actor is not None and not contact.lattice:
            self.sim.speak(session, actor, text)
        else:
            session.emit(talker.name+': '+text, kind='speech',
                         channel='lat' if contact.lattice else 'zone',
                         role='chan_lat' if contact.lattice else 'chan_zone',
                         at=self.clock.now_utc().isoformat(),
                         speaker=talker.name, speaker_role='service')
        self.publish(session)
        return True

    def undo_meeting(self, player: Any, talker: str) -> None:
        """Compensate a committed introduction that never reached the caller."""
        def restore() -> None:
            progress = deepcopy(player.progress)
            progress['met_talkers'] = sorted(set(progress.get('met_talkers', ())) - {talker})
            self.commerce.settle(player, {'progress': progress}, self.commerce.items,
                                 self.commerce.caches, self.commerce.serial, lambda success: None)
        try:
            self.commerce.enqueue_system(restore)
        except ValueError:
            # A full commerce queue may leave the encounter met and lose
            # its first line. Never bypass durability to repair live state.
            pass

    def open(self, session: Session, contact: Contact, tick: int) -> None:
        talker = self.content.dialogue[contact.talker]
        facts = self.facts(session, talker)
        line = evaluate(talker, facts, self.world.zones[contact.zone].rng).text
        if talker.id in facts.met:
            self.show(session, contact, line, tick)
            return
        player = self.game.players[session.player_id]
        progress = deepcopy(player.progress)
        progress['met_talkers'] = sorted((facts.met & self.content.dialogue.keys()) | {talker.id})
        def committed(success: bool) -> None:
            if success:
                # A read-only inventory may have opened during the write.
                external = self.sim.external_views.get(session.id)
                if ((external is None or contact.lattice and external[0] == 'lattice')
                        and session.id not in self.commerce.menus):
                    if self.show(session, contact, line, tick):
                        return
                self.undo_meeting(player, talker.id)
            else:
                self.commerce.toast(session, 'The introduction could not be saved. Try again.')
        if not self.commerce.settle(player, {'progress': progress}, self.commerce.items,
                                     self.commerce.caches, self.commerce.serial, committed):
            raise ValueError('Let the current transfer settle before talking.')

    def publish(self, session: Session) -> None:
        screen = self.menus[session.id]
        talker = self.content.dialogue[screen.contact.talker]
        offers = eligible_offers(talker, self.facts(session, talker))
        actor = self.world.zones[screen.contact.zone].actors.get(screen.contact.target)
        label = talker.name
        if actor is not None:
            template = self.content.npcs.get(actor.behaviour.get('template'))
            if template and template.presents:
                viewer = self.sim.avatars[session.user_id].actor
                label = presentation.name(actor, viewer, self.content)
        title = label+(' - '+talker.title if talker.title else '')
        hint = ('Choose an action; move' if offers else 'Move') + ' or Esc/B leaves'
        body = menu(title, [], 0, screen.line,
                    'Choose an action  Esc/B leaves' if screen.contact.lattice else hint)
        body['kind'] = 'talker'
        body['walk_away'] = not screen.contact.lattice
        body['actions'] = [{'key': offer.hotkey.lower(), 'label': offer.label} for offer in offers]
        # P12: no 'b Back' action; b and Esc close the page in the client.
        self.sim.external_views[session.id] = 'menu', body

    def board(self, session: Session, giver: str, wanted: str = '') -> None:
        actor = self.sim.avatars[session.user_id].actor
        objects = self.world.zones[actor.zone].objects.values()
        target = next((obj.spec.id for obj in objects
                       if obj.spec.params.get('contract_handler') == giver
                       and max(abs(obj.spec.tile[0]-actor.x), abs(obj.spec.tile[1]-actor.y)) <= 1), '')
        panels = self.core.contracts.panels
        handler = panels.station(session, target)
        panel = ContractPanel(self.clock.now_tick(), target, handler)
        self.close(session)
        panels.menus[session.id] = panel
        rows = panels.rows(session, panel)
        panel.cursor = next((index for index, row in enumerate(rows) if row['id'] == wanted), 0)

    def dispatch(self, session: Session, offer: Offer) -> None:
        if self.menus[session.id].contact.lattice:
            raise ValueError('Return to the physical counter to use this service.')
        if offer.kind == 'contract':
            template = self.content.contracts[offer.ref]
            owner = self.core.contracts
            offer_id = next((job.id for job in owner.state.engine.instances.values()
                             if job.template == template.id
                             and session.player_id in {member.player for member in job.roster}), '')
            if not offer_id:
                offer_id = (template.id if template.story else next(
                    (job.id for job in owner.state.engine.board(template.giver, owner.now())
                     if job.template == template.id), ''))
            self.board(session, template.giver, offer_id)
        elif offer.kind == 'service' and offer.ref in self.content.services:
            service = self.content.services[offer.ref]
            self.board(session, self.content.contracts[service.contract].giver, 'service:'+service.id)
        elif offer.kind in ('vendor', 'service'):
            actor = self.sim.avatars[session.user_id].actor
            contact = self.menus[session.id].contact
            counters = sorted((obj for obj in self.world.zones[actor.zone].objects.values()
                               if obj.spec.params.get('vendor') == offer.ref
                               and max(abs(obj.spec.tile[0]-actor.x), abs(obj.spec.tile[1]-actor.y)) <= 1),
                              key=lambda obj: (obj.spec.id != contact.target,
                                               obj.spec.tile != actor.position, obj.spec.id))
            if not counters:
                raise ValueError('Stand beside that counter before choosing its terms.')
            target = counters[0].spec.id
            self.commerce.vendor(session, target)
            if offer.kind == 'service':
                self.core.progression.clinics.counter(session, target)
            self.close(session)
            if offer.kind == 'service':
                self.core.progression.clinics.open(session, target)
            else:
                self.commerce.menus[session.id] = CommerceMenu('vendor', target,
                                                              opened=self.clock.now_tick())
        elif offer.kind == 'recruit':
            target = self.menus[session.id].contact.target
            factions = self.core.factions.station(session, target)
            if offer.ref not in factions:
                raise ValueError('That contact cannot recruit for this faction.')
            self.close(session)
            self.core.factions.input(session, Frame('intent', {
                'name': 'faction.open', 'args': {'target': target}}), self.clock.now_tick())
            self.core.factions.menus[session.id].cursor = factions.index(offer.ref)
        elif offer.kind == 'ask':
            # Entities 1.11 (S44): the question as the caller's speech, the
            # answer as the talker's, which replaces the page line. Grants nothing.
            screen = self.menus[session.id]
            talker = self.content.dialogue[screen.contact.talker]
            answer = next(line.text for line in talker.lines if line.id == offer.ref)
            player = self.game.players[session.player_id]
            session.emit(f'{player.name}: {offer.asks}', kind='speech', channel='zone', role='chan_zone',
                         at=self.clock.now_utc().isoformat(), speaker=player.name, speaker_role='caller')
            screen.line = answer
            actor = self.world.zones[screen.contact.zone].actors.get(screen.contact.target)
            if actor is not None:
                self.sim.speak(session, actor, answer)
            else:
                session.emit(talker.name+': '+answer, kind='speech', channel='zone', role='chan_zone',
                             at=self.clock.now_utc().isoformat(), speaker=talker.name, speaker_role='service')
            self.publish(session)
        elif offer.kind == 'travel':
            avatar = self.sim.avatars[session.user_id]
            choice = self.sim.interaction_target(avatar)
            if (not isinstance(choice.value, Exit) or choice.value.hidden
                    or choice.value.target_zone != offer.ref):
                raise ValueError('Stand beside that route before choosing travel.')
            self.close(session)
            self.sim.interact(session, avatar, self.clock.now_tick(), choice=choice)

    def interaction(self, session: Session, frame: Frame) -> Interaction | None:
        if session.player_id not in self.game.players:
            return None
        if session.id in self.menus:
            return Interaction()
        name = frame.data.get('name', '') if frame.type == 'intent' else ''
        external = self.sim.external_views.get(session.id)
        network = bool(session.player_id in self.core.lattice.presences and external and external[0] == 'lattice')
        if (not (interact(frame) or name == 'talk') or session.pending_prompts
                or external and not network or session.id in self.game.screens
                or session.id in self.sim.maps or session.id in self.commerce.menus):
            return None
        target = frame.data.get('args', {}).get('target', '') if name == 'talk' else ''
        if not isinstance(target, str):
            return Interaction()
        contact = self.contact(session, target)
        if contact is None:
            return None
        talker = self.content.dialogue[contact.talker]
        actor = self.world.zones[contact.zone].actors.get(contact.target)
        viewer = self.sim.avatars[session.user_id].actor
        label = presentation.name(actor, viewer, self.content) if actor else talker.name
        return Interaction(Focus(contact.target, label, 'talk to'), contact,
                           None if contact.lattice else contact.tile,
                           actor.id if actor else None, kind='dialogue')

    def input(self, session: Session, frame: Frame, tick: int, *, interaction: Interaction | None = None) -> bool:
        name = frame.data.get('name', '') if frame.type == 'intent' else ''
        key = frame.data.get('k', '').lower() if frame.type == 'key' else ''
        screen = self.menus.get(session.id)
        try:
            if screen:
                if name == 'menu_close' or key in ('escape', 'b'):
                    self.close(session)
                else:
                    value = frame.data.get('args', {}).get('key', '') if name == 'menu_select' else key
                    action = value.lower() if isinstance(value, str) else ''
                    if name == 'menu_select' and frame.data.get('expected_revision') != session.view_revision:
                        return True
                    talker = self.content.dialogue[screen.contact.talker]
                    offer = next((offer for offer in eligible_offers(talker, self.facts(session, talker))
                                  if offer.hotkey.lower() == action), None)
                    if offer:
                        self.dispatch(session, offer)
                    elif not screen.contact.lattice:
                        movement = key_action(self.core.keymap, session, frame)
                        if movement in ('move', 'sprint') or movement.startswith(('move_', 'sprint_')):
                            self.close(session)
                            return False
                return True
            if interaction is not None and interaction.kind != 'dialogue':
                return False  # The composite route selected a mission or board.
            choice = interaction or self.interaction(session, frame)
            if choice is not None:
                if choice.value is not None:
                    self.open(session, choice.value, tick)
                return True
        except (ValueError, KeyError) as exc:
            self.commerce.toast(session, str(exc) if isinstance(exc, ValueError) else 'That contact is unavailable.')
            return True
        return False

    def tick(self, ctx: TickContext) -> None:
        self.ambience.tick(ctx.tick, ctx.sessions, self.playing)
        if not self.content.dialogue:
            return
        for sid, screen in tuple(self.menus.items()):
            session = self.core.sessions.active.get(sid)
            if not session:
                self.menus.pop(sid, None)
                self.sim.external_views.pop(sid, None)
                continue
            caller = self.sim.avatars[session.user_id].actor
            if int(caller.behaviour.get('hit_serial', 0)) != screen.hit_serial:
                self.close(session)
                continue
            contact = self.contact(session, screen.contact.target)
            if (contact is None or ctx.tick-screen.opened >= MENU_TIMEOUT_SECONDS*TICK_HZ
                    and self.world.zones[contact.zone].allows_hostile(contact.tile)):
                target = self.world.actors.get(screen.contact.target)
                if (contact is None and not screen.contact.lattice and target is not None
                        and target.health > 0 and target.stance not in ('down', 'dead')
                        and (caller.zone, caller.position) == (screen.caller_zone, screen.caller_tile)
                        and (target.zone != caller.zone or max(abs(target.x-caller.x), abs(target.y-caller.y)) > 1)):
                    session.emit(presentation.name(target, caller, self.content)+' walks off.',
                                 kind='system', channel='system', role='muted',
                                 at=self.clock.now_utc().isoformat())
                self.close(session)
            else:
                self.publish(session)
