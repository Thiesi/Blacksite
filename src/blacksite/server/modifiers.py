"""One pure composition point for installed hardware and timed substances.

Game 3.1, 8.5, 8.6 and catalog 3/6. Simulation callers supply UTC seconds
and optional ability/event layers. Temporary values never enter permanent
skills or attribute-group arithmetic.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from blacksite.content.schema import ItemTemplate
from blacksite.server.items import ItemInstance, SECURED_SLOTS
from blacksite.server.players import Player
from blacksite.server.rules import character

# These values denote unlocks/capacities, rather than additive bonuses.
MAXIMUM_KEYS = frozenset({"hymn_tier", "dissonance_tier", "hymn_radius",
    "hidden_cell_radius", "jack_anywhere", "target_through_cover",
    "surge_inspect", "dissonance_knockdown_immune", "rig_slots", "dark_sight"})
# Resource changes are consumed once by the drug state machine, not per read.
RESOURCE_KEYS = frozenset({"health_over_time", "heal_seconds", "health_per_second"})


@dataclass(frozen=True)
class Modifiers:
    values: Mapping[str, float]
    installed_templates: frozenset[str] = frozenset()

    def bonus(self, key: str) -> float:
        return self.values.get(key, 0)

    def multiplier(self, key: str) -> float:
        return self.values.get(key, 1)

    def flag(self, key: str) -> bool:
        return bool(self.bonus(key))

    def skill(self, player: Player, line: str) -> float:
        return max(0, min(100, player.skills.get(line, 0)+self.bonus(line)))

    def attribute(self, player: Player, name: str) -> int:
        return max(0, min(100, int(player.attributes[name]+self.bonus(name))))

    def health_max(self, player: Player) -> int:
        return max(1, character.health_max(self.attribute(player, "vitals"))+int(self.bonus("health")))

    def tolerance(self, player: Player) -> int:
        return character.tolerance(self.attribute(player, "vitals"), player.archetype)+int(self.bonus("tolerance"))

    @property
    def secured_slots(self) -> int:
        return max(SECURED_SLOTS, SECURED_SLOTS+int(self.bonus("secured_slots")))


def compose(layers: Iterable[Mapping[str, int | float]]) -> Modifiers:
    """Bonuses add, multipliers multiply, unlocks take their highest tier."""
    values: dict[str, float] = {}
    for layer in layers:
        for key, raw in layer.items():
            if key in RESOURCE_KEYS:
                continue
            value = float(raw)
            if key.endswith("_multiplier"):
                values[key] = values.get(key, 1)*value
            elif key in MAXIMUM_KEYS:
                values[key] = max(values.get(key, 0), value)
            else:
                values[key] = values.get(key, 0)+value
    return Modifiers(MappingProxyType(values))


def collect(player: Player, items: Mapping[str, ItemInstance],
            templates: Mapping[str, ItemTemplate], now: float,
            extra: Iterable[Mapping[str, int | float]] = ()) -> Modifiers:
    layers: list[Mapping[str, int | float]] = []
    if player.archetype == "operator":
        layers.append({"drone_slots": 2})  # Game 3.2.
    implanted_rig = False
    installed: set[str] = set()
    for iid in sorted(set(player.implants.values())):
        item = items.get(iid)
        template = templates.get(item.template) if item and item.owner == player.id else None
        block = template.implant if template else None
        if not block or block.portable:
            continue
        installed.add(template.id)
        effects = dict(block.effects)
        # Catalog low-light optics adds three dark tiles; a flare supplies
        # an absolute minimum via the separate dark_sight key.
        if "dark_sight" in effects:
            effects["dark_sight_bonus"] = effects.pop("dark_sight")
        if block.rig_slots is not None:
            effects["rig_slots"] = block.rig_slots
            implanted_rig = True
        layers.append(effects)
    if player.archetype == "ghost" and not implanted_rig:
        layers.append({"jack_anywhere": 1, "rig_slots": 3})
        installed.add("imp_rig_native")
    dependent = {d["template"] for d in player.dependencies}
    crash_applied: set[str] = set()
    for state in player.drugs_active:
        template = templates.get(state["template"])
        if not template or not template.drug:
            continue
        if now < state["effect_until"]:
            layers.append(template.drug.effects)
        elif now < state["crash_until"] and state["template"] not in dependent:
            layers.append(template.drug.crash)
            crash_applied.add(state["template"])
    # Dependence survives a redose, death, logout and expired timed rows.
    for tid in sorted(dependent-crash_applied):
        template = templates.get(tid)
        if template and template.drug:
            layers.append(template.drug.crash)
    layers.extend(extra)
    result = compose(layers)
    return Modifiers(result.values, frozenset(installed))
