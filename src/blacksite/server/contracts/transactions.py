"""Architecture 15.2: join a frozen contract draft to its owning source."""

from collections.abc import Callable
from copy import deepcopy
from typing import Any


def join_state(effect: dict[str, Any], state: dict[str, Any],
               install: Callable[[dict[str, Any]], None]) -> None:
    # A lift can update both its job and journal. Later facts fork the
    # effect's staged record, and replace that record without adding an
    # older installer that could overwrite the final committed state.
    effect['contracts_state'] = deepcopy(state)
    if effect.get('_contracts_joined'):
        return
    effect['_contracts_joined'] = True
    previous = effect.get('callback')

    def committed(success: bool) -> None:
        if success:
            install(deepcopy(effect['contracts_state']))
        if previous:
            previous(success)

    effect['callback'] = committed
