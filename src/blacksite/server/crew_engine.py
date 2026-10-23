"""Game 10: live social crew adapter, consent and authorized views."""

from collections import deque
from dataclasses import asdict, dataclass
from dataclasses import replace
from typing import Any
from math import ceil

from blacksite.server.crews import (Registry, LootOffer, OFFER_SECONDS,
    GUARD_SECONDS, PARTICIPATION_SECONDS, SILT_SHARE_SECONDS)
from blacksite.server.clock import TICK_HZ
from blacksite.server.crews import shared_xp
from blacksite.server.progression import Grant, amount
from blacksite.server.skills import Use, eligible
from blacksite.server.loop import TickContext
from blacksite.server.protocol import Frame
from blacksite.server.sessions import Session
from blacksite.server.wake import menu
from blacksite.server.world.actors import Actor
from blacksite.server.world.sight import private_visible
from blacksite.server.world.simulation import MENU_TIMEOUT_SECONDS


@dataclass
class CrewMenu:
    cursor: int
    opened: int
    confirmation: tuple[str, str] | None = None


class Crews:
    def __init__(self, progression: Any, chat: Any) -> None:
        self.progression, self.game, self.chat = progression, progression.game, chat
        self.sim, self.lat = progression.sim, progression.lattice
        self.clock, self.content = progression.clock, progression.content
        self.combat, self.world = self.game.combat, self.game.world
        asset = self.content.text.get('crew')
        self.messages = dict(line.split(': ', 1) for line in asset.body.splitlines() if ': ' in line) if asset else {}
        self.registry = Registry(self.game.sessions.origin, self.clock.now_utc().isoformat())
        self.menus: dict[str, CrewMenu] = {}
        self.requests: dict[str, list[str]] = {}
        self.announced: set[str] = set()
        self.guards: dict[tuple[str, str], tuple[int, int]] = {}
        self.guarded_at: dict[tuple[str, str], int] = {}
        self.actions: dict[str, int] = {}
        self.linked_controls: dict[tuple[str, str], int] = {}
        self.silt_entries: dict[tuple[str, str], list[tuple[str, tuple[str, ...], int]]] = {}
        self.game.crews = self
        progression.crew_of = self.crew_id
        self.lat.crew_of = self.crew_id
        chat.crew_of = lambda session: self.crew_id(session.player_id)
        chat.crew_label = lambda session: self.label(session.player_id)
        self.combat.crew_together = self.together
        self.combat.allies_provider = self.allies
        old_target = self.sim.target_provider
        def target(actor: Actor) -> dict[str, Any] | None:
            result = old_target(actor) if old_target else None
            if result and self.together(actor.id, result['id']):
                result.update(relation='crew', warning=self.text('friendly_fire'))
                other = self.world.actors.get(result['id'])
                if other and not other.marked:
                    result['name_role'] = 'player_crew'
            return result
        self.sim.target_provider = target
        self.sim.crew_view = self.decorate
        attached = self.game.attached
        def on_attach(session: Session, player: Any) -> None:
            attached(session, player)
            if player.bbs_user_id not in self.announced:
                self.announced.add(player.bbs_user_id)
                self.log(player.id, self.text('restart'))
        self.game.attached = on_attach

    def crew_id(self, player: str) -> str | None:
        return self.registry.memberships.get(player)

    def text(self, message: str, **values: str) -> str:
        return self.messages.get(message, message.replace('_', ' ')).format(**values)

    def label(self, player: str) -> str:
        crew = self.registry.crew_of(player)
        return self.name(crew.leader)+"'s crew" if crew else 'none'

    def owner(self, actor: Actor) -> str:
        return str(actor.behaviour.get('interlock_initiator') or
                   (actor.owner if actor.behaviour.get('player_drone') else actor.id))

    def together(self, one: str, other: str) -> bool:
        a, b = self.world.actors.get(one), self.world.actors.get(other)
        return self.registry.together(self.owner(a) if a else one, self.owner(b) if b else other)

    def allies(self, actor: Actor) -> list[Actor]:
        crew = self.registry.crew_of(self.owner(actor))
        return [a for a in self.world.actors.values() if a.kind == 'player'
                and (a.id == actor.id or crew and a.id in crew.members)
                and a.zone == actor.zone and private_visible(actor, a)]

    def session(self, pid: str) -> Session | None:
        return self.combat.session(pid)

    def log(self, pid: str, text: str) -> None:
        session = self.session(pid)
        if session:
            self.sim.log(session, text)
            self.chat.toast(session, text)

    def name(self, pid: str) -> str:
        player = self.game.players.get(pid)
        return player.name if player else 'Another Wake'

    def changed(self, members: tuple[str, ...], text: str) -> None:
        for pid in members:
            self.log(pid, text)
        # Remote health/zone and relation changes must invalidate both views.
        for zone in self.world.zones.values():
            if any(a.id in members for a in zone.actors.values()):
                zone.revision += 1

    def disconnect(self, session: Session) -> None:
        self.menus.pop(session.id, None)
        self.requests.pop(session.id, None)
        change = self.registry.remove(session.player_id)
        self.guards = {pair: times for pair, times in self.guards.items() if session.player_id not in pair}
        self.actions.pop(session.player_id, None)
        if change:
            self.changed(change.before, self.text('left', name=self.name(session.player_id))+' '+
                         (self.text('dissolved') if change.dissolved else
                          self.text('leader', name=self.name(change.leader))))

    def perform(self, session: Session, verb: str, target: str = '') -> None:
        pid, tick = session.player_id, self.clock.now_tick()
        if verb in ('invite', 'kick', 'promote', 'beacon') and target and target not in self.game.players:
            match = self.chat.target(target)
            if not match:
                raise ValueError('Choose a unique online character name.')
            target = match.player_id
        if verb == 'invite':
            recipient = self.session(target)
            if not recipient or target not in self.game.players:
                raise ValueError('Choose an online character.')
            if session.user_id in self.chat.settings(recipient).get('ignored', []):
                raise ValueError('That caller is not accepting crew invitations.')
            pending = any(i.inviter == pid and i.target == target and i.until_tick > tick
                          for i in self.registry.invites.values())
            self.registry.invite(pid, target, tick)
            if pending:
                return  # Holding I never floods another caller's log or refreshes consent.
            self.log(target, self.text('invite_received', name=self.name(pid)))
            self.log(pid, self.text('invite_sent', name=self.name(target)))
        elif verb == 'accept':
            invitation = self.registry.offered(pid, target, tick)
            if not self.session(invitation.inviter):
                raise ValueError('The inviter has left. Ask again when they return.')
            crew = self.registry.accept(pid, target, tick)
            self.actions.pop(pid, None)
            self.changed(crew.members, self.text('joined', name=self.name(pid)))
        elif verb == 'decline':
            self.registry.decline(pid, target, tick)
            self.log(pid, self.text('declined'))
        elif verb in ('leave', 'kick'):
            change = self.registry.leave(pid) if verb == 'leave' else self.registry.kick(pid, target)
            self.actions.pop(pid if verb == 'leave' else target, None)
            self.changed(change.before, self.text('left', name=self.name(pid if verb == 'leave' else target))+' '+
                         (self.text('dissolved') if change.dissolved else self.text('leader', name=self.name(change.leader))))
        elif verb == 'promote':
            self.registry.promote(pid, target)
            self.changed(self.registry.crew_of(pid).members, self.text('leader', name=self.name(target)))
        elif verb == 'invites':
            crew = self.registry.leader(pid)
            self.registry.invitations_allowed(pid, not crew.allow_invites)
            self.changed(crew.members, self.text('invites_open' if crew.allow_invites else 'invites_closed'))
        elif verb == 'loot':
            crew = self.registry.leader(pid)
            self.registry.loot_mode(pid, target)
            self.changed(crew.members, self.text('loot', mode='free for all' if target == 'ffa' else 'round robin'))
        elif verb == 'beacon':
            self.registry.beacon(pid, target or None, self.game.players[pid].archetype == 'operator')
            self.changed(self.registry.crew_of(pid).members, self.text('beacon_set', name=self.name(target)) if target else self.text('beacon_clear'))
        else:
            raise ValueError('Choose an offered crew action.')

    def contribution(self, pid: str, use: Use) -> None:
        # A meaningful completed action counts even when today's skill cap is full.
        if eligible(use) and use.action in ('weapon_hit', 'melee_hit', 'armour_absorb',
                'drone_command', 'hymn_restore', 'dissonance_threat', 'program_change'):
            self.actions[pid] = self.clock.now_tick()

    def local(self, one: str, other: str) -> bool:
        a, b = self.lat.presences.get(one), self.lat.presences.get(other)
        if a and a.core and self.clock.now_tick()-self.linked_controls.get((other, a.core), -10000) <= PARTICIPATION_SECONDS*TICK_HZ:
            return True
        if b and b.core and self.clock.now_tick()-self.linked_controls.get((one, b.core), -10000) <= PARTICIPATION_SECONDS*TICK_HZ:
            return True
        if a or b:
            if a and b:
                return self.lat.encounters.location(a)[0] == self.lat.encounters.location(b)[0]
            presence, guard = (a, other) if a else (b, one)
            actor = self.combat.actor(self.game.players[guard])
            runner = self.combat.actor(self.game.players[presence.player_id])
            # The retained physical body is the linked body-guard objective.
            return bool(actor and runner and actor.zone and actor.zone == runner.zone
                        and private_visible(actor, runner) and private_visible(runner, actor))
        actors = [self.combat.actor(self.game.players[pid]) for pid in (one, other)]
        return bool(all(actors) and actors[0].zone and actors[0].zone == actors[1].zone
                    and private_visible(actors[0], actors[1]) and private_visible(actors[1], actors[0]))

    def nearby(self, one: str, other: str) -> bool:
        if not self.local(one, other):
            return False
        a, b = self.lat.presences.get(one), self.lat.presences.get(other)
        if a and b:
            # Room/cell co-presence is exact; separate branches are not guarding.
            return self.lat.encounters.location(a) == self.lat.encounters.location(b)
        actors = [self.combat.actor(self.game.players[pid]) for pid in (one, other)]
        return bool(all(actors) and sum((x-y)**2 for x, y in zip(actors[0].position, actors[1].position)) <= 36)

    def control_committed(self, player: str, core: str) -> None:
        self.linked_controls[player, core] = self.clock.now_tick()
        self.actions[player] = self.clock.now_tick()

    def add_rewards(self, effect: dict[str, Any], source: Any, grant: Grant) -> None:
        """Join recipient XP/identity drafts to the source's existing receipt."""
        crew = self.registry.crew_of(source.id)
        base = amount(grant, source)
        if not crew or grant.kind not in ('combat', 'run') or base <= 0:
            return
        now = self.clock.now_tick()
        awards = []
        for pid in crew.members:
            player = self.game.players[pid]
            if pid == source.id or not self.session(pid) or pid in self.game.deleting or not self.local(source.id, pid):
                continue
            guarded = now-self.guarded_at.get((source.id, pid), -10000) <= PARTICIPATION_SECONDS*TICK_HZ
            if not guarded and now-self.actions.get(pid, -10000) > PARTICIPATION_SECONDS*TICK_HZ:
                continue
            patch, identity, result = self.progression.reward_patch(player, replace(grant,
                shared_base=shared_xp(base, source.grade, player.grade)))
            if not result:
                continue
            if 'progress' in patch:
                patch['progress'] = {key: value for key, value in patch['progress'].items()
                                     if key not in player.progress or value != player.progress[key]}
            effect.setdefault('player_patches', {})[pid] = patch
            effect.setdefault('identities', {})[player.bbs_user_id] = identity
            awards.append((player, result))
        committed = effect.get('callback')
        def finished(success: bool) -> None:
            if committed:
                committed(success)
            if success:
                for player, result in awards:
                    self.progression.notify_reward(player, result, crew=True)
        effect['callback'] = finished

    def stage_cache(self, effect: dict[str, Any], cache: str, killer: str) -> None:
        """Freeze recovery rights and rotation in the cache's creation receipt."""
        if cache not in effect['caches']:
            return
        offer = self.registry.offer(killer, self.clock.now_tick())
        if not offer:
            return
        row = effect['caches'][cache]
        row['crew_offer'] = {**asdict(offer), 'until': self.clock.now_utc().timestamp()+OFFER_SECONDS}
        committed = effect.get('callback')
        def finished(success: bool) -> None:
            if success:
                self.registry.commit_offer(offer)
                if offer.mode == 'round_robin':
                    self.log(offer.recipient, self.offer_label(row['crew_offer']))
            if committed:
                committed(success)
        effect['callback'] = finished

    def offer_label(self, offer: dict[str, Any]) -> str:
        remaining = ceil(max(0, offer.get('until', 0)-self.clock.now_utc().timestamp()))
        if offer.get('mode') == 'round_robin' and remaining:
            return f"Crew turn: {self.name(offer['recipient'])} ({remaining}s)."
        return ''

    def cache_permits(self, player: str, cache: dict[str, Any], now: float) -> bool:
        if player == cache.get('victim'):
            return True
        offer = cache.get('crew_offer')
        if not offer:
            return cache.get('private_until', 0) <= now or player == cache.get('killer')
        # The drop's frozen roster remains meaningful after a leave or restart.
        if offer['mode'] == 'round_robin' and now < offer['until'] and player != offer['recipient']:
            return False
        return (player in offer['members'] or player == cache.get('killer')
                or now >= cache.get('private_until', 0))

    def data_offer(self, player: str, unit: str) -> LootOffer | None:
        offers = self.lat.sources.crew_offers
        saved = offers.get(unit)
        if saved:
            return LootOffer(saved['crew_id'], tuple(saved['members']), saved['mode'],
                saved['recipient'], self.clock.now_tick()+max(0, round((saved['until']-self.clock.now_utc().timestamp())*TICK_HZ)), saved['version'])
        offer = self.registry.offer(player, self.clock.now_tick())
        if offer:
            offers[unit] = {**asdict(offer), 'until': self.clock.now_utc().timestamp()+OFFER_SECONDS}
            self.lat.sources.revision += 1
        return offer

    def check_data(self, player: str, unit: str) -> LootOffer | None:
        offer = self.data_offer(player, unit)
        if offer and not offer.permits(player, self.clock.now_tick()):
            raise ValueError('Crew round-robin: '+self.offer_label(self.lat.sources.crew_offers[unit]))
        return offer

    def shared_silt(self, player: str, entrance: tuple[str, str]) -> str | None:
        for descent, roster, until in reversed(self.silt_entries.get(entrance, [])):
            if player in roster and self.clock.now_tick() < until:
                return descent
        return None

    def remember_silt(self, player: str, entrance: tuple[str, str], descent: str) -> None:
        crew = self.registry.crew_of(player)
        if crew:
            self.silt_entries.setdefault(entrance, []).append((descent, crew.members, self.clock.now_tick()+SILT_SHARE_SECONDS*TICK_HZ))

    def retains_silt(self, descent: str, tick: int) -> bool:
        return any(e[0] == descent and tick < e[2] for entries in self.silt_entries.values() for e in entries)

    def direction(self, source: str, destination: str) -> str:
        queue = deque([(source, '')])
        seen = {source}
        while queue:
            zone, first = queue.popleft()
            template = self.content.zones.get(zone)
            if not template:
                continue
            for ex in template.meta.exits:
                if ex.hidden or ex.target_zone in seen:
                    continue
                label = first or self.content.zones[ex.target_zone].meta.name
                if ex.target_zone == destination:
                    return label
                seen.add(ex.target_zone)
                queue.append((ex.target_zone, label))
        return 'elsewhere'

    def roster(self, pid: str) -> list[dict[str, Any]]:
        crew = self.registry.crew_of(pid)
        if not crew:
            return []
        viewer = self.combat.actor(self.game.players[pid])
        result = []
        for member in sorted(crew.members, key=lambda p: (p != crew.leader, crew.members.index(p))):
            player = self.game.players[member]
            actor = self.combat.actor(player)
            presence = self.lat.presences.get(member)
            private = bool(actor and viewer and not private_visible(viewer, actor))
            remote_silt = bool(presence and presence.instance and
                (not self.lat.presences.get(pid) or self.lat.presences[pid].instance != presence.instance))
            zone = 'private' if private else 'in transit' if not actor or not actor.zone else self.world.zones[actor.zone].template.meta.name
            if presence and not private:
                zone = 'jack / Silt' if presence.descent else 'jack / '+self.content.sectors[presence.sector].district
            health, maximum = (presence.integrity, presence.integrity_max) if presence else (actor.health, actor.health_max) if actor else (player.health, 1)
            result.append({'id': member, 'name': player.name, 'hp_pct': max(0, min(100, int(health*100/maximum))),
                'zone': zone, 'jacked': bool(presence), 'leader': member == crew.leader,
                'beacon': bool(crew.beacon and member == crew.beacon[1]),
                'direction': '' if private or remote_silt or not actor or not actor.zone or not viewer or not viewer.zone
                    else 'here' if viewer.zone == actor.zone else self.direction(viewer.zone, actor.zone)})
        return result

    def decorate(self, session: Session, body: dict[str, Any]) -> None:
        pid = session.player_id
        crew = self.registry.crew_of(pid)
        body['crew'] = self.roster(pid)
        body.setdefault('me', {})['crew'] = ({'id': crew.id, 'leader': crew.leader, 'loot': crew.loot} if crew else None)
        if not crew:
            return
        for entry in body.get('actors', []):
            if entry['id'] != pid and entry['id'] in crew.members:
                actor = self.world.actors.get(entry['id'])
                if actor and not actor.marked:
                    entry['role'] = 'player_crew'
        for entry in body.get('nearby', []):
            if entry['id'] in crew.members:
                entry['relation'] = '+'
                actor = self.world.actors.get(entry['id'])
                if actor and not actor.marked:
                    entry['role'] = 'player_crew'
        if crew.beacon and body.get('viewport'):
            target = self.world.actors.get(crew.beacon[1])
            viewer = self.world.actors.get(pid)
            if target and viewer and target.zone == viewer.zone and private_visible(viewer, target):
                body['objects'].append({'id': 'crew-beacon', 'kind': 'beacon', 'x': target.x, 'y': target.y,
                    'glyph': '+', 'role': 'player_crew', 'state': {}})

    def body(self, session: Session, screen: CrewMenu) -> dict[str, Any]:
        pid = session.player_id
        crew = self.registry.crew_of(pid)
        rows = [{'id': r['id'], 'cells': [r['name'], str(r['hp_pct'])+'%', r['zone'], 'leader' if r['leader'] else 'member']}
                for r in self.roster(pid)]
        invitations = [i for i in self.registry.invites.values() if i.target == pid]
        rows += [{'id': i.id, 'cells': [self.name(i.inviter), 'invitation', str(max(0, (i.until_tick-self.clock.now_tick())//10))+'s']}
                 for i in invitations]
        rows += [{'id': s.player_id, 'cells': [self.name(s.player_id), 'online', 'invite']}
                 for s in self.chat.online() if s.player_id != pid and not self.registry.crew_of(s.player_id)]
        screen.cursor = max(0, min(screen.cursor, len(rows)-1))
        selected = rows[screen.cursor]['id'] if rows else ''
        actions = [{'key': 't', 'label': 'crew chat'}]
        if any(i.id == selected for i in invitations):
            actions += [{'key': 'a', 'label': 'accept'}, {'key': 'd', 'label': 'decline'}]
        elif selected and not self.registry.crew_of(selected) and (not crew or crew.leader == pid or crew.allow_invites):
            actions.append({'key': 'i', 'label': 'invite'})
        if crew:
            actions.append({'key': 'l', 'label': 'leave'})
            if crew.leader == pid:
                actions += [{'key': 'm', 'label': 'member invites'}, {'key': 'r', 'label': 'round robin'}, {'key': 'f', 'label': 'free for all'}]
                if selected in crew.members and selected != pid:
                    actions += [{'key': 'k', 'label': 'kick'}, {'key': 'p', 'label': 'promote'}]
            if self.game.players[pid].archetype == 'operator':
                actions.append({'key': 'c', 'label': 'clear beacon'})
                if selected in crew.members:
                    actions.append({'key': 'o', 'label': 'beacon'})
        detail = 'Select an online character to invite. Invitations last 60 seconds.'
        if crew:
            detail = 'Loot: '+('free for all' if crew.loot == 'ffa' else 'round robin')+'. Member invitations: '+('open' if crew.allow_invites else 'leader only')+'.\nLogout leaves the crew; a lone member dissolves it.'
            member = next((r for r in self.roster(pid) if r['id'] == selected), None)
            if member and member['beacon']:
                detail += '\nBeacon: '+member['zone']+'\nRoute: '+(member['direction'] or 'Location stays private.')
        if screen.confirmation:
            verb, target = screen.confirmation
            detail = 'Confirm '+verb+(' '+self.name(target) if target else '')+'? Y confirms; Esc/B cancels.'
            actions = [{'key': 'y', 'label': 'confirm'}]
        body = menu('CREW', rows, screen.cursor, detail, 'Esc/B returns  T crew chat')
        body.update(kind='crew', columns=['Name', 'Health', 'Zone', 'Role'], actions=actions)
        return body

    def close(self, session: Session) -> None:
        self.menus.pop(session.id, None)
        self.sim.external_views.pop(session.id, None)
        self.sim.published.pop(session.id, None)
        session.needs_full_view = True

    def input(self, session: Session, frame: Frame, tick: int) -> bool:
        if not self.chat.ready(session):
            return False
        name = frame.data.get('name', '') if frame.type == 'intent' else ''
        args = frame.data.get('args', {})
        key = frame.data.get('k', '') if frame.type == 'key' else ''
        screen = self.menus.get(session.id)
        try:
            if screen:
                if name == 'menu_close' or key in ('escape', 'b', 'B'):
                    if screen.confirmation:
                        screen.confirmation = None
                    else:
                        self.close(session)
                elif name == 'menu_cursor' and type(args.get('delta')) is int and not screen.confirmation:
                    screen.cursor = max(0, screen.cursor+args['delta'])
                elif name == 'menu_select' or key:
                    if name == 'menu_select':
                        if frame.data.get('expected_revision') != session.view_revision:
                            return True
                        request = frame.data.get('request_id', '')
                        if request in self.requests.get(session.id, []):
                            return True
                        self.requests.setdefault(session.id, []).append(request)
                        self.requests[session.id] = self.requests[session.id][-128:]
                    body = self.body(session, screen)
                    action = args.get('key', '') if name == 'menu_select' else key.lower()
                    if action not in {a['key'] for a in body['actions']}:
                        return True
                    row = body['rows'][screen.cursor]['id'] if body['rows'] else ''
                    if name == 'menu_select' and args.get('row') != row:
                        return True
                    if screen.confirmation:
                        self.perform(session, *screen.confirmation)
                        screen.confirmation = None
                    elif action in ('l', 'k'):
                        screen.confirmation = ('leave', '') if action == 'l' else ('kick', row)
                    else:
                        if action == 't':
                            self.close(session)
                            self.chat.prompt(session, 'crew')
                            return True
                        verbs = {'i': 'invite', 'a': 'accept', 'd': 'decline', 'p': 'promote', 'o': 'beacon', 'c': 'beacon', 'm': 'invites', 'r': 'loot', 'f': 'loot'}
                        self.perform(session, verbs[action], 'round_robin' if action == 'r' else 'ffa' if action == 'f' else '' if action in ('c', 'm') else row)
                return True
            if session.pending_prompts or session.id in self.game.screens or session.id in self.sim.maps:
                return False
            if name.startswith('crew.'):
                verb = name[5:]
                target = args.get('target', args.get('mode', args.get('name', '')))
                if not isinstance(target, str):
                    raise ValueError('Choose a crew member.')
                if verb == 'open':
                    self.menus[session.id] = CrewMenu(0, tick)
                else:
                    self.perform(session, verb, target)
                return True
            table = next((m for m in self.sim.keymap.get('keymaps', []) if m['id'] == session.keymap_id), {})
            action = name or next((a for a, keys in table.get('bindings', {}).items() if key in keys), '')
            if action == 'crew' and (session.id not in self.sim.external_views or self.lat.location(session)):
                self.menus[session.id] = CrewMenu(0, tick)
                return True
        except (ValueError, KeyError, TypeError) as exc:
            self.chat.toast(session, str(exc) if isinstance(exc, ValueError) else 'That crew action is no longer available.')
            return True
        return False

    def tick(self, ctx: TickContext) -> None:
        for pid in tuple(self.registry.memberships):
            if pid not in self.game.players or not self.session(pid):
                change = self.registry.remove(pid)
                if change:
                    self.changed(change.before, self.text('left', name=self.name(pid)))
        self.linked_controls = {key: tick for key, tick in self.linked_controls.items()
                               if ctx.tick-tick <= PARTICIPATION_SECONDS*TICK_HZ and self.crew_id(key[0])}
        self.silt_entries = {entrance: [e for e in entries if ctx.tick < e[2]]
                             for entrance, entries in self.silt_entries.items()
                             if any(ctx.tick < e[2] for e in entries)}
        current_pairs = set()
        for crew in self.registry.crews.values():
            for source in crew.members:
                for target in crew.members:
                    if source == target:
                        continue
                    pair = source, target
                    if self.nearby(source, target):
                        start, last = self.guards.get(pair, (ctx.tick, ctx.tick))
                        self.guards[pair] = start, ctx.tick
                        if ctx.tick-start >= GUARD_SECONDS*TICK_HZ:
                            self.guarded_at[pair] = ctx.tick
                        current_pairs.add(pair)
        self.guards = {pair: times for pair, times in self.guards.items() if pair in current_pairs}
        self.guarded_at = {pair: tick for pair, tick in self.guarded_at.items()
                           if ctx.tick-tick <= PARTICIPATION_SECONDS*TICK_HZ and self.registry.together(*pair)}
        for invitation in self.registry.expire(ctx.tick):
            self.log(invitation.target, self.text('expired'))
        for sid, screen in tuple(self.menus.items()):
            session = self.game.sessions.active.get(sid)
            if not session or not self.chat.ready(session):
                self.menus.pop(sid, None)
                self.sim.external_views.pop(sid, None)
                continue
            if ctx.tick-screen.opened >= MENU_TIMEOUT_SECONDS*TICK_HZ:
                self.close(session)
            else:
                self.sim.external_views[sid] = 'menu', self.body(session, screen)
        for session in ctx.sessions:
            if self.crew_id(session.player_id):
                self.sim.published.pop(session.id, None)
            overlay = self.sim.external_views.get(session.id)
            if overlay and overlay[0] == 'lattice':
                self.decorate(session, overlay[1])
