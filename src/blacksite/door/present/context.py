"""Auto view: the door chooses the view from context (paradigm prototype C).

Rules, in order:

1. Anything threatening (a hazard, a target, a hostile, combat, heat)
   shows the tactical map, and keeps it for HOLD seconds after the last
   threat so the screen does not flicker in and out of a fight.
2. Arriving in a zone, arriving where a walk was going, or F5 shows a
   short look at eye level (street view, facing the most open way, so it
   looks into the place rather than at a wall). It is
   only a look: any key closes it and acts in the view underneath.
3. Safe and pocket ground with named places is a scene: you move by
   choosing where to go.
4. Everywhere else, contested and open ground, is the map: positioning
   matters there, so you move tile by tile.

The chosen view only changes presentation and the meaning of the arrow
keys; the server sees ordinary moves and trial walks either way. A tag in
the header always names the view and why.
"""

from dataclasses import dataclass
from typing import Any

from blacksite.door.present.screen import threatened

HOLD = 5.0
LOOK_SECONDS = 4.0
TAGS = {"map": "MAP", "scene": "SCENE"}


@dataclass
class Context:
    threat_at: float = -1e9
    look_until: float = 0.0
    walk_goal: list[int] | None = None

    def look(self, now: float, seconds: float = LOOK_SECONDS) -> None:
        if now - self.threat_at >= HOLD:
            self.look_until = now + seconds

    def observe(self, body: dict[str, Any], now: float) -> None:
        """Note threats and finished walks as views arrive."""
        if threatened(body):
            self.threat_at, self.look_until = now, 0.0
        walking = body.get("me", {}).get("walking")
        me = next((a for a in body.get("actors", []) if a.get("role") == "player_self"), None)
        if self.walk_goal and not walking and me and [me["x"], me["y"]] == list(self.walk_goal):
            self.look(now, 3.0)  # you have arrived: look at where you are
        self.walk_goal = walking

    def choose(self, body: dict[str, Any], now: float) -> tuple[str, str, bool]:
        """(base view, header tag, whether a look is showing over it)."""
        if threatened(body):
            self.threat_at, self.look_until = now, 0.0
        if now - self.threat_at < HOLD:
            return "map", "TACTICAL", False
        place = body.get("place") or {}
        calm = body.get("me", {}).get("safety") in ("safe", "pocket") and bool(place.get("places"))
        base = "scene" if calm else "map"
        if self.look_until > now:
            return base, "LOOK", True
        return base, TAGS[base], False
