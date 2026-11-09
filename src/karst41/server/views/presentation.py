"""Caller-specific presentation, never inputs to simulation rules (5.5.6)."""

from karst41.content.loader import ContentTree
from karst41.server.world.actors import Actor
from karst41.npc_presentation import npc_class, cover_role


def true_class(actor: Actor, content: ContentTree) -> str:
    if actor.kind == "player":
        return "caller"
    if actor.kind == "drone":
        return "drone"
    template = content.npcs.get(actor.behaviour.get("template"))
    return npc_class(template, actor.faction)


def presented_class(actor: Actor, viewer: Actor, content: ContentTree) -> str:
    template = content.npcs.get(actor.behaviour.get("template"))
    if actor.kind == "npc" and template and template.presents and viewer.id not in actor.revealed_to:
        return template.presents
    return true_class(actor, content)


def covered(actor: Actor, viewer: Actor, content: ContentTree) -> bool:
    return presented_class(actor, viewer, content) != true_class(actor, content)


def name(actor: Actor, viewer: Actor, content: ContentTree) -> str:
    if covered(actor, viewer, content):
        template = content.npcs.get(actor.behaviour.get("template"))
        if template is None or not template.cover_name:
            raise ValueError("covered NPC requires a validated cover_name")
        return template.cover_name
    return actor.name


def role(actor: Actor, viewer: Actor, content: ContentTree, legacy: str) -> str:
    if not covered(actor, viewer, content):
        return legacy
    return cover_role(presented_class(actor, viewer, content))


def object_role(kind: str, params: dict[str, object]) -> str:
    if params.get("dropped_item"):
        return "cache"
    if params.get("vendor"):
        return "vendor"
    return kind
