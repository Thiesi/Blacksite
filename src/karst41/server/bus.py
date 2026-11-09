"""Synchronous, instance-owned event dispatch inside a tick."""

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Event:
    kind: str
    data: dict[str, Any] = field(default_factory=dict)


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable[[Event], None]]] = defaultdict(list)

    def subscribe(self, kind: str, handler: Callable[[Event], None]) -> None:
        self._handlers[kind].append(handler)

    def publish(self, event: Event) -> None:
        for handler in tuple(self._handlers.get(event.kind, ())):
            handler(event)
