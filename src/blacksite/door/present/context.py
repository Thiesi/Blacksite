"""Pure, provisional P5 context decider, ported from V1 1060c9d.

The trial rule order and HOLD constant remain provisional until PT1.
P5 permits only the zone map. It wires no threat input, scene/look, key
or wall clock. Auto's other views require a later server-view contract;
see #106's technical and presentation decisions of 2026-10-30.
"""

from collections import deque
from dataclasses import dataclass, field
from typing import Any

HOLD = 5.0  # Provisional trial value, deliberately inactive in map-only P5.


@dataclass(frozen=True)
class Decision:
    view: str
    tag: str
    looking: bool
    rule: str
    why: str
    inputs: dict[str, Any] = field(default_factory=dict, compare=False)


@dataclass
class Context:
    last: Decision | None = None
    changes: deque[tuple[float, Decision]] = field(default_factory=lambda: deque(maxlen=12))

    def decide(self, body: dict[str, Any], now: float) -> Decision:
        """Injected bodies/clock only; there is no inferred threat signal."""
        return Decision('map', 'MAP', False, 'map-only', 'P5 enables only the zone map',
                        {'zone': body.get('me', {}).get('zone')})

    def choose(self, body: dict[str, Any], now: float) -> Decision:
        decision = self.decide(body, now)
        if self.last and self.last.inputs.get('zone') != decision.inputs.get('zone'):
            self.changes.clear()  # Architecture 5.5.4: discard old-zone client context.
        if decision != self.last:
            self.changes.append((now, decision))
        self.last = decision
        return decision
