"""Server-owned terminal, market and anonymous bounty menus."""

from dataclasses import dataclass, field
from typing import Any

from blacksite.server.clock import TICK_HZ
from blacksite.server.loop import TickContext
from blacksite.server.items import ItemInstance
from blacksite.server.protocol import Frame
from blacksite.server.quality import detail
from blacksite.server.rules.market import BOUNTY_MIN_TARGET_GRADE, LISTING_EXPIRIES, MARKET_ACTION_SECONDS
from blacksite.server.sessions import MARKET_PER_SECOND, Session
from blacksite.server.wake import menu
from blacksite.server.world.simulation import MENU_TIMEOUT_SECONDS


# Terminal UI 4: bound each view while retaining the full market history.
MENU_PAGE_ROWS = 12


@dataclass
class Panel:
    kind: str
    terminal: str
    opened: int
    cursor: int = 0
    mine: bool = False
    class_: str = 'all'
    sort: str = 'price'
    selected: str = ''
    form: dict[str, Any] = field(default_factory=dict)
    confirmation: tuple[str, dict[str, Any], str] | None = None


class Views:
    def __init__(self, owner: Any) -> None:
        self.owner = owner
        self.menus: dict[str, Panel] = {}
        self.prompts: dict[str, tuple[str, str]] = {}
        self.requests: dict[str, list[str]] = {}
        self.serial = 0
        previous = owner.sim.crew_view
        def decorate(session: Session, body: dict[str, Any]) -> None:
            previous(session, body)
            try:
                owner.terminal(session)
            except ValueError:
                return
            body['hint'] = body.get('hint', '')+'  F9 services'
        owner.sim.crew_view = decorate

    def close(self, session: Session) -> None:
        self.menus.pop(session.id, None)
        self.prompts.pop(session.id, None)
        session.pending_prompts.pop('market', None)
        self.owner.sim.external_views.pop(session.id, None)

    def label(self, pid: str) -> str:
        player = self.owner.game.players.get(pid)
        return f'{player.name} / {player.bbs_handle}' if player else 'Retired character'

    def item_detail(self, iid: str) -> str:
        return self.item_text(self.owner.commerce.items[iid])

    def item_text(self, item: ItemInstance) -> str:
        template = self.owner.commerce.content.items[item.template]
        condition = f'Qty {item.stack}'
        if template.weapon and template.weapon.ammo:
            condition += f'  Loaded {item.ammo}'
        if template.consumable:
            condition += f'  Charges {item.charges}'
        if item.health is not None:
            condition += f'  Drone health {item.health}'
        return f'{template.name}\n{detail(template,item.quality)}\n{condition}'

    def listing_item(self, listing: Any) -> ItemInstance:
        return (ItemInstance.from_record(listing.item_snapshot) if listing.item_snapshot
                else self.owner.commerce.items[listing.item])

    def rows(self, session: Session, panel: Panel) -> list[dict[str, Any]]:
        owner, pid = self.owner, session.player_id
        player = owner.game.players[pid]
        if panel.kind == 'terminal':
            return [{'id': 'market', 'cells': ['Market', 'Listings, bids and delivery']},
                    {'id': 'bounties', 'cells': ['Bounties', 'Prices on local names']},
                    {'id': 'jack', 'cells': ['Jack in', 'Your body stays here']},
                    {'id': 'collect', 'cells': ['Collect', 'Your protected market deliveries']}]
        if panel.kind == 'expiry':
            return [{'id': str(seconds), 'cells': [label]} for seconds, label in zip(
                LISTING_EXPIRIES, ('24 hours', '72 hours', 'Seven days'))]
        if panel.kind == 'items':
            return [{'id': iid, 'cells': [owner.commerce.content.items[owner.commerce.items[iid].template].name,
                    f'{owner.commerce.items[iid].quality:.0%}']} for iid in player.inventory
                    if owner.listable(player, owner.commerce.items[iid])]
        if panel.kind == 'collect':
            entries = owner.lat.interlock.state.get('impounds', {}).get(pid, {}).get('items', {})
            return [{'id': iid, 'cells': [owner.commerce.content.items[owner.commerce.items[iid].template].name,
                    'No fee']} for iid, entry in entries.items() if entry.get('source') == 'market']
        if panel.kind == 'targets':
            return [{'id': p.id, 'cells': [p.name, p.bbs_handle, f'Grade {p.grade}']}
                    for p in sorted(owner.game.players.values(), key=lambda p: (p.name, p.id))
                    if p.origin == player.origin and p.id not in owner.game.deleting]
        if panel.kind == 'bounties':
            targets: dict[str, list[Any]] = {}
            for row in owner.bounties.rows.values():
                if row.status == 'active' and row.expires_at > owner.now():
                    targets.setdefault(row.target, []).append(row)
            return [{'id': target, 'cells': [self.label(target), str(sum(r.chits for r in rows)),
                    f'{len({r.poster for r in rows})} posters']} for target, rows in sorted(targets.items())]
        listings = [v for v in owner.market.listings.values()
                    if (v.seller == pid if panel.mine else v.status == 'open' and v.expires_at > owner.now())]
        if panel.class_ != 'all':
            listings = [v for v in listings if owner.commerce.content.items[self.listing_item(v).template].class_ == panel.class_]
        listings.sort(key=lambda v: ((v.expires_at if panel.sort == 'expiry' else
            owner.market.highest(v.id).amount if owner.market.highest(v.id) else v.ask), v.id))
        return [{'id': v.id, 'cells': [owner.commerce.content.items[self.listing_item(v).template].name,
                str(owner.market.highest(v.id).amount if owner.market.highest(v.id) else v.price or v.ask),
                f'{max(0,int(v.expires_at-owner.now()))}s' if v.status == 'open' else v.status,
                self.label(v.seller)]} for v in listings]

    def body(self, session: Session, panel: Panel) -> dict[str, Any]:
        rows = self.rows(session, panel)
        cursor = min(panel.cursor, max(0, len(rows)-1))
        row = rows[cursor]['id'] if rows else ''
        text = 'Market money uses your bank. Esc/B returns. The street stays active.'
        help_asset = self.owner.commerce.content.text.get('text-market-help')
        if help_asset:
            text = help_asset.body.strip()
        actions = 'Esc/B  D bid  U buy  L list  M mine  C collect  K cancel  F class  S sort'
        if panel.kind == 'market' and row:
            listing = self.owner.market.listings[row]
            item = self.listing_item(listing)
            highest = self.owner.market.highest(listing.id)
            text = self.item_text(item)+f'\nSeller {self.label(listing.seller)}\nAsk {listing.ask}; buyout {listing.buyout or "none"}; highest {highest.amount if highest else "none"}.\nStatus {listing.status}; sale price {listing.price}.'
        elif panel.kind in ('items', 'collect') and row:
            text = self.item_detail(row)
            actions = 'Enter choose  Esc/B returns'
        elif panel.kind == 'bounties':
            text = 'Posters are anonymous. Normal combat, Marked and recovery rules still apply.'
            actions = 'P post  Esc/B returns'
        elif panel.kind == 'targets':
            text, actions = 'Choose a local character. Targets require grade 5.', 'Enter choose  Esc/B returns'
        elif panel.kind == 'expiry':
            text, actions = 'Choose the listing duration.', 'Enter choose  Esc/B returns'
        elif panel.kind == 'terminal':
            text, actions = 'Public services. Jacking leaves your body here.', 'M market  O bounties  J jack  C collect  Enter choose  Esc/B'
        if panel.confirmation:
            text = panel.confirmation[2]+'\nY confirms. Esc/B returns without a transfer.'
            actions = 'Y confirm  Esc/B returns'
        start = cursor//MENU_PAGE_ROWS*MENU_PAGE_ROWS
        body = menu('MY LISTINGS' if panel.mine and panel.kind == 'market' else panel.kind.upper(),
                    rows[start:start+MENU_PAGE_ROWS] or [{'id': '', 'cells': ['No entries.']}],
                    cursor-start, text, actions)
        body['page'] = start//MENU_PAGE_ROWS+1
        body['pages'] = max(1, (len(rows)+MENU_PAGE_ROWS-1)//MENU_PAGE_ROWS)
        keys = {'terminal': [('m', 'market'), ('o', 'bounties'), ('j', 'jack'), ('c', 'collect')],
            'market': [('d', 'bid'), ('u', 'buyout'), ('l', 'list'), ('m', 'my listings'),
                       ('c', 'collect'), ('k', 'cancel'), ('f', 'class'), ('s', 'sort')],
            'bounties': [('p', 'post')], 'items': [('enter', 'choose')],
            'collect': [('enter', 'collect')], 'targets': [('enter', 'choose')],
            'expiry': [('enter', 'choose')]}[panel.kind]
        body['actions'] = [{'key': k, 'label': label} for k, label in
                           ([('y', 'confirm')] if panel.confirmation else keys)]
        body['columns'] = {'market': ['Item', 'Bid/ask', 'Time', 'Seller'],
            'bounties': ['Name / handle', 'Chits', 'Posters'], 'targets': ['Name', 'Handle', 'Grade'],
            'items': ['Item', 'Quality'], 'collect': ['Item', 'Collection'],
            'terminal': ['Service', 'Use'], 'expiry': ['Duration']}[panel.kind]
        body['clear_prompt'] = session.id not in self.prompts
        return body

    def prompt(self, session: Session, field: str, label: str) -> None:
        self.serial += 1
        token = f'market:{session.id}:{self.serial}'
        self.prompts[session.id] = token, field
        session.pending_prompts['market'] = token
        session.send(Frame('prompt', {'id': token, 'kind': 'line', 'label': label, 'max_len': 12}))

    def line(self, session: Session, panel: Panel, text: str, field: str) -> None:
        amount = None if field == 'buyout' and not text.strip() else int(text)
        if field in ('price', 'buyout'):
            panel.form[field] = amount
            if field == 'price':
                self.prompt(session, 'buyout', 'Buyout chits; blank means none')
            else:
                panel.kind, panel.cursor = 'expiry', 0
        elif field == 'bid':
            panel.confirmation = 'bid', {'listing': panel.selected, 'chits': amount}, f'Hold {amount} banked chits for this bid?'
        else:
            panel.confirmation = 'post', {'target': panel.selected, 'chits': amount}, f'Post {amount} banked chits on {self.label(panel.selected)}?'

    def submit(self, session: Session, action: str, args: dict[str, Any], tick: int) -> None:
        if not session.allow('market', tick, MARKET_PER_SECOND, MARKET_ACTION_SECONDS):
            raise ValueError('One market or bounty action per second.')
        self.owner.request(session, action, args)

    def act(self, session: Session, panel: Panel, key: str, row: str, tick: int) -> None:
        owner = self.owner
        if panel.confirmation:
            if key == 'y':
                action, args, _ = panel.confirmation
                self.submit(session, action, {**args, 'terminal': panel.terminal}, tick)
                panel.confirmation = None
                panel.kind = 'bounties' if action == 'post' else 'collect' if action == 'collect' else 'market'
            return
        if panel.kind == 'terminal':
            choice = {'m': 'market', 'o': 'bounties', 'j': 'jack', 'c': 'collect'}.get(key, row if key == 'enter' else '')
            if choice == 'jack':
                self.close(session)
                owner.lat.jack_in(session, panel.terminal)
            elif choice in ('market', 'bounties', 'collect'):
                panel.kind, panel.cursor = choice, 0
            return
        if panel.kind == 'expiry' and key == 'enter' and row:
            panel.form['expiry'] = int(row)
            panel.confirmation = 'list', dict(panel.form), f'List this exact item for {panel.form["price"]} chits; buyout {panel.form["buyout"] or "none"}?'
        elif panel.kind == 'items' and key == 'enter' and row:
            panel.form = {'item': row}
            self.prompt(session, 'price', 'Asking chits')
        elif panel.kind == 'collect' and key in ('enter', 'c') and row:
            panel.confirmation = 'collect', {'item': row}, 'Collect this market delivery? No fee.'
        elif panel.kind == 'targets' and key == 'enter' and row:
            if owner.game.players[row].grade < BOUNTY_MIN_TARGET_GRADE:
                raise ValueError('Nobody pays for a Wake.')
            panel.selected = row
            self.prompt(session, 'bounty', 'Bounty chits; minimum 100')
        elif panel.kind == 'bounties' and key == 'p':
            panel.kind, panel.cursor = 'targets', 0
        elif panel.kind == 'market':
            if key == 'l':
                panel.kind, panel.cursor = 'items', 0
            elif key == 'c':
                panel.kind, panel.cursor = 'collect', 0
            elif key == 'm':
                panel.mine, panel.cursor = not panel.mine, 0
            elif key == 's':
                panel.sort = 'expiry' if panel.sort == 'price' else 'price'
            elif key == 'f':
                classes = ['all', *sorted({v.class_ for v in owner.commerce.content.items.values()})]
                panel.class_, panel.cursor = classes[(classes.index(panel.class_)+1)%len(classes)], 0
            elif key == 'd' and row:
                panel.selected = row
                self.prompt(session, 'bid', 'Bid chits')
            elif key in ('u', 'k') and row:
                listing = owner.market.listings[row]
                if key == 'u' and listing.buyout is None:
                    raise ValueError('This listing has no buyout.')
                action = 'buyout' if key == 'u' else 'cancel'
                panel.confirmation = action, {'listing': row}, f'Buyout total {listing.buyout} chits. Your existing bid escrow counts toward it.' if key == 'u' else 'Cancel this unsold listing? Its weight returns to your inventory.'

    def input(self, session: Session, frame: Frame, tick: int) -> bool:
        if session.player_id not in self.owner.game.players:
            return False
        name = frame.data.get('name', '') if frame.type == 'intent' else ''
        key = frame.data.get('k', '').lower() if frame.type == 'key' else ''
        args = frame.data.get('args', {})
        panel = self.menus.get(session.id)
        bank_menu = self.owner.commerce.menus.get(session.id)
        selection_key = str(args.get('key', 'enter')).lower()
        bank_collect = bool(name == 'menu_select' and bank_menu and bank_menu.kind == 'bank'
            and (selection_key == 'c' or selection_key == 'enter' and args.get('row') == 'market_delivery'))
        try:
            if key == 'f9' and not panel:
                if (not self.owner.commerce.ready(session) or session.pending_prompts
                        or session.id in self.owner.sim.external_views or session.id in self.owner.sim.maps):
                    return False
                try:
                    terminal = self.owner.terminal(session)
                except ValueError:
                    return False
                self.menus[session.id] = Panel('terminal', terminal.spec.id, tick)
                return True
            if name in ('market.open', 'bounty.open'):
                terminal = self.owner.terminal(session, args.get('terminal', ''))
                self.menus[session.id] = Panel('market' if name == 'market.open' else 'bounties', terminal.spec.id, tick)
                return True
            actions = {'market.list': 'list', 'market.bid': 'bid', 'market.buyout': 'buyout',
                       'market.cancel': 'cancel', 'market.collect': 'collect', 'bounty.post': 'post'}
            if name in actions or bank_collect or panel and name == 'menu_select':
                request = frame.data.get('request_id', '')
                if (not request or request in self.requests.get(session.id, [])
                        or frame.data.get('expected_revision') != session.view_revision):
                    return True
                self.requests.setdefault(session.id, []).append(request)
                self.requests[session.id] = self.requests[session.id][-128:]
                if bank_collect:
                    rows = self.owner.commerce.body(session, bank_menu)['rows']
                    row = rows[min(bank_menu.cursor, len(rows)-1)]['id'] if rows else ''
                    if args.get('row') != row:
                        return True
                    self.owner.terminal(session, bank_menu.target, bank=True)
                    self.owner.commerce.close(session)
                    self.menus[session.id] = Panel('collect', bank_menu.target, tick)
                    return True
                if name in actions:
                    self.submit(session, actions[name], args, tick)
                    return True
            if not panel:
                return False
            if name in ('menu_close', 'prompt_cancel') or key in ('escape', 'b'):
                self.close(session)
            elif frame.type == 'line':
                prompt = self.prompts.get(session.id)
                if prompt and frame.data['id'] == prompt[0]:
                    self.prompts.pop(session.id)
                    session.pending_prompts.pop('market', None)
                    self.line(session, panel, frame.data['text'], prompt[1])
            elif name == 'menu_cursor' and type(args.get('delta')) is int:
                panel.cursor = max(0, min(panel.cursor+args['delta'], max(0, len(self.rows(session,panel))-1)))
            elif name == 'menu_select':
                rows = self.rows(session, panel)
                row = rows[min(panel.cursor, len(rows)-1)]['id'] if rows else ''
                if args.get('row') == row:
                    self.act(session, panel, str(args.get('key', 'enter')).lower(), row, tick)
            return True
        except (ValueError, KeyError, TypeError) as exc:
            self.owner.commerce.toast(session, str(exc) if isinstance(exc,ValueError) else 'Read the current market screen.')
            return True

    def terminal_input(self, session: Session, frame: Frame, tick: int) -> bool:
        if (session.pending_prompts or session.id in self.owner.sim.external_views
                or session.id in self.owner.game.screens or session.id in self.owner.sim.maps):
            return False
        name = frame.data.get('name', '') if frame.type == 'intent' else ''
        key = frame.data.get('k', '').lower() if frame.type == 'key' else ''
        table = next((m for m in self.owner.sim.keymap.get('keymaps', []) if m['id'] == session.keymap_id), {})
        action = next((a for a, keys in table.get('bindings', {}).items() if frame.data.get('k') in keys), name)
        if key != 'e' and action != 'interact':
            return False
        try:
            terminal = self.owner.terminal(session)
        except ValueError:
            return False
        self.menus[session.id] = Panel('terminal', terminal.spec.id, tick)
        return True

    def tick(self, ctx: TickContext) -> None:
        for sid, panel in tuple(self.menus.items()):
            session = self.owner.game.sessions.active.get(sid)
            if not session or session.closed:
                self.menus.pop(sid)
                self.owner.sim.external_views.pop(sid, None)
                continue
            try:
                self.owner.terminal(session, panel.terminal, bank=panel.kind == 'collect')
                actor = self.owner.sim.avatars[session.user_id].actor
                if (ctx.tick-panel.opened >= MENU_TIMEOUT_SECONDS*TICK_HZ
                        and self.owner.game.world.zones[actor.zone].allows_hostile(actor.position)):
                    raise ValueError('Your market screen closes. The street stays active.')
            except (ValueError, KeyError):
                self.close(session)
                continue
            self.owner.sim.external_views[sid] = 'menu', self.body(session, panel)
        self.requests = {sid: ids for sid, ids in self.requests.items() if sid in self.owner.game.sessions.active}
