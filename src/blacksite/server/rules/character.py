"""Character arithmetic: game design 3.1-3.4 and 4, without I/O."""

from datetime import datetime, timedelta
import unicodedata

from blacksite.content.ids import display_width as cell_width


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
LEASE_DAYS, DISCHARGE_GRADE = 90, 5
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
    return "Wake" if grade < 5 else "Ninety-Day" if grade == 5 else f"Grade {grade}"


def legal_at(first_decant: datetime, grade: int, now: datetime, previous: str | None = None) -> str | None:
    if previous is not None:
        return previous
    due = first_decant + timedelta(days=LEASE_DAYS)
    if grade >= DISCHARGE_GRADE or now >= due:
        return min(now, due).isoformat()
    return None


def name_key(name: str) -> str:
    return unicodedata.normalize("NFC", name).casefold()


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
