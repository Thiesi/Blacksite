"""Auto view: the door chooses the view from context (paradigm prototype C).

Rules, in order; the first that applies decides:

1. danger: anything threatening (a hazard, a target, a hostile, combat,
   heat) shows the tactical map at once. Nothing delays it.
2. hold: the tactical map stays for HOLD seconds after the last threat,
   so a fight does not flicker in and out of view.
3. look: arriving in a zone, arriving where a walk was going, or F5 shows
   a short look at eye level over the view underneath. It is only a look:
   any key closes it and acts in the view underneath.
4. intent: how you last moved in this zone decides between the map and
   the scene. Stepping tile by tile means the map; choosing a way (the
   way keys, or a walk) means the scene. Your own keys are the escape
   hatch, and they keep working until you leave the zone.
5. ground: until you move, safe and pocket ground with named places is a
   scene, and everywhere else is the map.

Escalation is immediate and calming is slow: the only automatic move to a
calmer view is the end of the hold. Ground only sets where a zone starts,
so walking along a boundary cannot flip the view back and forth.

Keys mean the same in every view (arrows step, Enter talks), so a view
change never changes what a key does. Every decision carries its rule and
a reason in plain words; the inspector (F10) and the trace show them.
"""

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from blacksite.door.present.screen import threats

HOLD = 5.0
LOOK_SECONDS = 4.0
TAGS = {"map": "MAP", "scene": "SCENE"}


@dataclass(frozen=True)
class Decision:
    view: str
    tag: str
    looking: bool
    rule: str
    why: str
    inputs: dict[str, Any] = field(default_factory=dict, compare=False)

    @property
    def shown(self) -> tuple[str, str, bool]:
        return self.view, self.tag, self.looking


@dataclass
class Context:
    threat_at: float = -1e9
    threat_why: str = ""
    look_until: float = 0.0
    look_why: str = ""
    walk_goal: list[int] | None = None
    moved: str | None = None
    sink: Callable[[float, Decision, Decision | None], None] | None = None
    last: Decision | None = None
    changes: deque[tuple[float, Decision]] = field(default_factory=lambda: deque(maxlen=12))

    def arrive(self, now: float, name: str) -> None:
        """A new zone: forget how you moved, and look at where you are."""
        self.moved = None
        self.look(now, why=f"you arrived in {name}" if name else "you arrived")

    def look(self, now: float, seconds: float = LOOK_SECONDS, why: str = "F5") -> None:
        if now - self.threat_at >= HOLD:
            self.look_until, self.look_why = now + seconds, why

    def intend(self, how: str) -> None:
        """`steps` or `ways`: the player's own choice of how to move."""
        self.moved = how

    def observe(self, body: dict[str, Any], now: float) -> None:
        """Note threats, walks and finished walks as views arrive."""
        self.danger(body, now)
        walking = body.get("me", {}).get("walking")
        if walking:
            self.moved = "ways"
        me = next((a for a in body.get("actors", []) if a.get("role") == "player_self"), None)
        if self.walk_goal and not walking and me and [me["x"], me["y"]] == list(self.walk_goal):
            self.look(now, 3.0, "you arrived where you walked")
        self.walk_goal = walking

    def danger(self, body: dict[str, Any], now: float) -> list[str]:
        found = threats(body)
        if found:
            self.threat_at, self.threat_why, self.look_until = now, ", ".join(found), 0.0
        return found

    def choose(self, body: dict[str, Any], now: float) -> Decision:
        decision = self.decide(body, now)
        if self.last is None or decision.shown != self.last.shown or decision.rule != self.last.rule:
            self.changes.append((now, decision))
            if self.sink:
                self.sink(now, decision, self.last)
        self.last = decision
        return decision

    def decide(self, body: dict[str, Any], now: float) -> Decision:
        found = self.danger(body, now)
        me, place = body.get("me", {}), body.get("place") or {}
        safety, places = me.get("safety", "?"), len(place.get("places") or [])
        inputs = {"zone": me.get("zone"), "safety": safety, "places": places, "moved": self.moved,
                  "threat": ", ".join(found) or None,
                  "threat_age": round(now - self.threat_at, 1) if self.threat_at > -1e8 else None,
                  "look_left": round(self.look_until - now, 1) if self.look_until > now else None}
        if found:
            return Decision("map", "TACTICAL", False, "danger", ", ".join(found), inputs)
        if now - self.threat_at < HOLD:
            left = HOLD - (now - self.threat_at)
            return Decision("map", "TACTICAL", False, "hold",
                            f"held {left:.1f} s more after {self.threat_why}", inputs)
        if not places:
            view, rule, why = "map", "ground", "no named places here"
        elif self.moved == "steps":
            view, rule, why = "map", "intent", "you are moving tile by tile"
        elif self.moved == "ways":
            view, rule, why = "scene", "intent", "you chose a way"
        elif safety in ("safe", "pocket"):
            view, rule, why = "scene", "ground", f"{safety} ground with {places} named places"
        else:
            view, rule, why = "map", "ground", f"{safety} ground"
        if self.look_until > now:
            return Decision(view, "LOOK", True, "look", f"{self.look_why}; then {why}", inputs)
        return Decision(view, TAGS[view], False, rule, why, inputs)
