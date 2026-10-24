"""Game 7.1/7.2/7.6: pure standing, membership and perk receipts.

Callers mutate player/identity proposals and publish only after their
owning commerce transaction commits. No reputation notification pays a
second reward after commit.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from blacksite.content.schema import Faction, WakeCard
from blacksite.server.players import Player

@dataclass(frozen=True)
class EventOffer:
    """S24 supplies information about a plan already committed."""
    plan_id: str
    text: str
    revision: int = 1


STANDING_MIN = -100  # Game 7.1.
STANDING_MAX = 100
JOIN_STANDING = 30
LEAVE_STANDING = -50
LEAVE_DAYS = 7
RANK_THRESHOLDS = (30, 50, 70, 90)
PERK_STANDING = 90  # Game 7.6: titles below this grant no perk.
NPC_KILL_STANDING = -5  # Game 7.1: explicit, not propagated twice.
NPC_ENEMY_STANDING = 2
PLAYER_KILL_STANDING = -10
MARKED_KILL_STANDING = 5
MARKED_KILL_SECONDS = 86400  # Game 7.1: once per victim BBS identity.
CUT_STANDING = -10
THEFT_REPORT_STANDING = -10
CONTAINMENT_SERVICE_FEE = 150  # Game 7.6.
SABLE_RESERVATION_SECONDS = 600  # Game 7.6.


def relation(factions: dict[str, Faction], source: str | None, target: str | None) -> str:
    if not source or not target:
        return "N"
    if source == target:
        return "A"
    faction = factions.get(source)
    return faction.relations.get(target, "N") if faction else "N"


def standing(player: Player, faction: str) -> int:
    return player.standing.get(faction, 0)


def normalize_card_standing(player: Player, cards: dict[str, WakeCard]) -> bool:
    """Migrate card-only IDs once without granting card holders membership."""
    changed = False
    for cid, card in cards.items():
        if not card.faction or card.faction == cid:
            continue
        if cid in player.standing:
            old = player.standing.pop(cid)
            player.standing[card.faction] = max(STANDING_MIN, min(STANDING_MAX,
                player.standing.get(card.faction, 0)+old))
            changed = True
        if player.faction == cid:
            player.faction = card.faction
            changed = True
    return changed


def vector(factions: dict[str, Faction], changes: dict[str, int],
           mode: str = "propagate") -> dict[str, int]:
    if mode not in ("propagate", "explicit"):
        raise ValueError("Standing mode must be propagate or explicit.")
    result: dict[str, int] = {}
    for fid, delta in changes.items():
        if fid not in factions or type(delta) is not int:
            raise ValueError("Standing needs a known faction and whole delta.")
        result[fid] = result.get(fid, 0)+delta
        if mode == "explicit":
            continue
        half = (abs(delta)//2)*(1 if delta >= 0 else -1)
        for other, attitude in factions[fid].relations.items():
            if attitude in ("A", "H"):
                result[other] = result.get(other, 0)+(half if attitude == "A" else -half)
    return result


def apply_vector(player: Player, factions: dict[str, Faction], changes: dict[str, int],
                 mode: str = "propagate") -> dict[str, int]:
    """Combine once, then clamp; explicit story vectors have no cascade."""
    applied: dict[str, int] = {}
    for fid, delta in vector(factions, changes, mode).items():
        before = standing(player, fid)
        after = max(STANDING_MIN, min(STANDING_MAX, before+delta))
        if after != before:
            player.standing[fid] = after
            applied[fid] = after-before
    return applied


def apply_delta(player: Player, factions: dict[str, Faction], faction: str,
                delta: int, mode: str = "propagate") -> dict[str, int]:
    return apply_vector(player, factions, {faction: delta}, mode)


def rank(player: Player, factions: dict[str, Faction], faction: str | None = None) -> str:
    fid = faction or player.faction
    definition = factions.get(fid)
    if not definition:
        return ""
    return next((row.title for row in reversed(definition.ranks)
                 if standing(player, fid) >= row.standing), "")


def perk(player: Player, faction: str) -> bool:
    return player.faction == faction and standing(player, faction) >= PERK_STANDING


def join(player: Player, factions: dict[str, Faction], faction: str, now: datetime) -> None:
    if faction not in factions:
        raise ValueError("Choose one of the eight factions.")
    if player.faction:
        raise ValueError("Leave your current faction first.")
    if not player.legal_at:
        raise ValueError("Legal discharge is required: grade 5 or ninety days.")
    if player.progress.get("faction_cooldown_until", 0) > now.timestamp():
        raise ValueError("Seven days must pass after leaving a faction.")
    if standing(player, faction) < JOIN_STANDING:
        raise ValueError("Standing +30 is required to join.")
    player.faction = faction


def leave(player: Player, factions: dict[str, Faction], now: datetime) -> dict[str, int]:
    if not player.faction:
        raise ValueError("You are Freelance.")
    former = player.faction
    player.faction = None
    player.progress["faction_cooldown_until"] = (now+timedelta(days=LEAVE_DAYS)).timestamp()
    return apply_delta(player, factions, former, LEAVE_STANDING, "explicit")


def claim_daily(identity: dict[str, Any], key: str, now: datetime) -> bool:
    day = now.astimezone(timezone.utc).date().isoformat()
    receipts = identity.setdefault("receipts", {}).setdefault("faction_perks", {})
    if receipts.get(key) == day:
        return False
    receipts[key] = day
    return True


def npc_kill(factions: dict[str, Faction], faction: str | None) -> dict[str, int]:
    if faction not in factions:
        return {}
    return {faction: NPC_KILL_STANDING, **{other: NPC_ENEMY_STANDING
        for other, attitude in factions[faction].relations.items() if attitude == "H"}}


def player_kill(player: Player, victim: Player, factions: dict[str, Faction],
                identity: dict[str, Any], now: datetime) -> dict[str, int]:
    """Both ordinary loss and a capped Marked reward form one explicit vector."""
    if player.bbs_user_id == victim.bbs_user_id:
        return {}
    result: dict[str, int] = {}
    if victim.faction and relation(factions, player.faction, victim.faction) != "H":
        result[victim.faction] = PLAYER_KILL_STANDING
    if victim.marked_until and datetime.fromisoformat(victim.marked_until) > now:
        receipts = identity.setdefault("receipts", {}).setdefault("marked_kills", {})
        if receipts.get(victim.bbs_user_id, 0) <= now.timestamp():
            result["wardens"] = result.get("wardens", 0)+MARKED_KILL_STANDING
            receipts[victim.bbs_user_id] = now.timestamp()+MARKED_KILL_SECONDS
    return result
