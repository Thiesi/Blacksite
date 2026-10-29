"""Caller-specific presentation, never inputs to simulation rules (5.5.6)."""

from blacksite.content.loader import ContentTree
from blacksite.server.world.actors import Actor


def true_class(actor: Actor, content: ContentTree) -> str:
    if actor.kind == "player":
        return "caller"
    if actor.kind == "drone":
        return "drone"
    template = content.npcs.get(actor.behaviour.get("template"))
    if actor.faction == "wardens":
        return "warden"
    behaviours = {b.kind for b in template.behaviours} if template else set()
    if "guard" in behaviours:
        return "security"
    if template and (template.vendor or "vendor" in behaviours or "talker" in behaviours):
        return "service"
    if template and any(b.params.get("hostile_all") for b in template.behaviours):
        return "hostile"
    return "civilian"


def presented_class(actor: Actor, viewer: Actor, content: ContentTree) -> str:
    template = content.npcs.get(actor.behaviour.get("template"))
    if actor.kind == "npc" and template and template.presents and viewer.id not in actor.revealed_to:
        return template.presents
    return true_class(actor, content)


def covered(actor: Actor, viewer: Actor, content: ContentTree) -> bool:
    return presented_class(actor, viewer, content) != true_class(actor, content)


def name(actor: Actor, viewer: Actor, content: ContentTree) -> str:
    # No cover-name field exists. Do not leak "Warden" in an authored name.
    return presented_class(actor, viewer, content).title() if covered(actor, viewer, content) else actor.name


def role(actor: Actor, viewer: Actor, content: ContentTree, legacy: str) -> str:
    if not covered(actor, viewer, content):
        return legacy
    return {"civilian": "npc_neutral", "warden": "npc_warden",
            "security": "npc_neutral", "service": "npc_vendor",
            "hostile": "npc_hostile"}[presented_class(actor, viewer, content)]


def object_role(kind: str, params: dict[str, object]) -> str:
    if params.get("dropped_item"):
        return "cache"
    if params.get("vendor"):
        return "vendor"
    return kind
