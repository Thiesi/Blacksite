"""Shared physical channel state for power cuts, harvesting and crafting."""

from dataclasses import dataclass

from blacksite.server.world.actors import Actor


@dataclass
class PhysicalChannel:
    core: str
    zone: str
    object: str
    tile: tuple[int, int]
    until: int
    last_hit: int
    kind: str = "cut"
    recipe: str = ""

    def valid(self, actor: Actor | None) -> bool:
        return bool(actor and actor.zone == self.zone and actor.position == self.tile
                    and actor.stance == "normal" and actor.health > 0
                    and int(actor.behaviour.get("hit_serial", 0)) == self.last_hit)
