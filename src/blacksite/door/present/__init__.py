"""Proposal 68 presentation renderers, selectable beside the shipped ones.

`docs/design/proposals/68-presentation/spec.md` is the contract. These
renderers draw the same authorized view bodies as `door.views`; they add
no sight, movement or game rules. A caller switches with F9, and
`BLACKSITE_PRESENTATION` (or `DOOR_BLACKSITE_PRESENTATION`) picks the
starting renderer.
"""

from collections.abc import Mapping


def enabled(environment: Mapping[str, str]) -> bool:
    value = environment.get("DOOR_BLACKSITE_PRESENTATION", environment.get("BLACKSITE_PRESENTATION", ""))
    return value.lower() in ("1", "on", "68", "place")
