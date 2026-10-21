"""Small operator endpoint; output uses the existing text view contract."""

import json
from collections.abc import Callable
from typing import Any

from blacksite.server.protocol import Frame
from blacksite.server.clock import TICK_HZ
from blacksite.server.sessions import Session, Sessions


def dispatch(session: Session, frame: Frame, sessions: Sessions,
             status: Callable[[], dict[str, Any]], stop: Callable[[], None],
             audit: Callable[[dict[str, Any]], None]) -> None:
    if session.role != "operator":
        session.send(Frame("bye", {"reason": "forbidden", "text": "Operator credential required."}))
        return
    if frame.type == "admin.who":
        result = [{"handle": s.door_info["handle"], "player_name": None, "zone": s.subscribed,
                   "connected_s": max(0, sessions.clock.now_tick() - s.connected_tick) / TICK_HZ}
                  for s in sessions.active.values() if not s.closed and s.role == "caller"]
    else:
        result = status() if frame.type == "admin.status" else {"ok": True}
    audit({"operator": session.user_id, "command": frame.type, "target": None, "outcome": "ok"})
    session.view_revision += 1
    session.publish_view(Frame("view", {"rev": session.view_revision, "kind": "text", "body": {
        "title": frame.type, "lines": [json.dumps(result, ensure_ascii=False)], "page": 1, "pages": 1}}),
        None, sessions.clock.now_tick())
    if frame.type == "admin.stop":
        stop()
