"""Game 8.3: atomic world adapter for market and bounty proposals."""

from collections.abc import Callable
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from typing import Any

from blacksite.server.clock import TICK_HZ
from blacksite.server.inventory import Inventory
from blacksite.server.items import ItemInstance
from blacksite.server.loop import TickContext
from blacksite.server.market import Bounties, Listing, Market
from blacksite.server.players import Player
from blacksite.server.protocol import Frame
from blacksite.server.relays import Ledger
from blacksite.server.rules.market import fee
from blacksite.server.rules.character import carry_kg
from blacksite.server.sessions import Session


@dataclass
class Proposal:
    market: Market
    bounties: Bounties
    items: dict[str, ItemInstance]
    interlock: dict[str, Any]
    relays: Ledger
    patches: dict[str, dict[str, Any]] = field(default_factory=dict)
    notes: list[tuple[str, str]] = field(default_factory=list)
    audit: list[dict[str, Any]] = field(default_factory=list)


class Trading:
    def __init__(self, core: Any, state: dict[str, Any]) -> None:
        self.core, self.game, self.commerce = core, core.characters, core.commerce
        self.sim, self.clock, self.lat = self.game.sim, core.clock, core.lattice
        self.game.market = self
        self.market = Market(core.sessions.origin, state.get('market', {}))
        self.bounties = Bounties(core.sessions.origin, state.get('bounties', {}))
        self.last_expiry = -TICK_HZ
        self.game.before_delete = self.prepare_retirement
        from blacksite.server.market_views import Views
        self.views = Views(self)

    def now(self) -> float:
        return self.clock.now_utc().timestamp()

    def draft(self) -> Proposal:
        return Proposal(self.market.fork(), self.bounties.fork(), deepcopy(self.commerce.items),
                        deepcopy(self.lat.interlock.state), self.core.relays.ledger.fork())

    def bank(self, draft: Proposal, pid: str, amount: int) -> None:
        player = self.game.players.get(pid)
        if not player or pid in self.game.deleting:
            raise ValueError('That character is no longer available.')
        patch = draft.patches.setdefault(pid, {})
        balance = patch.get('chits_bank', player.chits_bank) + amount
        if balance < 0:
            raise ValueError('Not enough banked chits.')
        patch['chits_bank'] = balance

    def notify(self, pid: str, text: str) -> None:
        session = self.core.combat.session(pid)
        if session:
            session.emit(text, kind="system", channel="system", role="chan_sys",
                         at=self.clock.now_utc().isoformat())
            self.commerce.toast(session, text)

    def terminal(self, session: Session, target: str = '', bank: bool = False) -> Any:
        if not isinstance(target, str):
            raise ValueError('Choose a terminal by its identifier.')
        if not self.commerce.ready(session):
            raise ValueError('Return to your body before using the market.')
        actor = self.sim.avatars[session.user_id].actor
        terminal = self.lat.terminal(actor, target or None)
        if terminal:
            return terminal
        if bank:
            zone = self.game.world.zones[actor.zone]
            for obj in zone.objects.values():
                if (obj.spec.kind == 'bank' and (not target or target == obj.spec.id)
                        and max(abs(actor.x-obj.spec.tile[0]), abs(actor.y-obj.spec.tile[1])) <= 1
                        and self.game.world.object_access(actor, obj.spec)):
                    return obj
        raise ValueError('Stand beside an accessible terminal'+(' or bank.' if bank else '.'))

    def deliver(self, draft: Proposal, iid: str, pid: str) -> None:
        self.core.apartments.impound(draft.interlock, draft.items, pid, [iid])
        draft.interlock['impounds'][pid]['items'][iid]['source'] = 'market'

    def sale(self, draft: Proposal, listing: Listing) -> None:
        if listing.winner:
            tax = fee(listing.price)
            self.bank(draft, listing.seller, listing.price-tax)
            account = draft.relays.totals('kestrel')
            account['treasury'] += tax
            self.deliver(draft, listing.item, listing.winner)
            draft.notes.extend([(listing.seller, f'Market sale: {listing.price-tax} chits reach your bank; fee {tax}.'),
                                (listing.winner, 'Your market purchase waits in personal impound. Collection is free.')])
        else:
            patch = draft.patches.setdefault(listing.seller, {})
            inventory = list(patch.get('inventory', self.game.players[listing.seller].inventory))
            if listing.item not in inventory:
                inventory.append(listing.item)
            patch['inventory'] = inventory
            draft.items[listing.item].owner = listing.seller
            draft.notes.append((listing.seller, 'Your unsold item returns to inventory. Its weight counts again.'))

    def changes(self, market: Market, bounties: Bounties) -> dict[str, Any]:
        def changed(old: dict[str, Any], new: dict[str, Any]) -> list[dict[str, Any]]:
            return [asdict(v) for key, v in new.items()
                    if key not in old or v is not old[key] and v != old[key]]
        return {'listings': changed(self.market.listings, market.listings),
                'bids': changed(self.market.bids, market.bids),
                'bounties': changed(self.bounties.rows, bounties.rows),
                'serials': {'market': market.serial, 'bounty': bounties.serial}}

    def write(self, draft: Proposal, session: Session | None = None,
              after: Callable[[bool], None] = lambda success: None) -> bool:
        def committed(success: bool) -> None:
            if success:
                self.market, self.bounties = draft.market, draft.bounties
                self.core.relays.ledger = draft.relays
                if self.lat.interlock.state != draft.interlock:
                    self.lat.interlock.state = draft.interlock
                    self.lat.interlock.compose()
                for pid, patch in draft.patches.items():
                    if 'inventory' in patch:
                        self.core.progression.sync_actor(self.game.players[pid])
                for pid, text in draft.notes:
                    self.notify(pid, text)
            elif session:
                self.commerce.toast(session, 'The market transfer could not be saved. Your goods and escrow remain.')
            after(success)
        if not self.commerce.settle(None, {}, draft.items, self.commerce.caches,
                                    self.commerce.serial, committed):
            return False
        effect = self.commerce.outbox[-1]
        effect.update(player_patches=draft.patches, market_changes=self.changes(draft.market, draft.bounties),
                      market_audit=draft.audit)
        if draft.interlock != self.lat.interlock.state:
            effect['interlock_state'] = draft.interlock
        if draft.relays.record() != self.core.relays.record():
            effect['relays_state'] = draft.relays.record()
        return True

    def request(self, session: Session, action: str, args: dict[str, Any]) -> None:
        args = deepcopy(args)
        self.commerce.enqueue_system(lambda: self.execute(session, action, args))

    def listable(self, player: Player, item: ItemInstance) -> bool:
        return bool(item.owner == player.id and item.id in player.inventory
            and not (item.secured or item.bound or item.mission
                or self.commerce.content.items[item.template].no_vendor_sale
                or item.id in (*player.equipment.values(), *player.implants.values())))

    def execute(self, session: Session, action: str, args: dict[str, Any]) -> None:
        try:
            self.terminal(session, args.get('terminal', ''), bank=action == 'collect')
            player = self.game.players[session.player_id]
            draft = self.draft()
            if action == 'list':
                inv = Inventory(draft.items, self.commerce.content.items)
                item = inv.owned(player, args['item'])
                if not self.listable(player, item):
                    raise ValueError('List an unsecured, unequipped item without a binding or mission.')
                listing = draft.market.list_item(player.id, item.id, args['price'], args.get('buyout'), args['expiry'], self.now())
                listing.item_snapshot = item.record()
                draft.patches[player.id] = {'inventory': [i for i in player.inventory if i != item.id]}
                item.owner = 'market'
                draft.notes.append((player.id, 'Your item is listed. Its instance and condition are unchanged.'))
                args = {**args, 'listing': listing.id}
            elif action == 'bid':
                bid, previous = draft.market.bid(args['listing'], player.id, args['chits'], self.now())
                if previous:
                    self.bank(draft, previous.bidder, previous.amount)
                    draft.notes.append((previous.bidder, 'Your previous market escrow returns to your bank.'))
                self.bank(draft, player.id, -bid.amount)
                draft.notes.extend([(player.id, 'Your bid is held in escrow.'),
                                    (draft.market.listings[bid.listing].seller, 'Market bid received.')])
            elif action == 'buyout':
                listing, previous = draft.market.buyout(args['listing'], player.id, self.now())
                if previous:
                    self.bank(draft, previous.bidder, previous.amount)
                    draft.notes.append((previous.bidder, 'Your previous market escrow returns to your bank.'))
                self.bank(draft, player.id, -listing.price)
                self.sale(draft, listing)
            elif action == 'cancel':
                listing, _ = draft.market.cancel(args['listing'], player.id, self.now())
                self.sale(draft, listing)
            elif action == 'collect':
                entry = draft.interlock.get('impounds', {}).get(player.id, {}).get('items', {}).get(args['item'])
                item = draft.items.get(args['item'])
                if not entry or entry.get('source') != 'market' or not item or item.owner != 'impound:'+player.id:
                    raise ValueError('Choose a market delivery from your personal impound.')
                inventory = [*player.inventory, item.id]
                carrier = deepcopy(player)
                carrier.inventory = inventory
                mods = self.core.progression.modifiers(player)
                capacity = carry_kg(mods.attribute(player, 'frame')) + mods.bonus('carry_kg')
                if Inventory(draft.items, self.commerce.content.items).weight(carrier) > capacity:
                    raise ValueError('Make room in your carry weight. The delivery stays protected.')
                item.owner = player.id
                draft.patches[player.id] = {'inventory': inventory}
                del draft.interlock['impounds'][player.id]['items'][item.id]
                draft.notes.append((player.id, 'Market delivery collected. No fee.'))
            elif action == 'post':
                target = self.game.players.get(args['target'])
                if not target or target.origin != player.origin or target.id in self.game.deleting:
                    raise ValueError('Choose a character on this origin.')
                row = draft.bounties.post(player.id, target.id, target.grade, args['chits'], self.now())
                self.bank(draft, player.id, -row.chits)
                notice = self.commerce.content.text.get('text-bounty-notice')
                text = (notice.body if notice else 'A price has been put on {name}. {chits} chits.').strip().format(name=target.name, chits=row.chits)
                draft.notes.extend([(player.id, text), (target.id, text)])
            else:
                raise ValueError('Unknown market action.')
            draft.audit.append({'action': 'bounty.post' if action == 'post' else 'market.'+action,
                                'player': player.id, 'args': deepcopy(args)})
            if not self.write(draft, session):
                raise ValueError('The market is busy. Try again.')
        except (ValueError, KeyError, TypeError) as exc:
            self.commerce.toast(session, str(exc) if isinstance(exc, ValueError) else 'That market choice is no longer available.')

    def expire(self) -> None:
        if self.commerce.pending:
            return
        now = self.now()
        if not (any(v.status == 'open' and v.expires_at <= now for v in self.market.listings.values())
                or any(v.status == 'active' and v.expires_at <= now for v in self.bounties.rows.values())):
            return
        draft = self.draft()
        for listing, _ in draft.market.expire(now):
            self.sale(draft, listing)
            draft.audit.append({'action': 'market.expire', 'listing': listing.id})
        for bounty in draft.bounties.expire(now):
            self.bank(draft, bounty.poster, bounty.chits)
            draft.notes.append((bounty.poster, 'Your expired bounty returns to your bank.'))
            draft.audit.append({'action': 'bounty.expire', 'bounty': bounty.id})
        self.write(draft)

    def stage_death(self, effect: dict[str, Any], victim: Player, killer: Player | None) -> None:
        if not killer or killer.id == victim.id or killer.id in self.game.deleting:
            return
        zone = self.game.world.zones[victim.zone]
        bounties = self.bounties.fork()
        payments = bounties.claim(victim.id, killer.id, self.now(), zone.template.meta.safety in ('contested', 'open') and zone.allows_hostile(victim.tile))
        if not payments:
            return
        patches = effect.setdefault('player_patches', {})
        for row, pid in payments:
            patch = patches.setdefault(pid, {})
            patch['chits_bank'] = patch.get('chits_bank', self.game.players[pid].chits_bank) + row.chits
        effect['market_changes'] = self.changes(self.market, bounties)
        effect['market_audit'] = [{'action': 'bounty.'+row.status, **asdict(row)} for row, _ in payments]
        previous = effect.get('callback', lambda success: None)
        def committed(success: bool) -> None:
            previous(success)
            if success:
                self.bounties = bounties
                for row, pid in payments:
                    self.notify(pid, f'Bounty {row.status}: {row.chits} chits reach your bank.')
                self.notify(victim.id, 'The bounties on your name are settled.')
        effect['callback'] = committed

    def prepare_retirement(self, session: Session, player: Player, proceed: Callable[[], None]) -> None:
        def prepare() -> None:
            draft = self.draft()
            returns, refunds = draft.market.retire(player.id, self.now())
            bounties = draft.bounties.retire(player.id)
            inventory = list(player.inventory)
            for bid in refunds:
                self.bank(draft, bid.bidder, bid.amount)
                draft.notes.append((bid.bidder, 'A retiring character releases your market escrow.'))
            impound = draft.interlock.get('impounds', {}).get(player.id, {}).get('items', {})
            deliveries = [iid for iid, entry in impound.items() if entry.get('source') == 'market']
            for iid in [*(listing.item for listing in returns), *deliveries]:
                draft.items[iid].owner = player.id
                if iid not in inventory:
                    inventory.append(iid)
                impound.pop(iid, None)
            for bounty in bounties:
                self.bank(draft, bounty.poster, bounty.chits)
                draft.notes.append((bounty.poster, 'A retiring character releases your bounty escrow.'))
            if not (returns or refunds or bounties or deliveries):
                proceed()
                return
            draft.patches.setdefault(player.id, {})['inventory'] = inventory
            draft.audit.append({'action': 'market.retire', 'player': player.id})
            def finished(success: bool) -> None:
                if success:
                    proceed()
                else:
                    self.game.screens[session.id] = ('sheet', 0)
                    self.game.dirty_screens.add(session.id)
            self.write(draft, session, finished)
        self.commerce.enqueue_system(prepare)

    def input(self, session: Session, frame: Frame, tick: int) -> bool:
        return self.views.input(session, frame, tick)

    def admin(self, name: str, args: dict[str, Any], reply: Callable[[Any], None]) -> None:
        if name in ('market.list', 'bounty.list'):
            # Architecture 15.2: bounded operator pages, full history retained.
            rows = list(self.market.listings.values() if name == 'market.list' else self.bounties.rows.values())
            pages = max(1, (len(rows)+99)//100)
            page = args.get('page', 1)
            if type(page) is not int or page < 1:
                reply({'ok': False, 'error': 'Page must be a positive integer.'})
                return
            selected = rows[(page-1)*100:page*100]
            result = {'page': page, 'pages': pages, 'total': len(rows),
                      'listings' if name == 'market.list' else 'bounties': [asdict(row) for row in selected]}
            if name == 'market.list':
                ids = {row.id for row in selected}
                result['bids'] = [asdict(row) for row in self.market.bids.values()
                                  if row.listing in ids and row.status == 'held']
            reply(result)
            return
        def propose() -> None:
            try:
                draft = self.draft()
                if name == 'market.cancel':
                    listing, previous = draft.market.cancel(args['listing'], None, self.now())
                    if previous:
                        self.bank(draft, previous.bidder, previous.amount)
                        draft.notes.append((previous.bidder, 'The operator cancels a listing. Your escrow returns.'))
                    self.sale(draft, listing)
                elif name == 'bounty.refund':
                    bounty = draft.bounties.refund(args['bounty'])
                    self.bank(draft, bounty.poster, bounty.chits)
                    draft.notes.append((bounty.poster, 'The operator refunds your bounty.'))
                else:
                    raise ValueError('Unknown market operator command.')
                draft.audit.append({'action': name, 'args': deepcopy(args)})
                self.write(draft, after=lambda success: reply({'ok': success}))
            except (ValueError, KeyError) as exc:
                reply({'ok': False, 'error': str(exc)})
        try:
            self.commerce.enqueue_system(propose)
        except ValueError as exc:
            reply({'ok': False, 'error': str(exc)})

    def tick(self, ctx: TickContext) -> None:
        if ctx.tick-self.last_expiry >= TICK_HZ:
            self.last_expiry = ctx.tick
            self.expire()
        self.views.tick(ctx)
