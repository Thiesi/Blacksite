"""Game 8.4: one per-template policy for actual and displayed item stats."""

from collections.abc import Mapping
from random import Random

from blacksite.content.schema import ItemTemplate
from blacksite.server.items import QUALITY_MAX, QUALITY_MIN

QUALITY_SKILL_SPAN = .15  # Game 8.4: floor improvement from skill 0-100.
QUALITY_ROLL_SPAN = .15  # Game 8.4: unchanged uniform random span.
YARD_RELAY_BONUS = .05  # Game 8.4/7.7: S21 supplies the ownership hook.

# These are numeric magnitudes, never schedules, capacities or permissions.
IMPLANT_EFFECTS = frozenset({
    "dark_sight", "arm_k", "arm_e", "arm_c", "arm_d", "carry_kg",
    "stamina_regen_multiplier", "range_penalty_multiplier",
    "weapon_cooldown_multiplier", "kinetic_accuracy", "shock_decay_multiplier",
    "chemical_dot_multiplier", "stealth_sight_reduction", "health", "evasion",
    "heavy_cooldown_multiplier", "integrity", "cell_move_multiplier",
    "listening", "dissonance_damage_multiplier",
})
DRONE_EFFECTS = frozenset({"carry_kg", "heal_per_second"})


def validate_policy(template: ItemTemplate) -> str | None:
    policy = template.quality
    if policy.kind == "none":
        return "none quality must have an empty key" if policy.key else None
    if policy.kind == "weapon_damage":
        valid = template.weapon is not None and not policy.key
    elif policy.kind == "armour":
        valid = bool(template.armour and policy.key in ("kinetic", "energy", "chemical", "dissonance")
                     and getattr(template.armour.armour, policy.key, 0) > 0)
    elif policy.kind == "implant_effect":
        valid = bool(template.implant and policy.key in IMPLANT_EFFECTS
                     and policy.key in template.implant.effects)
    elif policy.kind == "drone_damage":
        valid = bool(template.drone and template.drone.attack and not policy.key)
    else:
        valid = bool(template.drone and policy.key in DRONE_EFFECTS
                     and policy.key in template.drone.effects)
    return None if valid else "quality selector needs a compatible scalable stat"


def value(template: ItemTemplate, quality: float, kind: str, key: str, base: float) -> float:
    """Only the selected magnitude changes; preserve quality-one exactly."""
    if template.quality.kind != kind or template.quality.key != key:
        return base
    if kind == "implant_effect" and key.endswith("_multiplier"):
        return 1 + (base-1)*quality
    return base*quality


def effects(template: ItemTemplate, quality: float, kind: str,
            base: Mapping[str, int | float]) -> dict[str, float]:
    return {key: value(template, quality, kind, key, raw) for key, raw in base.items()}


def damage_multiplier(template: ItemTemplate, quality: float) -> float:
    return quality if template.quality.kind in ("weapon_damage", "drone_damage") else 1


def roll(template: ItemTemplate | None, skill: float, rng: Random,
         relay_bonus: float = 0) -> float:
    if template is None or template.quality.kind == "none":
        return 1
    # Game 8.4: skill raises the floor; S21 Yard Relay supplies +0.05.
    return min(QUALITY_MAX, QUALITY_MIN+QUALITY_SKILL_SPAN*max(0, min(100, skill))/100
               +rng.uniform(0, QUALITY_ROLL_SPAN)+relay_bonus)


def bounds(template: ItemTemplate | None, skill: float, relay_bonus: float = 0) -> tuple[float, float]:
    if template is None or template.quality.kind == "none":
        return 1, 1
    floor = QUALITY_MIN+QUALITY_SKILL_SPAN*max(0, min(100, skill))/100+relay_bonus
    return min(QUALITY_MAX, floor), min(QUALITY_MAX, floor+QUALITY_ROLL_SPAN)


def detail(template: ItemTemplate, quality: float) -> str:
    lines = [f"Quality {quality*100:.0f}%"]
    if template.weapon:
        lines.append(f"Damage {template.weapon.damage*damage_multiplier(template, quality):g}, "
                     f"range {template.weapon.range or 'melee'}.")
    if template.armour:
        armour = template.armour.armour
        lines.append("Armour "+" ".join(f"{short}{int(value(template, quality, 'armour', key, getattr(armour, key)))}"
                     for short, key in (("K", "kinetic"), ("E", "energy"), ("C", "chemical"), ("D", "dissonance"))))
    if template.implant:
        lines.extend(f"{key.replace('_', ' ')} {raw:g}" for key, raw in
                     effects(template, quality, "implant_effect", template.implant.effects).items())
    if template.drone:
        if template.drone.attack:
            lines.append(f"Drone damage {template.drone.attack.damage*damage_multiplier(template, quality):g}")
        lines.extend(f"{key.replace('_', ' ')} {raw:g}" for key, raw in
                     effects(template, quality, "drone_effect", template.drone.effects).items())
    return "\n".join(lines)
