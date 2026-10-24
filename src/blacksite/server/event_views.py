"""Authoritative forecast menus and public event summaries, game 12."""

from dataclasses import dataclass
from copy import deepcopy
from math import ceil
from typing import Any

from blacksite.server.clock import TICK_HZ
from blacksite.server.events import Plan
from blacksite.server.event_forecasts import remember
from blacksite.server.factions import perk
from blacksite.server.items import ItemInstance
from blacksite.server.loop import TickContext
from blacksite.server.protocol import Frame
from blacksite.server.sessions import Session
from blacksite.server.wake import menu

PAGE_ROWS = 12  # Same bounded menu pages as S23 / architecture 5.4.


@dataclass
class Panel:
    opened: int
    chart: bool = False
    cursor: int = 0
    selected: str = ''
    held: bool = False


class Views:
    def __init__(self, owner: Any) -> None:
        self.owner = owner
        self.menus: dict[str, Panel] = {}

    def chart(self, pid: str) -> bool:
        player = self.owner.game.players[pid]
        return any(iid in self.owner.commerce.items
            and self.owner.commerce.items[iid].owner == pid
            and self.owner.commerce.items[iid].template == 'key_ringfall_chart'
            for iid in player.inventory)

    def access(self, session: Session, panel: Panel) -> None:
        if panel.chart:
            if not self.owner.commerce.ready(session) or not self.chart(session.player_id):
                raise ValueError('Keep the chart with your body to read it.')
        else:
            self.owner.core.market.terminal(session)

    def open(self, session: Session, *, chart: bool = False) -> None:
        panel = Panel(self.owner.clock.now_tick(), chart)
        self.access(session, panel)
        self.menus[session.id] = panel
        if chart:
            plans = [plan for plan in self.owner.scheduler.reserved() if plan.template == 'ring-fall']
            if plans:
                self.read(session, panel, min(plans, key=lambda plan: plan.starts_at))
            else:
                self.owner.commerce.toast(session, 'No committed Ring-fall is announced. Your chart remains.')

    def close(self, session: Session) -> None:
        self.menus.pop(session.id, None)
        self.owner.sim.external_views.pop(session.id, None)
        if avatar := self.owner.sim.avatars.get(session.user_id):
            self.owner.sim.reset_view(session, avatar)

    def plans(self, session: Session, panel: Panel) -> list[Plan]:
        saved = self.owner.game.players[session.player_id].progress.get('event_forecasts', {})
        if panel.held:
            plans = [self.owner.scheduler.plans[pid] for pid in saved if pid in self.owner.scheduler.plans]
        else:
            plans = list(self.owner.scheduler.reserved())
            present = {plan.id for plan in plans}
            plans += [self.owner.scheduler.plans[pid] for pid in saved
                      if pid not in present and pid in self.owner.scheduler.plans]
        return sorted(plans, key=lambda plan: (plan.starts_at, plan.id))

    def detailed(self, session: Session, plan: Plan) -> bool:
        owner = self.owner
        player = owner.game.players[session.player_id]
        if plan.template == 'ring-fall':
            return self.chart(player.id) or perk(player, 'ferrymen') or owner.now() >= plan.starts_at-5
        if plan.template == 'choir-surge':
            return perk(player, 'choir') or any(
                owner.commerce.items.get(iid) and owner.commerce.items[iid].template == 'imp_res_tenant_ear'
                for iid in player.implants.values()) or plan.state != 'planned'
        return True

    def read(self, session: Session, panel: Panel, plan: Plan) -> None:
        self.access(session, panel)
        owner = self.owner
        text = owner.text(plan, detailed=self.detailed(session, plan))
        record = {'revision': plan.revision, 'text': text}
        if not plan.live:
            record['final'] = owner.forecast_outcome(plan)
        self.save(session, panel, plan.id, record)

    def save(self, session: Session, panel: Panel, pid: str, record: dict[str, Any]) -> None:
        owner, player = self.owner, self.owner.game.players[session.player_id]
        progress = deepcopy(player.progress)
        known = progress.setdefault('event_forecasts', {})
        previous = {key: value for key, value in known.get(pid, {}).items() if key != 'read_at'}
        if previous == record:
            panel.selected = pid
            return
        remember(progress, pid, record, owner.now())
        def committed(success: bool) -> None:
            if success and self.menus.get(session.id) is panel:
                panel.selected = pid
            elif not success:
                owner.commerce.toast(session, 'The forecast could not be saved. Read it again.')
        if not owner.commerce.settle(player, {'progress': progress}, owner.commerce.items,
                owner.commerce.caches, owner.commerce.serial, committed):
            raise ValueError('The city is busy. Read the forecast again.')

    def use(self, session: Session, item: ItemInstance) -> bool:
        if item.template != 'key_ringfall_chart':
            return False
        self.owner.commerce.close(session)
        self.open(session, chart=True)
        return True

    def body(self, session: Session, panel: Panel) -> dict[str, Any]:
        if panel.held:
            return self.held_body(session, panel)
        owner = self.owner
        plans = self.plans(session, panel)
        panel.cursor = min(panel.cursor, max(0, len(plans)-1))
        start = panel.cursor//PAGE_ROWS*PAGE_ROWS
        selected = owner.scheduler.plans.get(panel.selected) if panel.selected else (
            plans[panel.cursor] if plans else None)
        detail = (owner.text(selected, detailed=self.detailed(session, selected)) if selected else
            'No committed event is announced. Ordinary work remains open.')
        notice = owner.game.players[session.player_id].progress.get('convoy_notice')
        if notice:
            detail += '\nYour reservation: '+notice
        if selected:
            saved = owner.game.players[session.player_id].progress.get('event_forecasts', {}).get(selected.id)
            if saved and saved['revision'] != selected.revision:
                detail = 'Your forecast changes.\n'+detail
            if selected.template == 'ring-fall' and not self.detailed(session, selected):
                detail += '\nKin reads the ring free. A carried chart also names it. Impact warnings remain public.'
            if selected.allocations.get('route') and selected.state == 'active':
                route = owner.content.routes.get(selected.allocations['route'])
                if route:
                    detail += '\nRoute: '+' -> '.join(owner.place(point.zone) for point in route.waypoints)
        rows = [{'id': plan.id, 'cells': [owner.content.events[plan.template].name
                    if plan.template in owner.content.events else plan.template,
                    plan.state, owner.time(plan.starts_at)]} for plan in plans[start:start+PAGE_ROWS]]
        if panel.selected and selected:
            rows = [{'id': selected.id, 'cells': [owner.content.events[selected.template].name
                if selected.template in owner.content.events else selected.template, selected.state]}]
        body = menu('YOUR FORECASTS' if panel.held else 'CITY FORECASTS',
            rows or [{'id': '', 'cells': ['No announced plans.']}],
            0 if panel.selected else panel.cursor-start, detail,
            'R read  H held forecasts  Esc/B returns')
        body['actions'] = [{'key': 'r', 'label': 'read'}, {'key': 'h', 'label': 'held forecasts'}]
        body['columns'] = ['Event', 'State', 'Starts UTC']
        body['page'], body['pages'] = start//PAGE_ROWS+1, max(1, (len(plans)+PAGE_ROWS-1)//PAGE_ROWS)
        return body

    def held_ids(self, session: Session) -> list[str]:
        known = self.owner.game.players[session.player_id].progress.get('event_forecasts', {})
        return sorted(known, key=lambda pid: (known[pid].get('read_at', 0), pid), reverse=True)

    def ids(self, session: Session, panel: Panel) -> list[str]:
        return self.held_ids(session) if panel.held else [plan.id for plan in self.plans(session, panel)]

    def held_body(self, session: Session, panel: Panel) -> dict[str, Any]:
        owner = self.owner
        known = owner.game.players[session.player_id].progress.get('event_forecasts', {})
        ids = self.held_ids(session)
        panel.cursor = min(panel.cursor, max(0, len(ids)-1))
        start = panel.cursor//PAGE_ROWS*PAGE_ROWS
        pid = panel.selected if panel.selected in known else (ids[panel.cursor] if ids else '')
        def fields(pid: str) -> tuple[str, str, float | None]:
            current = owner.scheduler.plans.get(pid)
            final = known[pid].get('final', {})
            name = owner.content.events[current.template].name if current and current.template in owner.content.events else (
                final.get('name') or known[pid]['text'].partition(':')[0])
            return name, current.state if current else final.get('state', 'closed'), (
                current.starts_at if current else final.get('starts_at'))
        detail = 'No forecast is saved. Read an announced plan first.'
        if pid:
            saved = known[pid]
            current = owner.scheduler.plans.get(pid)
            final = saved.get('final', {})
            detail = owner.text(current, detailed=self.detailed(session, current)) if current else (
                final.get('text') or saved['text']+'\nThis older outcome is no longer in city history.')
            revision = current.revision if current else final.get('revision', saved['revision'])
            if revision != saved['revision']:
                detail = 'Your forecast changes.\n'+detail
        shown = [pid] if panel.selected and pid else ids[start:start+PAGE_ROWS]
        rows = []
        for entry in shown:
            name, state, starts = fields(entry)
            rows.append({'id': entry, 'cells': [name, state, owner.time(starts) if starts is not None else '']})
        body = menu('YOUR RECENT FORECASTS', rows or [{'id': '', 'cells': ['No saved plans.']}],
            0 if panel.selected else panel.cursor-start, detail, 'R read  H city forecasts  Esc/B returns')
        body['actions'] = [{'key': 'r', 'label': 'read'}, {'key': 'h', 'label': 'city forecasts'}]
        body['columns'] = ['Event', 'State', 'Starts UTC']
        body['page'], body['pages'] = start//PAGE_ROWS+1, max(1, (len(ids)+PAGE_ROWS-1)//PAGE_ROWS)
        return body

    def input(self, session: Session, frame: Frame, tick: int) -> bool:
        name = frame.data.get('name') if frame.type == 'intent' else ''
        key = str(frame.data.get('k', '')).lower() if frame.type == 'key' else ''
        if name == 'event.open':
            try:
                self.open(session)
            except ValueError as exc:
                self.owner.commerce.toast(session, str(exc))
            return True
        panel = self.menus.get(session.id)
        if panel is None:
            return False
        try:
            if name == 'menu_close' or key in ('escape', 'b'):
                if panel.selected:
                    panel.selected = ''
                else:
                    self.close(session)
                return True
            self.access(session, panel)
            args = frame.data.get('args', {})
            if name == 'menu_cursor' and not panel.selected:
                delta = args.get('delta', 0)
                if type(delta) is int:
                    panel.cursor = max(0, min(panel.cursor+delta, len(self.ids(session, panel))-1))
            elif name == 'menu_select' or key:
                if name == 'menu_select' and frame.data.get('expected_revision') != session.view_revision:
                    return True
                action = str(args.get('key', 'enter')).lower() if name == 'menu_select' else key
                if action == 'h':
                    panel.held, panel.cursor, panel.selected = not panel.held, 0, ''
                elif action in ('r', 'enter'):
                    ids = self.ids(session, panel)
                    pid = panel.selected or (ids[min(panel.cursor, len(ids)-1)] if ids else '')
                    if pid and (name != 'menu_select' or args.get('row') == pid):
                        if plan := self.owner.scheduler.plans.get(pid):
                            self.read(session, panel, plan)
                        elif panel.held:
                            saved = self.owner.game.players[session.player_id].progress['event_forecasts'][pid]
                            record = {key: value for key, value in saved.items() if key != 'read_at'}
                            if final := record.get('final'):
                                record.update(revision=final['revision'], text=final['text'])
                            self.save(session, panel, pid, record)
        except (ValueError, KeyError) as exc:
            self.owner.commerce.toast(session, str(exc))
        return True

    def decorate(self, session: Session, body: dict[str, Any]) -> None:
        owner = self.owner
        plans = [plan for plan in owner.scheduler.reserved()
                 if plan.ends_at > owner.now() and (plan.state == 'active' or 'warning' in plan.milestones)]
        summaries = []
        for plan in plans:
            warning = max(0, owner.warning_until.get(plan.id, 0)-owner.clock.now_tick())/TICK_HZ
            remaining = max(0, plan.ends_at-owner.now())
            name = owner.content.events[plan.template].name
            summary = f'{name} !{ceil(warning)}s' if warning else f'{name} {ceil(remaining/60)}m'
            summaries.append({'id': plan.id, 'revision': plan.revision, 'state': plan.state,
                'warning': warning, 'remaining': remaining, 'summary': summary,
                'scope': [owner.place(place) for place in plan.where]})
        body['event'] = {'plans': summaries} if summaries else None

    def tick(self, ctx: TickContext) -> None:
        for sid, panel in tuple(self.menus.items()):
            session = self.owner.core.sessions.active.get(sid)
            if session is None or session.closed:
                self.menus.pop(sid, None)
                self.owner.sim.external_views.pop(sid, None)
                continue
            try:
                self.access(session, panel)
            except ValueError:
                self.close(session)
                continue
            self.owner.sim.external_views[sid] = 'menu', self.body(session, panel)
