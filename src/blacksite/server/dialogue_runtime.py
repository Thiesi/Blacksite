"""Authoritative talker menus; actions retain their subsystem's checks."""

from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from blacksite.content.schema import DialogueNode, Offer
from blacksite.server.clock import TICK_HZ
from blacksite.server.commerce import CommerceMenu
from blacksite.server.contracts.panels import Panel as ContractPanel
from blacksite.server.dialogue import BARK_RADIUS, BarkScheduler, Facts, eligible_offers, evaluate
from blacksite.server.factions import relation
from blacksite.server.loop import TickContext
from blacksite.server.protocol import Frame
from blacksite.server.sessions import Session
from blacksite.server.wake import menu
from blacksite.server.world.simulation import MENU_TIMEOUT_SECONDS


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


class Dialogue:
    def __init__(self, core: Any) -> None:
        self.core, self.game, self.clock = core, core.characters, core.clock
        self.content, self.world, self.commerce = self.game.content, core.world, core.commerce
        self.sim = self.game.sim
        self.menus: dict[str, TalkerMenu] = {}
        self.barks = BarkScheduler()
        # S26 binds only its committed settlement. No placement or pending
        # finale proposal supplies a historical outcome.
        self.season_facts: Callable[[Any], SeasonFacts] = lambda player: SeasonFacts()

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
            if did in self.content.dialogue and self.content.active('dialogue', did):
                found.append(Contact(did, obj.spec.id, zone.id, obj.spec.tile))
        for actor in zone.actors.values():
            template = self.content.npcs.get(actor.behaviour.get('template'))
            if template and template.dialogue in self.content.dialogue and actor.health > 0:
                did = template.dialogue
                if self.content.active('dialogue', did) and actor.stance not in ('down', 'dead'):
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
            if (did in self.content.dialogue and self.content.active('dialogue', did)
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
                 and zone.entry_policy(actor, contact.tile)]
        found.sort(key=lambda contact: (contact.tile != actor.position, contact.target))
        return found[0] if found else None

    def close(self, session: Session) -> None:
        self.menus.pop(session.id, None)
        self.sim.external_views.pop(session.id, None)
        avatar = self.sim.avatars.get(session.user_id)
        if avatar:
            self.sim.reset_view(session, avatar)

    def show(self, session: Session, contact: Contact, text: str, tick: int) -> None:
        if session.closed or self.contact(session, contact.target) is None:
            return
        self.menus[session.id] = TalkerMenu(contact, text, tick)
        talker = self.content.dialogue[contact.talker]
        if contact.lattice:
            self.core.lattice.log(session, talker.name+': '+text)
        else:
            self.sim.log(session, talker.name+': '+text)
        self.publish(session)

    def open(self, session: Session, contact: Contact, tick: int) -> None:
        talker = self.content.dialogue[contact.talker]
        facts = self.facts(session, talker)
        line = evaluate(talker, facts, self.world.zones[contact.zone].rng).text
        if talker.id in facts.met:
            self.show(session, contact, line, tick)
            return
        player = self.game.players[session.player_id]
        progress = deepcopy(player.progress)
        progress['met_talkers'] = sorted(facts.met | {talker.id})
        def committed(success: bool) -> None:
            if success:
                # A read-only inventory may have opened during the write.
                # Record the encounter without overwriting another menu.
                external = self.sim.external_views.get(session.id)
                if ((external is None or contact.lattice and external[0] == 'lattice')
                        and session.id not in self.commerce.menus):
                    self.show(session, contact, line, tick)
            else:
                self.commerce.toast(session, 'The introduction could not be saved. Try again.')
        if not self.commerce.settle(player, {'progress': progress}, self.commerce.items,
                                     self.commerce.caches, self.commerce.serial, committed):
            raise ValueError('Let the current transfer settle before talking.')

    def publish(self, session: Session) -> None:
        screen = self.menus[session.id]
        talker = self.content.dialogue[screen.contact.talker]
        offers = eligible_offers(talker, self.facts(session, talker))
        title = talker.name+(' - '+talker.title if talker.title else '')
        body = menu(title, [], 0, screen.line, 'Choose an action  Esc/B leaves')
        body['kind'] = 'talker'
        body['actions'] = [{'key': offer.hotkey.lower(), 'label': offer.label} for offer in offers]
        body['actions'].append({'key': 'b', 'label': 'Back'})
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
                offer_id = next((job.id for job in owner.state.engine.board(template.giver, owner.now())
                                 if job.template == template.id), '')
            self.board(session, template.giver, offer_id)
        elif offer.kind == 'service' and offer.ref in self.content.services:
            service = self.content.services[offer.ref]
            self.board(session, self.content.contracts[service.contract].giver, 'service:'+service.id)
        elif offer.kind in ('vendor', 'service'):
            vendor = self.content.vendors[offer.ref]
            self.commerce.vendor(session, vendor.object_id)
            self.close(session)
            if offer.kind == 'service':
                self.core.progression.clinics.open(session, vendor.object_id)
            else:
                self.commerce.menus[session.id] = CommerceMenu('vendor', vendor.object_id,
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
        elif offer.kind == 'travel':
            avatar = self.sim.avatars[session.user_id]
            exits = sorted((ex for ex in self.world.zones[avatar.zone].template.meta.exits
                            if not ex.hidden and max(abs(ex.tile[0]-avatar.actor.x),
                                                     abs(ex.tile[1]-avatar.actor.y)) <= 1),
                           key=lambda ex: (ex.tile != avatar.actor.position, ex.id))
            if not exits or exits[0].target_zone != offer.ref:
                raise ValueError('Stand beside that route before choosing travel.')
            self.close(session)
            self.sim.interact(session, avatar, self.clock.now_tick())

    def input(self, session: Session, frame: Frame, tick: int) -> bool:
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
                return True
            external = self.sim.external_views.get(session.id)
            network = bool(session.player_id in self.core.lattice.presences and external and external[0] == 'lattice')
            if (name not in ('talk', 'interact') and key != 'e'
                    or session.pending_prompts or external and not network
                    or session.id in self.sim.maps or session.id in self.commerce.menus):
                return False
            contact = self.contact(session, frame.data.get('args', {}).get('target', '') if name == 'talk' else '')
            if contact:
                self.open(session, contact, tick)
                return True
        except (ValueError, KeyError) as exc:
            self.commerce.toast(session, str(exc) if isinstance(exc, ValueError) else 'That contact is unavailable.')
            return True
        return False

    def tick(self, ctx: TickContext) -> None:
        if not self.content.dialogue:
            return
        for sid, screen in tuple(self.menus.items()):
            session = self.core.sessions.active.get(sid)
            if not session:
                self.menus.pop(sid, None)
                self.sim.external_views.pop(sid, None)
                continue
            contact = self.contact(session, screen.contact.target)
            if (contact is None or ctx.tick-screen.opened >= MENU_TIMEOUT_SECONDS*TICK_HZ
                    and self.world.zones[contact.zone].allows_hostile(contact.tile)):
                self.close(session)
            else:
                self.publish(session)
        if ctx.tick % TICK_HZ:
            return
        interacting = {screen.contact.talker for screen in self.menus.values()}
        for zone in self.world.zones.values():
            sessions = [session for session in ctx.sessions
                        if (avatar := self.sim.avatars.get(session.user_id)) and avatar.zone == zone.id]
            if not sessions:
                continue
            for contact in self.contacts(zone):
                nearby = [session for session in sessions
                          if (self.sim.avatars[session.user_id].actor.x-contact.tile[0])**2
                          + (self.sim.avatars[session.user_id].actor.y-contact.tile[1])**2 <= BARK_RADIUS**2]
                talker = self.content.dialogue[contact.talker]
                bark = self.barks.choose(talker, ctx.tick, zone.rng, nearby=bool(nearby),
                                         interacting=talker.id in interacting)
                if bark:
                    for session in nearby:
                        self.sim.log(session, talker.name+': '+bark.text)
