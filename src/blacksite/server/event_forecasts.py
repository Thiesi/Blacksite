"""Game 12: bounded personal forecast receipts, independent of hot history."""

from typing import Any

from blacksite.server.rules.events import HELD_FORECASTS


def remember(progress: dict[str, Any], pid: str, record: dict[str, Any], now: float) -> None:
    known = progress.setdefault('event_forecasts', {})
    known[pid] = {**record, 'read_at': now}
    older = sorted((key for key in known if key != pid),
        key=lambda key: (known[key].get('read_at', 0), key))
    for key in older[:max(0, len(known)-HELD_FORECASTS)]:
        del known[key]
