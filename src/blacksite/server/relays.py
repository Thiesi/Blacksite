"""Game 7.4: socket-free relay claims and exact influence accounting."""

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from blacksite.server.clock import TICK_HZ

HACK_HOLD_SECONDS = 180  # Game 7.4.
SOLO_HOLD_SECONDS = 480
ABSENCE_SECONDS = 5
CAPTURE_XP = 100
CAPTURE_STANDING = 15
CAPTURE_COOLDOWN_SECONDS = 86400
DAILY_SHARE_CAP = 200
MICROSECONDS = 1_000_000
POINT_DENOMINATOR = 3600 * MICROSECONDS


@dataclass(frozen=True)
class Participant:
    player: str
    identity: str
    faction: str | None


@dataclass
class Claim:
    id: str
    relay: str
    faction: str
    holder: Participant
    elapsed: int = 0
    absent_since: int | None = None
    supporters: dict[str, Participant] = field(default_factory=dict)
    hacked: set[str] = field(default_factory=set)

    @property
    def required(self) -> int:
        return (HACK_HOLD_SECONDS if self.hacked else SOLO_HOLD_SECONDS) * TICK_HZ

    def participants(self) -> tuple[Participant, ...]:
        return (self.holder, *(p for pid, p in self.supporters.items() if pid in self.hacked))


@dataclass(frozen=True)
class Capture:
    claim: str
    relay: str
    faction: str
    former: str | None
    participants: tuple[Participant, ...]
    rewarded: tuple[Participant, ...]


class Ledger:
    """Committed ownership, history, season totals and identity receipts.

    Callers fork this ledger and commit its record with the corresponding
    character changes. Claims themselves are live channels: restarting
    aborts them, rather than counting time with no conscious holder.
    """

    def __init__(self, state: dict[str, Any] | None = None) -> None:
        self.state = deepcopy(state or {})
        for key in ('relays', 'factions', 'capture_receipts', 'daily_receipts'):
            self.state.setdefault(key, {})
        self.state.setdefault('serial', 0)
        self.state.setdefault('season', 1)
        self.state.setdefault('cutoff', None)
        self.state.setdefault('captures', [])

    def fork(self) -> 'Ledger':
        return Ledger(self.state)

    def record(self) -> dict[str, Any]:
        return deepcopy(self.state)

    def owner(self, relay: str, at: float | None = None) -> str | None:
        record = self.state['relays'].get(relay, {})
        if at is None:
            return record.get('faction')
        return next((row['faction'] for row in reversed(record.get('history', [])) if row['at'] <= at), None)

    def totals(self, faction: str) -> dict[str, int]:
        return self.state['factions'].setdefault(faction, {'influence': 0, 'treasury': 0, 'fraction': 0})

    def settle(self, rates: dict[str, int], now: float) -> int:
        cutoff = self.state['cutoff']
        until = min(now, cutoff) if cutoff is not None else now
        paid = 0
        for rid, row in self.state['relays'].items():
            previous = row['paid_until']
            if until <= previous:
                continue
            if row['faction']:
                total = self.totals(row['faction'])
                elapsed = max(0, round(until*MICROSECONDS)-round(previous*MICROSECONDS))
                points, total['fraction'] = divmod(total['fraction']+elapsed*rates[rid], POINT_DENOMINATOR)
                total['influence'] += points
                total['treasury'] += points
                paid += points
            row['paid_until'] = until
        return paid

    def set_owner(self, relay: str, faction: str | None, player: str | None, now: float,
                  rates: dict[str, int]) -> None:
        self.settle(rates, now)
        row = self.state['relays'].setdefault(relay, {'history': [], 'paid_until': now})
        row.update(faction=faction, captured_at=now, captured_by=player, paid_until=now)
        row['history'].append({'at': now, 'faction': faction})

    def capture(self, claim: Claim, now: float, rates: dict[str, int]) -> Capture:
        former = self.owner(claim.relay)
        if former == claim.faction:
            raise ValueError('Your faction already holds this relay.')
        participants = claim.participants()
        rewarded = []
        for person in participants:
            key = person.identity+':'+claim.relay
            previous = self.state['capture_receipts'].get(key)
            if previous is None or now >= previous+CAPTURE_COOLDOWN_SECONDS:
                self.state['capture_receipts'][key] = now
                rewarded.append(person)
        self.set_owner(claim.relay, claim.faction, claim.holder.player, now, rates)
        self.state['serial'] += 1
        self.state['captures'].append({'id': self.state['serial'], 'season': self.state['season'],
            'relay': claim.relay, 'faction': claim.faction, 'former': former, 'at': now,
            'holder': claim.holder.player, 'participants': [person.player for person in participants],
            'rewarded': [person.player for person in rewarded]})
        return Capture(claim.id, claim.relay, claim.faction, former, participants, tuple(rewarded))

    def daily_share(self, identity: str, faction: str, utc_day: str) -> int:
        if self.state['daily_receipts'].get(identity) == utc_day:
            return 0
        total = self.totals(faction)
        amount = min(DAILY_SHARE_CAP, total['treasury']//100)
        if amount:
            total['treasury'] -= amount
            self.state['daily_receipts'][identity] = utc_day
        return amount

    def reset_season(self, season: int, cutoff: float, rates: dict[str, int]) -> None:
        self.state['cutoff'] = cutoff
        self.settle(rates, cutoff)
        for rid in tuple(self.state['relays']):
            self.set_owner(rid, None, None, cutoff, rates)
        # Treasury is currency already earned; only the season score resets.
        for total in self.state['factions'].values():
            total['influence'], total['fraction'] = 0, 0
        self.state['season'], self.state['cutoff'] = season, None


class Claims:
    def __init__(self) -> None:
        self.serial = 0
        self.active: dict[str, Claim] = {}
        self.last_tick: int | None = None

    def start(self, relay: str, participant: Participant) -> Claim:
        if not participant.faction:
            raise ValueError('Join a faction before holding a relay. You may support a named claim as a runner.')
        if any(c.holder.player == participant.player for c in self.active.values()):
            raise ValueError('Leave your current relay claim first.')
        if any(c.relay == relay and c.faction == participant.faction for c in self.active.values()):
            raise ValueError('Your faction already has an active claim here.')
        self.serial += 1
        claim = Claim(str(self.serial), relay, participant.faction, participant)
        self.active[claim.id] = claim
        return claim

    def support(self, claim: str, participant: Participant) -> None:
        current = self.active.get(claim)
        if current is None:
            raise ValueError('That claim has ended. Choose its current card.')
        if current.holder.player == participant.player:
            raise ValueError('Keep holding the physical terminal; another runner can support it.')
        for other in self.active.values():
            if participant.player in other.supporters:
                raise ValueError('Withdraw your existing runner support first.')
        current.supporters[participant.player] = participant

    def hack(self, claim: str, player: str) -> bool:
        current = self.active.get(claim)
        if current is None or player not in current.supporters:
            return False
        current.hacked.add(player)
        return True

    def withdraw(self, player: str) -> None:
        for cid, claim in tuple(self.active.items()):
            if claim.holder.player == player:
                self.active.pop(cid)
            claim.supporters.pop(player, None)
            claim.hacked.discard(player)

    def step(self, tick: int, conscious: set[str], present: set[str], paused: set[str]) -> tuple[Claim, ...]:
        delta = max(0, tick-self.last_tick) if self.last_tick is not None else 0
        self.last_tick = tick
        for cid, claim in tuple(self.active.items()):
            if claim.holder.player not in conscious:
                self.active.pop(cid)
            elif claim.holder.player not in present:
                if claim.absent_since is None:
                    claim.absent_since = tick
                elif tick-claim.absent_since > ABSENCE_SECONDS*TICK_HZ:
                    self.active.pop(cid)
            else:
                claim.absent_since = None
        ready = []
        for claim in self.active.values():
            if claim.absent_since is not None or claim.relay in paused:
                continue
            opposing = any(other.relay == claim.relay and other.faction != claim.faction
                and other.absent_since is None for other in self.active.values())
            if not opposing:
                claim.elapsed += delta
                if claim.elapsed >= claim.required:
                    ready.append(claim)
        return tuple(ready)
