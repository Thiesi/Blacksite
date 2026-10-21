"""Small operator endpoint; output uses the existing text view contract."""

import json
from collections.abc import Callable
from typing import Any

from blacksite.server.protocol import Frame
from blacksite.server.clock import TICK_HZ
from blacksite.server.sessions import Session, Sessions


def dispatch(session: Session, frame: Frame, sessions: Sessions,
             status: Callable[[], dict[str, Any]], stop: Callable[[], None],
             audit: Callable[[dict[str, Any]], None],
             lattice_who: Callable[[], list[dict[str, str]]] = lambda: [],
             lattice_reveal: Callable[[str, str, str], dict[str, bool]] = lambda p, s, c: {"ok": False}) -> None:
    if session.role != "operator":
        session.send(Frame("bye", {"reason": "forbidden", "text": "Operator credential required."}))
        return
    if frame.type == "admin.lattice.reveal":
        result = lattice_reveal(frame.data["player"], frame.data["sector"], frame.data["cell"])
    elif frame.type == "admin.lattice.who":
        result = lattice_who()
    elif frame.type == "admin.who":
        result = [{"handle": s.door_info["handle"], "player_name": s.player_name, "zone": s.subscribed,
                   "connected_s": max(0, sessions.clock.now_tick() - s.connected_tick) / TICK_HZ}
                  for s in sessions.active.values() if not s.closed and s.role == "caller"]
    else:
        result = status() if frame.type == "admin.status" else {"ok": True}
    audit({"operator": session.user_id, "command": frame.type,
           "target": {key: frame.data[key] for key in ("player", "sector", "cell")} if frame.type == "admin.lattice.reveal" else None,
           "outcome": "unavailable" if isinstance(result, dict) and result.get("ok") is False else "ok"})
    session.view_revision += 1
    session.publish_view(Frame("view", {"rev": session.view_revision, "kind": "text", "body": {
        "title": frame.type, "lines": [json.dumps(result, ensure_ascii=False)], "page": 1, "pages": 1}}),
        None, sessions.clock.now_tick())
    if frame.type == "admin.stop":
        stop()
