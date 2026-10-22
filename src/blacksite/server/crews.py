"""Game 10: deterministic live membership, invitations and drop offers.

No session, transport, storage or clock access. Owners pass ticks, validate
online character identity, and commit loot rotation with their receipt.
"""
from dataclasses import dataclass, replace
from fractions import Fraction
from typing import Literal

from blacksite.server.clock import TICK_HZ

CREW_MIN = 2  # Game 10.
CREW_MAX = 5
INVITE_SECONDS = 60
OFFER_SECONDS = 10
FULL_XP_GAP = 5
XP_GAP_DIVISOR = 20
MIN_XP_SHARE = Fraction(1, 4)
LootMode = Literal['ffa', 'round_robin']


@dataclass
class Crew:
    id: str
    leader: str
    members: tuple[str, ...]
    loot: LootMode = 'ffa'
    allow_invites: bool = False
    beacon: tuple[str, str] | None = None  # Operator, target.
    next_loot: int = 0
    loot_version: int = 0


@dataclass(frozen=True)
class Invitation:
    id: str
    inviter: str
    target: str
    crew_id: str | None
    until_tick: int


@dataclass(frozen=True)
class Change:
    crew_id: str
    before: tuple[str, ...]
    members: tuple[str, ...]
    leader: str | None

    @property
    def dissolved(self) -> bool:
        return not self.members


@dataclass(frozen=True)
class LootOffer:
    crew_id: str
    members: tuple[str, ...]
    mode: LootMode
    recipient: str | None
    until_tick: int
    version: int

    def permits(self, player: str, tick: int) -> bool:
        """Apply after victim recovery and ordinary loot/access checks."""
        return self.mode == 'ffa' or tick >= self.until_tick or player == self.recipient


def share_multiplier(source_grade: int, recipient_grade: int) -> Fraction:
    gap = max(0, abs(source_grade-recipient_grade)-FULL_XP_GAP)
    return max(MIN_XP_SHARE, Fraction(1)-Fraction(gap, XP_GAP_DIVISOR))


def shared_xp(base: int, source_grade: int, recipient_grade: int) -> int:
    award = base*share_multiplier(source_grade, recipient_grade)
    return max(0, award.numerator//award.denominator)


class Registry:
    def __init__(self, origin: str, boot: str) -> None:
        self.origin, self.boot, self.serial = origin, boot, 0
        self.crews: dict[str, Crew] = {}
        self.memberships: dict[str, str] = {}
        self.invites: dict[str, Invitation] = {}

    def new_id(self, kind: str) -> str:
        self.serial += 1
        return f'{self.origin}:{kind}:{self.boot}.{self.serial}'

    def crew_of(self, player: str) -> Crew | None:
        return self.crews.get(self.memberships.get(player, ''))

    def together(self, one: str, other: str) -> bool:
        cid = self.memberships.get(one)
        return bool(cid and cid == self.memberships.get(other))

    def leader(self, player: str) -> Crew:
        crew = self.crew_of(player)
        if not crew or crew.leader != player:
            raise ValueError('Only the crew leader may do that.')
        return crew

    def expire(self, tick: int) -> tuple[Invitation, ...]:
        expired = tuple(invite for invite in self.invites.values() if tick >= invite.until_tick)
        for invite in expired:
            self.invites.pop(invite.id)
        return expired

    def invite(self, inviter: str, target: str, tick: int) -> Invitation:
        self.expire(tick)
        if inviter == target or self.crew_of(target):
            raise ValueError('Choose another online character without a crew.')
        crew = self.crew_of(inviter)
        if crew and (crew.leader != inviter and not crew.allow_invites):
            raise ValueError('Only the leader may invite until member invites are enabled.')
        if crew and len(crew.members) >= CREW_MAX:
            raise ValueError('This crew already has five members.')
        old = next((i for i in self.invites.values() if i.inviter == inviter and i.target == target), None)
        if old:
            return old
        invitation = Invitation(self.new_id('invite'), inviter, target, crew.id if crew else None,
                                tick+INVITE_SECONDS*TICK_HZ)
        self.invites[invitation.id] = invitation
        return invitation

    def offered(self, target: str, invitation: str, tick: int) -> Invitation:
        offer = self.invites.get(invitation)
        if not offer or offer.target != target:
            raise ValueError('That invitation is no longer available to you.')
        if tick >= offer.until_tick:
            self.invites.pop(invitation)
            raise ValueError('That invitation expired.')
        return offer

    def accept(self, target: str, invitation: str, tick: int) -> Crew:
        offer = self.offered(target, invitation, tick)
        if self.crew_of(target):
            raise ValueError('Leave your current crew first.')
        crew = self.crews.get(offer.crew_id) if offer.crew_id else None
        if offer.crew_id:
            if (not crew or offer.inviter not in crew.members
                    or crew.leader != offer.inviter and not crew.allow_invites):
                raise ValueError('That invitation no longer has crew approval.')
            if len(crew.members) >= CREW_MAX:
                raise ValueError('The crew filled before you accepted.')
            crew.members += (target,)
        else:
            if self.crew_of(offer.inviter):
                raise ValueError('The inviter has changed crews. Ask for a new invitation.')
            crew = Crew(self.new_id('crew'), offer.inviter, (offer.inviter, target))
            self.crews[crew.id] = crew
            self.memberships[offer.inviter] = crew.id
            for iid, other in tuple(self.invites.items()):
                if other.target == offer.inviter:
                    self.invites.pop(iid)
                elif other.inviter == offer.inviter and other.crew_id is None:
                    self.invites[iid] = replace(other, crew_id=crew.id)
        self.memberships[target] = crew.id
        self.clear_invites(target)
        return crew

    def decline(self, target: str, invitation: str, tick: int) -> None:
        self.offered(target, invitation, tick)
        self.invites.pop(invitation)

    def clear_invites(self, player: str) -> None:
        self.invites = {iid: invite for iid, invite in self.invites.items()
                        if player not in (invite.inviter, invite.target)}

    def remove(self, player: str) -> Change | None:
        self.clear_invites(player)
        crew = self.crew_of(player)
        if not crew:
            return None
        before = crew.members
        next_player = before[crew.next_loot % len(before)]
        self.memberships.pop(player)
        crew.members = tuple(pid for pid in before if pid != player)
        if len(crew.members) < CREW_MIN:
            self.crews.pop(crew.id)
            for pid in crew.members:
                self.memberships.pop(pid)
            self.invites = {iid: i for iid, i in self.invites.items() if i.crew_id != crew.id}
            return Change(crew.id, before, (), None)
        if crew.leader == player:
            crew.leader = crew.members[0]
        if crew.beacon and player in crew.beacon:
            crew.beacon = None
        crew.next_loot = (crew.members.index(next_player) if next_player in crew.members
                          else before.index(player) % len(crew.members))
        return Change(crew.id, before, crew.members, crew.leader)

    def leave(self, player: str) -> Change:
        change = self.remove(player)
        if change is None:
            raise ValueError('You are not in a crew.')
        return change

    def kick(self, leader: str, target: str) -> Change:
        crew = self.leader(leader)
        if target == leader or target not in crew.members:
            raise ValueError('Choose another member of your crew.')
        return self.leave(target)

    def promote(self, leader: str, target: str) -> None:
        crew = self.leader(leader)
        if target not in crew.members:
            raise ValueError('Choose a member of your crew.')
        crew.leader = target

    def invitations_allowed(self, leader: str, allowed: bool) -> None:
        self.leader(leader).allow_invites = allowed

    def loot_mode(self, leader: str, mode: LootMode) -> None:
        if mode not in ('ffa', 'round_robin'):
            raise ValueError('Choose free-for-all or round-robin.')
        self.leader(leader).loot = mode

    def beacon(self, operator: str, target: str | None, is_operator: bool) -> None:
        crew = self.crew_of(operator)
        if not is_operator or not crew or target is not None and target not in crew.members:
            raise ValueError('An Operator can mark only a member of their own crew.')
        crew.beacon = (operator, target) if target is not None else None

    def offer(self, player: str, tick: int) -> LootOffer | None:
        crew = self.crew_of(player)
        if not crew:
            return None
        recipient = crew.members[crew.next_loot % len(crew.members)] if crew.loot == 'round_robin' else None
        return LootOffer(crew.id, crew.members, crew.loot, recipient,
                         tick+OFFER_SECONDS*TICK_HZ if recipient else tick, crew.loot_version)

    def commit_offer(self, offer: LootOffer) -> bool:
        crew = self.crews.get(offer.crew_id)
        if not crew or offer.mode != 'round_robin' or offer.version != crew.loot_version:
            return False
        if offer.recipient in crew.members:
            crew.next_loot = (crew.members.index(offer.recipient)+1) % len(crew.members)
        crew.loot_version += 1
        return True
