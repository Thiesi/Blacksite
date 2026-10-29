"""Pure input decisions for architecture 5.5.2.

None passes input to the next handler. An empty Interaction consumes it
without advertising an action (menus, prompts, travel, and helpless states).
Target selection is independent of disclosure: an unseen target still owns
the input, but the view must not name it or substitute a lower priority one.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from blacksite.server.protocol import Frame
from blacksite.server.sessions import Session
from blacksite.server.world.zone import ObjectState


@dataclass(frozen=True)
class Focus:
    id: str
    label: str
    verb: str

    def record(self) -> dict[str, str]:
        return {"id": self.id, "label": self.label, "verb": self.verb}


@dataclass(frozen=True)
class Interaction:
    focus: Focus | None = None
    value: Any = None
    tile: tuple[int, int] | None = None
    actor_id: str | None = None
    kind: str = ""


@dataclass(frozen=True)
class InputRoute:
    name: str
    handler: Callable[..., bool | None]
    query: Callable[[Session, Frame], Interaction | None]
    final: bool = False


@dataclass(frozen=True)
class ResolvedInteraction:
    index: int
    route: InputRoute
    choice: Interaction


def key_action(keymap: dict[str, Any], session: Session, frame: Frame) -> str:
    name = frame.data.get("name", "") if frame.type == "intent" else ""
    key = frame.data.get("k", "") if frame.type == "key" else ""
    table = next((m for m in keymap.get("keymaps", []) if m["id"] == session.keymap_id), {})
    return next((a for a, keys in table.get("bindings", {}).items() if key in keys), name)


def interact(frame: Frame) -> bool:
    return (frame.type == "intent" and frame.data.get("name") == "interact"
            or frame.type == "key" and frame.data.get("k") in ("e", "E"))


def object_interaction(obj: ObjectState, verb: str = "open") -> Interaction:
    label = str(obj.spec.params.get("name") or obj.spec.id.replace("-", " ").replace("_", " "))
    return Interaction(Focus(obj.spec.id, label, verb), obj, obj.spec.tile)
