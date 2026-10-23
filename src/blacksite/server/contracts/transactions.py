"""Architecture 15.2: join a frozen contract draft to its owning source."""

from collections.abc import Callable
from copy import deepcopy
from typing import Any


def join_state(effect: dict[str, Any], state: dict[str, Any],
               install: Callable[[dict[str, Any]], None]) -> None:
    snapshot = deepcopy(state)
    effect['contracts_state'] = snapshot
    previous = effect.get('callback')

    def committed(success: bool) -> None:
        if success:
            install(deepcopy(snapshot))
        if previous:
            previous(success)

    effect['callback'] = committed
