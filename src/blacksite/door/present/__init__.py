"""Proposal 68 presentation renderers, selectable beside the shipped ones.

`docs/design/proposals/68-presentation/spec.md` is the contract. These
renderers draw the same authorized view bodies as `door.views`; they add
no sight, movement or game rules. A caller cycles shipped, map, street, scene and auto views with F7, and
`BLACKSITE_PRESENTATION` (or `DOOR_BLACKSITE_PRESENTATION`) picks the
starting renderer.
"""

from collections.abc import Mapping


def mode(environment: Mapping[str, str]) -> str:
    """`shipped`, or a proposal view: `map`, `street` (A), `scene` (B) or `auto` (C)."""
    value = environment.get("DOOR_BLACKSITE_PRESENTATION", environment.get("BLACKSITE_PRESENTATION", "")).lower()
    if value in ("street", "scene", "auto"):
        return value
    return "map" if value in ("1", "on", "68", "place", "map") else "shipped"


def enabled(environment: Mapping[str, str]) -> bool:
    return mode(environment) != "shipped"
