"""Small operator endpoint; output uses the existing text view contract."""

import json
from collections.abc import Callable
from typing import Any

from blacksite.server.protocol import Frame
from blacksite.server.sessions import Session, Sessions


def dispatch(session: Session, frame: Frame, sessions: Sessions,
             status: Callable[[], dict[str, Any]], stop: Callable[[], None],
             audit: Callable[[dict[str, Any]], None]) -> None:
    if session.role != "operator":
        session.send(Frame("bye", {"reason": "forbidden", "text": "Operator credential required."}))
        return
    if frame.type == "admin.who":
        result = [{"session": s.id, "user_id": s.user_id, "player": s.player_id}
                  for s in sessions.active.values() if not s.closed and s.role == "caller"]
    else:
        result = status() if frame.type == "admin.status" else {"stopping": True}
    audit({"operator": session.user_id, "command": frame.type, "target": None, "outcome": "ok"})
    session.view_revision += 1
    session.publish_view(Frame("view", {"rev": session.view_revision, "kind": "text", "body": {
        "title": frame.type, "lines": [json.dumps(result, ensure_ascii=False)], "page": 1, "pages": 1}}),
        None, sessions.clock.now_tick())
    if frame.type == "admin.stop":
        stop()
