"""Game 3.4/3.5: reward proposals and identity-scoped repetition limits.

These functions mutate transaction drafts only. The caller commits the
reward, its source state, player and identity together before publication.
No network intent can manufacture a Grant.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from math import ceil
from typing import Any, Literal

from blacksite.server.players import Player
from blacksite.server.modifiers import Modifiers
from blacksite.server.rules import character

COMBAT_BASE_XP = 20  # Game 3.5.
COMBAT_GRADE_STEP_XP = 2  # 20*(grade gap/10), game 3.5.
COMBAT_MIN_XP = 5
CORE_TIER_XP = 40
CRAFT_TIER_XP = 15
ZONE_DISCOVERY_XP = 25
CELL_DISCOVERY_XP = 5
CONTRIBUTION_XP = 25
RELAY_CAPTURE_XP = 100
RELAY_HOLD_XP = 10
RELAY_HOLD_SECONDS = 600
RELAY_HOLD_DAILY_CAP = 60
PVP_REWARD_SECONDS = 86400

RewardKind = Literal["combat", "run", "contract", "relay_capture", "relay_hold",
                     "craft", "zone_discovery", "cell_discovery", "contribution"]


@dataclass(frozen=True)
class Grant:
    kind: RewardKind
    receipt: str
    eligible: bool = False
    scope: str = ""
    tier: int = 0
    opponent_grade: int = 0
    opponent_identity: str = ""
    core: str = ""
    amount: int = 0  # Only the accepted contract supplies an XP amount.
    periods: int = 1  # Completed active hold periods, never offline catch-up.
    training: bool = False
    self_or_crew: bool = False
    authored: bool = False
    consumed_inputs: bool = False
    shared_base: int | None = None  # Game 10, trusted source XP after crew scaling.


@dataclass(frozen=True)
class Award:
    xp: int
    old_grade: int
    grade: int
    grade_points: int
    health_max: int
    discharged: bool


def combat_xp(own_grade: int, opponent_grade: int) -> int:
    return max(COMBAT_MIN_XP, COMBAT_BASE_XP+COMBAT_GRADE_STEP_XP*(opponent_grade-own_grade))


def amount(grant: Grant, player: Player) -> int:
    if not grant.eligible or not grant.receipt or grant.training:
        return 0
    if grant.kind == "combat":
        if grant.self_or_crew or grant.opponent_identity == player.bbs_user_id or grant.opponent_grade < 1:
            return 0
        return max(0, grant.shared_base) if grant.shared_base is not None else combat_xp(player.grade, grant.opponent_grade)
    if grant.kind == "run":
        return (max(0, grant.shared_base) if grant.shared_base is not None else CORE_TIER_XP*grant.tier) if grant.core and 1 <= grant.tier <= 5 else 0
    if grant.kind == "contract":
        return max(0, grant.amount)
    if grant.kind == "relay_capture":
        return RELAY_CAPTURE_XP
    if grant.kind == "relay_hold":
        return RELAY_HOLD_XP*max(0, grant.periods)
    if grant.kind == "craft":
        return CRAFT_TIER_XP*grant.tier if grant.consumed_inputs and 1 <= grant.tier <= 5 else 0
    if grant.kind == "zone_discovery":
        return ZONE_DISCOVERY_XP if grant.authored else 0
    if grant.kind == "cell_discovery":
        return CELL_DISCOVERY_XP if grant.authored else 0
    if grant.kind == "contribution":
        return CONTRIBUTION_XP
    raise ValueError("Unknown progression reward source.")


def award(player: Player, identity: dict[str, Any], grant: Grant, now: datetime,
          modifiers: Modifiers | None = None) -> Award | None:
    """Apply a verified source to player/identity drafts; return UI facts.

    Stable source scopes (for example an NPC spawner slot) keep a receipt
    watermark. Its owning engine must also retire the defeated spawn or
    complete the contract in this same transaction. Discovery and unique
    contribution sources retain their own permanent keys.
    """
    xp = amount(grant, player)
    if xp <= 0:
        return None
    if now.tzinfo is None:
        raise ValueError("Progression receipts require an aware UTC clock.")
    now = now.astimezone(timezone.utc)
    day, stamp = now.date().isoformat(), now.timestamp()
    receipts = player.progress.get("reward_receipts", {})
    key = grant.kind+":"+(grant.scope or grant.receipt)
    if receipts.get(key) == grant.receipt:
        return None
    if grant.kind in ("zone_discovery", "cell_discovery", "contribution") and key in receipts:
        return None
    if grant.kind == "run" and identity.get("run_xp_days", {}).get(grant.core) == day:
        return None
    if grant.kind == "combat" and grant.opponent_identity:
        last = identity.get("combat_xp_until", {}).get(grant.opponent_identity, 0)
        if last > stamp:
            return None
    if grant.kind == "relay_hold":
        old = identity.get("hold_xp", {})
        used = old.get("xp", 0) if old.get("day") == day else 0
        xp = min(xp, max(0, RELAY_HOLD_DAILY_CAP-used))
        if not xp:
            return None
        identity["hold_xp"] = {"day": day, "xp": used+xp}
    if grant.kind == "run":
        identity.setdefault("run_xp_days", {})[grant.core] = day
    if grant.kind == "combat" and grant.opponent_identity:
        identity.setdefault("combat_xp_until", {})[grant.opponent_identity] = stamp+PVP_REWARD_SECONDS
    old_grade, old_vitals, old_health = player.grade, player.attributes["vitals"], player.health
    old_max = modifiers.health_max(player) if modifiers else character.health_max(old_vitals)
    old_points = player.progress.get("points", 0)
    player.update_progression(player.xp+xp)
    new_max = modifiers.health_max(player) if modifiers else character.health_max(player.attributes["vitals"])
    if player.grade != old_grade:
        player.health = min(new_max, max(0, ceil(old_health*new_max/old_max)))
    player.progress.setdefault("reward_receipts", {})[key] = grant.receipt
    legal_before = identity.get("legal_at")
    player.update_personhood(identity, now)
    return Award(xp, old_grade, player.grade, player.progress.get("points", 0)-old_points,
                 new_max, legal_before is None and player.legal_at is not None)
