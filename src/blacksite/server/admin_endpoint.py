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
             lattice_reveal: Callable[[str, str, str], dict[str, bool]] = lambda p, s, c: {"ok": False},
             relay_command: Callable[[str, dict[str, Any], Callable[[Any], None]], None] | None = None,
             market_command: Callable[[str, dict[str, Any], Callable[[Any], None]], None] | None = None,
             event_command: Callable[[str, dict[str, Any], Callable[[Any], None]], None] | None = None) -> None:
    if session.role != "operator":
        session.send(Frame("bye", {"reason": "forbidden", "text": "Operator credential required."}))
        return
    def reply(result: Any) -> None:
        target = ({key: frame.data[key] for key in ("player", "sector", "cell")}
                  if frame.type == 'admin.lattice.reveal' else
                  {key: frame.data[key] for key in ('relay', 'faction')} if frame.type == 'admin.relay.set' else
                  {key: frame.data[key] for key in ('listing', 'bounty') if key in frame.data}
                  if frame.type in ('admin.market.cancel', 'admin.bounty.refund') else
                  {key: frame.data[key] for key in ('event', 'where', 'plan') if key in frame.data}
                  if frame.type.startswith('admin.event.') else None)
        audit({"operator": session.user_id, "command": frame.type, "target": target,
               "outcome": "unavailable" if isinstance(result, dict) and result.get("ok") is False else "ok"})
        if session.closed:
            return
        session.view_revision += 1
        session.publish_view(Frame("view", {"rev": session.view_revision, "kind": "text", "body": {
            "title": frame.type, "lines": [json.dumps(result, ensure_ascii=False)], "page": 1, "pages": 1}}),
            None, sessions.clock.now_tick())
        if frame.type == 'admin.stop':
            stop()
    if frame.type.startswith('admin.relay.'):
        if relay_command:
            relay_command(frame.type.removeprefix('admin.'), frame.data, reply)
        else:
            reply({'ok': False, 'error': 'Relay service is unavailable.'})
        return
    if frame.type.startswith('admin.event.'):
        if event_command:
            event_command(frame.type.removeprefix('admin.'), frame.data, reply)
        else:
            reply({'ok': False, 'error': 'Event service is unavailable.'})
        return
    if frame.type.startswith(('admin.market.', 'admin.bounty.')):
        if market_command:
            market_command(frame.type.removeprefix('admin.'), frame.data, reply)
        else:
            reply({'ok': False, 'error': 'Market service is unavailable.'})
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
    reply(result)
