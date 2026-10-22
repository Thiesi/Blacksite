"""Game 3.3/3.5: meaningful skill use on a server-owned transaction draft.

Callers supply completed action receipts and eligibility facts, never
client claims. Day/encounter caps are separate from grade-point spending.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from math import ceil
from types import MappingProxyType

from blacksite.content.schema import SkillDefinition
from blacksite.server.players import Player
from blacksite.server.rules.character import SKILL_GROUPS, attributes

SKILL_MAX = 100  # Game 3.3.
DAILY_USE_CAP = 2  # Game 3.5, per line per character per UTC day.
STEALTH_ENCOUNTER_CAP = 1  # Game 3.5.
ENCOUNTER_IDLE_SECONDS = 60  # Game 3.5.

LINE_GROUP = MappingProxyType({line: group for group, lines in SKILL_GROUPS for line in lines})
# Game 3.5: named action, eligible lines, gain per completed receipt.
USE_RULES = MappingProxyType({
    "weapon_hit": (("kinetic", "energy"), .2),
    "melee_hit": (("melee",), .3),
    "armour_absorb": (("armour",), .1),
    "stealth_second": (("stealth",), .05),
    "drone_command": (("drones",), .1),
    "authored_cell": (("lattice",), .05),
    "program_change": (("programs",), .15),
    "fabricate": (("fabrication",), 1),
    "hymn_restore": (("hymns",), .15),
    "dissonance_threat": (("dissonance",), .15),
    "hidden_authored": (("listening",), .5),
})


@dataclass(frozen=True)
class Use:
    action: str
    line: str
    receipt: str
    eligible: bool = False
    changed: bool = False
    threat: bool = False
    training: bool = False
    self_or_crew: bool = False
    authored: bool = False
    seconds: float = 1
    encounter: str = ""


def eligible(use: Use) -> bool:
    if not use.receipt or not use.eligible or use.training or use.self_or_crew:
        return False
    if use.action in ("weapon_hit", "melee_hit", "armour_absorb", "stealth_second", "dissonance_threat"):
        return use.threat
    if use.action in ("authored_cell", "hidden_authored"):
        return use.authored and use.changed
    return use.changed


def gain(player: Player, use: Use, now: datetime, definition: SkillDefinition | None = None) -> float:
    """Mutate only a proposal; its enclosing receipt must commit atomically."""
    rule = USE_RULES.get(use.action)
    if not rule or use.line not in rule[0] or not eligible(use):
        return 0
    if use.action == "stealth_second" and (not use.encounter or use.seconds <= 0):
        return 0
    if now.tzinfo is None:
        raise ValueError("Skill-use receipts require an aware UTC clock.")
    day = now.astimezone(timezone.utc).date().isoformat()
    old = player.progress.get("skill_use", {})
    if old.get("day") == day:
        ledger = old
    else:
        # Retain one encounter's budget across midnight. The daily reset
        # alone must not give that same encounter another full point.
        ledger = {"day": day, "gains": {}, "receipts": [],
                  "stealth": old.get("stealth", {})}
    if use.receipt in ledger.get("receipts", ()):
        return 0
    used = float(ledger.get("gains", {}).get(use.line, 0))
    room = min(DAILY_USE_CAP-used, SKILL_MAX-float(player.skills.get(use.line, 0)))
    if definition is not None and definition.id != use.line:
        raise ValueError("Skill schedule does not match the awarded line.")
    amount = float(definition.uses.get(use.action, 0) if definition is not None else rule[1])
    if use.action == "stealth_second":
        encounter = ledger.get("stealth", {})
        previous = float(encounter.get("gain", 0)) if encounter.get("id") == use.encounter else 0
        amount = min(amount*use.seconds, STEALTH_ENCOUNTER_CAP-previous)
    amount = round(max(0, min(room, amount)), 6)
    if not amount:
        return 0
    ledger.setdefault("gains", {})[use.line] = round(used+amount, 6)
    ledger.setdefault("receipts", []).append(use.receipt)
    if use.action == "stealth_second":
        ledger["stealth"] = {"id": use.encounter, "gain": round(previous+amount, 6)}
    player.progress["skill_use"] = ledger
    player.skills[use.line] = round(float(player.skills.get(use.line, 0))+amount, 6)
    player.attributes = attributes(player.archetype, player.skills, player.grade)
    return amount


def spend(player: Player, line: str, points: int = 1) -> float:
    """The skill menu spends whole grade points; a final gain caps at 100."""
    if line not in LINE_GROUP or type(points) is not int or points <= 0:
        raise ValueError("Choose a skill and a positive number of grade points.")
    amount = round(min(points, SKILL_MAX-float(player.skills.get(line, 0))), 6)
    cost = ceil(amount)
    if amount <= 0:
        raise ValueError("That skill is already at 100.")
    if cost > player.progress.get("points", 0):
        raise ValueError("You do not have enough grade points.")
    player.progress["points"] -= cost
    player.skills[line] = round(float(player.skills.get(line, 0))+amount, 6)
    player.attributes = attributes(player.archetype, player.skills, player.grade)
    return amount
