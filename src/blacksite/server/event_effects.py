"""Game 12: bounded effect calculations; callers own publication and I/O."""

from typing import Any

from blacksite.content.schema import IceTemplate
from blacksite.server.lattice.ice import Ice


def beneficial(effect: dict[str, Any], multiplier: float) -> dict[str, Any]:
    """Scale named benefits, never damage, range, duration or a cooldown.

    March's magnitude is the stamina saving, so a 50% saving becomes
    65%, rather than multiplying the remaining cost in the wrong direction.
    Revive's eligibility/count and dissonance effects remain unchanged.
    """
    result = dict(effect)
    for key in ('heal', 'armour', 'stamina'):
        if result.get(key, 0) > 0:
            result[key] *= multiplier
    if result.get('shock', 0) < 0:
        result['shock'] *= multiplier
    if 0 < result.get('stamina_multiplier', 1) < 1:
        result['stamina_multiplier'] = max(0, 1-(1-result['stamina_multiplier'])*multiplier)
    return result


def compatible(base: IceTemplate, variant: IceTemplate) -> bool:
    """Only authored substitutes with the same counterplay and role."""
    return (not base.black and not variant.black and variant.id in base.variants
            and variant.tier <= base.tier and variant.class_ == base.class_
            and variant.role == base.role and variant.trigger == base.trigger
            and variant.behaviour == base.behaviour and variant.counters == base.counters)


def swap(ice: Ice, template: IceTemplate, tier: int, tick: int) -> None:
    """Keep received damage, activation/cast clocks, gates and status.

    Spawn computes only the new template's tiered stats. Installing its
    fresh timers would restart a cast or grant an immediate free attack.
    """
    stats = Ice.spawn(ice.id, template, ice.location, tier, tick, ice.affiliation)
    alive = ice.alive
    damage = max(0, ice.maximum-ice.integrity)
    ice.template = template
    ice.maximum, ice.attack, ice.meat_damage = stats.maximum, stats.attack, stats.meat_damage
    ice.integrity = max(0, ice.maximum-damage) if alive else 0
