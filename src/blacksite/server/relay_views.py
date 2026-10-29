"""Server-owned territory cards and explicit hold/support actions."""

from dataclasses import dataclass
from typing import Any

from blacksite.server.clock import TICK_HZ
from blacksite.server.commerce import CommerceMenu
from blacksite.server.protocol import Frame
from blacksite.server.sessions import Session
from blacksite.server.wake import menu
from blacksite.server.world.simulation import MENU_TIMEOUT_SECONDS


@dataclass
class Panel:
    relay: str = ''
    cursor: int = 0
    opened: int = 0
    route: str = ''


class Views:
    def __init__(self, owner: Any) -> None:
        self.owner = owner
        self.menus: dict[str, Panel] = {}
        self.requests: dict[str, list[str]] = {}
        self.statuses: dict[str, str] = {}
        previous = owner.sim.crew_view
        def decorate(session: Session, body: dict[str, Any]) -> None:
            previous(session, body)
            self.decorate(session, body)
        owner.sim.crew_view = decorate

    def close(self, session: Session) -> None:
        if session.id in self.menus:
            self.menus.pop(session.id)
            self.owner.sim.external_views.pop(session.id, None)

    def terminal(self, session: Session) -> bool:
        actor = self.owner.world.actors.get(session.player_id)
        zone = self.owner.world.zones.get(actor.zone) if actor else None
        return bool(zone and any(obj.spec.kind in ('terminal', 'relay')
            and max(abs(actor.x-obj.spec.tile[0]), abs(actor.y-obj.spec.tile[1])) <= 1
            for obj in zone.objects.values()))

    def status(self, rid: str) -> str:
        relay = self.owner.content.relays[rid]
        claims = [c for c in self.owner.claims.active.values() if c.relay == rid and c.absent_since is None]
        if self.owner.curfew(relay.zone):
            return 'Curfew: clocks paused'
        if len({c.faction for c in claims}) > 1:
            return 'Relay contested: clocks paused'
        return 'Claim active' if claims else 'No active claim'

    def body(self, session: Session, panel: Panel) -> dict[str, Any]:
        owner = self.owner
        if panel.route:
            return owner.passages.body(session, panel.route)
        player = owner.game.players[session.player_id]
        if not panel.relay:
            rows = []
            for rid, relay in owner.content.relays.items():
                if owner.active(rid):
                    faction = owner.owner(rid)
                    captured = owner.ledger.state['relays'].get(rid, {}).get('captured_at', owner.now())
                    held = f'{max(0, int(owner.now()-captured))//60}m held' if faction else '-'
                    rows.append({'id': rid, 'cells': [relay.name,
                        owner.content.factions[faction].short if faction else 'Neutral', held, self.status(rid)]})
            influence = owner.ledger.state['factions'].get(player.faction, {}).get('influence', 0)
            supporting = next((c for c in owner.claims.active.values() if player.id in c.supporters), None)
            role = ('\nYour runner claim: '+owner.content.relays[supporting.relay].name+
                    '. Inspect it to withdraw.') if supporting else ''
            return menu('RELAYS', rows, min(panel.cursor, max(0, len(rows)-1)),
                f'Your faction influence: {influence}. Enter inspects. Holds require the actual terminal.'+role,
                'Enter inspect  Esc/B returns')
        relay = owner.content.relays[panel.relay]
        faction = owner.owner(relay.id)
        name = owner.content.factions[faction].short if faction else 'Neutral'
        rows = [{'id': 'status', 'cells': [name, self.status(relay.id)]}]
        for claim in owner.claims.active.values():
            if claim.relay != relay.id:
                continue
            holder = owner.game.players.get(claim.holder.player)
            defending = faction == claim.faction
            rows.append({'id': 'claim:'+claim.id, 'cells': [holder.name if holder else 'Absent holder',
                owner.content.factions[claim.faction].short,
                f'{claim.elapsed//TICK_HZ}s active' if defending else f'{claim.elapsed//TICK_HZ}/{claim.required//TICK_HZ}s',
                'Defending' if defending else 'Core open' if claim.hacked else 'Core opening needed for 3 min']})
        holding = ('H starts active physical defence. You keep earning active hold XP.\n'
            if player.faction and player.faction == faction else
            'H starts an explicit physical hold. 3 min with a named runner; 8 min alone.\n')
        detail = (f'{relay.name} | {name} | {relay.rate} influence/hour\n'
            +holding+
            'S supports the selected named claim. Open relay_open in its core.\n'
            'Only verified participants receive capture credit; joining a crew gives none.\n'
            'Opposing active claims and Curfew pause clocks. More than 5s away ends a hold.')
        telemetry = owner.benefits.telemetry(player, relay.id)
        if telemetry:
            detail += '\n'+'\n'.join(telemetry)
        body = menu(relay.name, rows, min(panel.cursor, len(rows)-1), detail,
            'H hold  S support selected claim  V member counter  X withdraw  Esc/B closes')
        body['kind'] = 'relays'
        body['actions'] = [{'key':'h','label':'hold'}, {'key':'s','label':'support claim'},
            {'key':'v','label':'member counter'}, {'key':'x','label':'withdraw'}]
        return body

    def act(self, session: Session, panel: Panel, key: str, row: str) -> None:
        owner = self.owner
        if panel.route:
            if owner.passages.choose(session, panel.route, row, key):
                self.close(session)
            return
        if not panel.relay:
            if key == 'enter' and owner.active(row):
                panel.relay, panel.cursor = row, 0
            return
        if key == 'h':
            owner.start(session, panel.relay)
            self.close(session)
        elif key == 's' and row.startswith('claim:'):
            owner.support(session, row.removeprefix('claim:'))
            self.close(session)
        elif key == 'x':
            owner.withdraw(session.player_id, panel.relay)
            owner.log(session.player_id, 'You withdraw from your relay claim or runner support.')
            self.close(session)
        elif key == 'v':
            relay = owner.content.relays[panel.relay]
            owner.commerce.vendor(session, relay.terminal)
            self.close(session)
            owner.commerce.menus[session.id] = CommerceMenu('vendor', relay.terminal, opened=owner.clock.now_tick())

    def input(self, session: Session, frame: Frame, tick: int) -> bool:
        owner = self.owner
        if session.player_id not in owner.game.players:
            return False
        name = frame.data.get('name', '') if frame.type == 'intent' else ''
        args = frame.data.get('args', {})
        key = frame.data.get('k', '') if frame.type == 'key' else ''
        panel = self.menus.get(session.id)
        try:
            if panel:
                if name == 'menu_close' or key.lower() in ('escape', 'b'):
                    self.close(session)
                elif name == 'menu_cursor' and type(args.get('delta')) is int:
                    count = len(self.body(session, panel)['rows'])
                    panel.cursor = max(0, min(panel.cursor+args['delta'], max(0, count-1)))
                elif name == 'menu_select':
                    request = frame.data.get('request_id', '')
                    if (not request or request in self.requests.get(session.id, [])
                            or frame.data.get('expected_revision') != session.view_revision):
                        return True
                    rows = self.body(session, panel)['rows']
                    row = rows[panel.cursor]['id'] if rows else ''
                    if args.get('row') != row:
                        return True
                    self.requests.setdefault(session.id, []).append(request)
                    self.requests[session.id] = self.requests[session.id][-128:]
                    self.act(session, panel, str(args.get('key', 'enter')).lower(), row)
                return True
            actor = owner.world.actors.get(session.player_id)
            holding = bool(actor and actor.behaviour.get('channel', {}).get('owner') == 'relay')
            if holding and (name == 'menu_close' or key.lower() in ('b', 'escape')):
                owner.cancel_hold(session.player_id)
                owner.log(session.player_id, 'You leave the relay terminal.')
                return True
            if (session.pending_prompts or session.id in owner.sim.external_views
                    or session.id in owner.game.screens or session.id in owner.sim.maps):
                return False
            if name in ('relays.open', 'relays') or key == 'f8':
                if self.terminal(session) and (holding or owner.commerce.ready(session)):
                    self.menus[session.id] = Panel(opened=tick)
                    return True
                if name == 'relays.open':
                    raise ValueError('Use a public terminal to inspect territory.')
                return False
            if (name == 'interact' or key.lower() == 'e') and (holding or owner.commerce.ready(session)):
                rid = next((rid for rid in owner.content.relays if owner.active(rid) and owner.near(session.player_id, rid)), None)
                if rid:
                    self.menus[session.id] = Panel(rid, opened=tick)
                    return True
        except (ValueError, KeyError, TypeError) as exc:
            owner.log(session.player_id, str(exc) if isinstance(exc, ValueError) else 'Read the current relay card.')
            return True
        return False

    def decorate(self, session: Session, body: dict[str, Any]) -> None:
        owner = self.owner
        actor = owner.world.actors.get(session.player_id)
        if not actor:
            return
        player = owner.game.players[session.player_id]
        routes = owner.benefits.patrols(player)
        if routes:
            viewport = body['viewport']
            visible = lambda x, y: (0 <= x-viewport['x'] < viewport['w']
                and 0 <= y-viewport['y'] < viewport['h']
                and body['tiles'][y-viewport['y']][x-viewport['x']] != -1)
            body['patrol_routes'] = [{'name': route['name'], 'waypoints': [
                {'x': x, 'y': y} for x, y in route['waypoints'] if visible(x, y)]} for route in routes]
            body['hint'] = body.get('hint', '')+'  + patrol waypoints (live street)'
        for obj in body.get('objects', []):
            rid = next((rid for rid, relay in owner.content.relays.items()
                        if relay.zone == actor.zone and relay.terminal == obj.get('id') and owner.active(rid)), None)
            if rid:
                faction = owner.owner(rid)
                obj['role'] = owner.content.factions[faction].colour if faction in owner.content.factions else 'relay'
                obj['relay'] = {'faction': owner.owner(rid), 'state': self.status(rid),
                    'progress': [{'faction': c.faction, 'seconds': c.elapsed/TICK_HZ, 'needs_hack': not bool(c.hacked)}
                                 for c in owner.claims.active.values() if c.relay == rid]}
        claim = next((c for c in owner.claims.active.values() if c.holder.player == session.player_id), None)
        if claim:
            body['hint'] = (f'Defending | Active hold {claim.elapsed//TICK_HZ}s | B withdraws'
                if owner.owner(claim.relay) == claim.faction else
                f'{self.status(claim.relay)} | Hold {claim.elapsed/TICK_HZ:.1f}/{claim.required/TICK_HZ:g}s | B withdraws')
        elif self.terminal(session):
            body['hint'] = body.get('hint', '')+'  F8 relays'

    def tick(self, tick: int) -> None:
        owner = self.owner
        for sid, panel in tuple(self.menus.items()):
            session = owner.game.sessions.active.get(sid)
            if (not session or session.closed or session.player_id not in owner.game.players
                    or not (self.terminal(session) or panel.route and owner.passages.near(session, panel.route))):
                if session:
                    self.close(session)
                else:
                    self.menus.pop(sid)
                    owner.sim.external_views.pop(sid, None)
                continue
            actor = owner.world.actors[session.player_id]
            if (tick-panel.opened >= MENU_TIMEOUT_SECONDS*TICK_HZ
                    and owner.world.zones[actor.zone].allows_hostile(actor.position)):
                self.close(session)
                owner.log(session.player_id, 'Your relay card closes. The street stays active.')
                continue
            owner.sim.external_views[sid] = 'menu', self.body(session, panel)
        for rid, relay in owner.content.relays.items():
            if not owner.active(rid):
                continue
            status = self.status(rid)
            if rid in self.statuses and status != self.statuses[rid]:
                for session in owner.game.sessions.active.values():
                    actor = owner.world.actors.get(session.player_id)
                    if actor and actor.zone == relay.zone and not session.closed:
                        owner.log(session.player_id, relay.name+': '+status+'.')
            self.statuses[rid] = status
        self.requests = {sid: values for sid, values in self.requests.items() if sid in owner.game.sessions.active}
