"""Data-backed actors and faction relations (game design 5.5, 7.2)."""

from blacksite.content.loader import ContentTree
from blacksite.content.schema import NpcTemplate, WeaponBlock
from blacksite.server.world.actors import Actor
from blacksite.server.rules.character import health_max

EVALUATION_TICKS = 5
LOST_SIGHT_SECONDS = 20
DORMANT_SECONDS = 30 * 60
PROVOCATION_SECONDS = 5 * 60
HEAT_SECONDS = 10 * 60
RESPONSE_COUNT = 2
RESPONSE_RADIUS = 3
FLEE_FRACTION = .20
WANDER_PAUSE_TICKS = (2, 10)
SUBDUE_SECONDS = 3  # Game design 5.3.
SUBDUE_SHOCK = 80


def relation(content: ContentTree, source: str | None, target: str | None) -> str:
    if source and source == target:
        return "A"
    faction = content.factions.get(source)
    return faction.relations.get(target, "N") if faction else "N"


def weapon(content: ContentTree, template: NpcTemplate) -> WeaponBlock | None:
    item = content.items.get(template.weapon)
    return template.attack or (item.weapon if item else None)


def make_actor(template: NpcTemplate, actor_id: str, state: dict[str, object]) -> Actor:
    health = template.health or health_max(template.attributes.vitals)
    return Actor(actor_id, template.name, kind="drone" if template.training else "npc",
                 faction=template.faction, health=health, health_max=health,
                 behaviour={"template": template.id, "evasion": template.attributes.nerve/3, **state})
