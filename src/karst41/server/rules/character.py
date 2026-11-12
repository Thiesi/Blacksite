"""Character arithmetic: game design 3.1-3.4 and 4, without I/O."""

from datetime import datetime, timedelta
import unicodedata

from karst41.content.ids import display_width as cell_width


def display_width(text: str) -> int:
    return sum(cell_width(char) for char in text)

ATTRIBUTE_NAMES = ("frame", "nerve", "cortex", "resonance", "vitals")
ARCHETYPES = (("hardline", (40, 20, 15, 5, 40)), ("ghost", (15, 40, 35, 10, 20)),
              ("cantor", (10, 20, 25, 45, 25)), ("operator", (20, 30, 30, 5, 30)))
SKILL_GROUPS = (("frame", ("kinetic", "melee", "armour")),
                ("nerve", ("energy", "stealth", "drones")),
                ("cortex", ("lattice", "programs", "fabrication")),
                ("resonance", ("hymns", "dissonance", "listening")))
MAX_GRADE, POINTS_PER_GRADE = 30, 3  # Game design 3.4.
LEASE_DAYS, SIGNATORY_GRADE = 90, 5
DISCHARGE_GRADE = SIGNATORY_GRADE  # Old name; architecture keeps `discharge_xp` (2026-11-12).
NAME_MIN, NAME_MAX = 2, 24  # Game design 4.
START_CHITS, CARD_STANDING = 200, 10  # Game design 4 and 7.1.
SLEEPER_SECONDS, SHOCK_DECAY_PER_SECOND = 60, 5  # Game design 2 and 3.1.


def health_max(vitals: int) -> int:
    return 50 + 2 * vitals


def stamina_max(nerve: int, frame: int) -> int:
    return 30 + nerve + frame // 2


def tolerance(vitals: int, archetype: str = "") -> int:
    return max(4, vitals // 10) + (2 if archetype == "hardline" else 0)


def evasion(nerve: int, equipment: int = 0) -> int:
    # Cover is a separate hit modifier (game design 3.1 and 5.3).
    return nerve // 3 + equipment


def carry_kg(frame: int) -> float:
    return frame / 2


def attributes(archetype: str, skills: dict[str, float] | None = None, grade: int = 1) -> dict[str, int]:
    result = dict(zip(ATTRIBUTE_NAMES, dict(ARCHETYPES)[archetype]))
    for attribute, lines in SKILL_GROUPS:
        result[attribute] = min(100, result[attribute] + int(sum((skills or {}).get(line, 0) for line in lines) // 10))
    result["vitals"] = min(100, result["vitals"] + grade - 1)
    return result


def grade_threshold(grade: int) -> int:
    if not 1 <= grade <= MAX_GRADE:
        raise ValueError("grade must be 1-30")
    return 0 if grade == 1 else 100 * grade * (grade + 1) // 2


def grade_for(xp: int, previous: int = 1) -> int:
    return max(previous, max(g for g in range(1, MAX_GRADE + 1) if grade_threshold(g) <= max(0, xp)))


def grade_name(grade: int) -> str:
    # Only named milestones in design 3.4; no invented intermediate ranks.
    return "Wake" if grade < 5 else "Signatory" if grade == 5 else f"Grade {grade}"


def legal_at(first_decant: datetime, grade: int, now: datetime, previous: str | None = None) -> str | None:
    """Personhood is calendar only (game design 3.4, owner 2026-11-12).

    Stamped once, when 90 days have passed since the first decant, with the
    value first_decant + 90 days even when first observed later. Grade never
    shortens it. A stamp already set (including one set early under the old
    grade 5 rule) stays: legal status is never removed (bible 8.1).
    """
    if previous is not None:
        return previous
    due = first_decant + timedelta(days=LEASE_DAYS)
    return due.isoformat() if now >= due else None


SIGNATORY_REQUIRED = "Signatory (grade 5) or day 90 is required."
# #223: the price notice once per character on reaching grade 5, when
# contested-zone grade protection ends (bible 4.3). It fits the 51 cells a
# menu or talk page leaves on the 80x24 hint row.
GRADE5_NOTICE = "Grade 5: G5+ can attack you in CONTESTED zones."


def signatory(grade: int, legal_at: str | None) -> bool:
    """Renting and joining: grade 5 (Signatory) or personhood, whichever is first."""
    return grade >= SIGNATORY_GRADE or legal_at is not None


def name_key(name: str) -> str:
    return unicodedata.normalize("NFC", name).casefold()


def reserved_name(name: str) -> bool:
    """Game design 4 step 7: the gurney-number form (`No. 0431`) is reserved.

    Reserved when the normalised key, with spaces and punctuation removed,
    is `no` followed only by digits.
    """
    key = "".join(c for c in name_key(name) if c.isalnum())
    return key.startswith("no") and len(key) > 2 and key[2:].isdigit()


GURNEY_TYPED = "That form is a gurney number. Choose another name."


def gurney_rename(name: str) -> str:
    """Forced rename at attach for a name that falls under the reserved form."""
    return f"{name} reads as a gurney number now. Choose another name."


def valid_name(name: str) -> bool:
    return NAME_MIN <= display_width(name) <= NAME_MAX and all(c.isalpha() or c.isdigit() or c in " -_'" for c in name)


def normalize_name(name: str) -> str:
    return unicodedata.normalize("NFC", name).strip()


def default_name(handle: str) -> str:
    result = ""
    for char in normalize_name(handle):
        if (char.isalpha() or char.isdigit() or char in " -_'") and display_width(result + char) <= NAME_MAX:
            result += char
    return result.strip() if valid_name(result.strip()) else "New Wake"
