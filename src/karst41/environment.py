"""Operator environment names and the temporary pre-R1 aliases."""

from collections.abc import Mapping
from functools import cache
import logging


@cache
def _legacy_notice() -> None:
    # Operator entry points get one visible warning. The door installs no
    # terminal logging handler; its diagnostics remain out of game output.
    logging.getLogger(__name__).warning(
        'Deprecated BLACKSITE configuration used; use KARST41 names. '
        'Legacy aliases will be removed in S31.')


def setting(environment: Mapping[str, str], names: tuple[str, ...],
            default: str | None = None) -> str | None:
    """Prefer every new spelling before the corresponding old spellings.

    Names within each generation retain their declared priority. An empty
    value is set, so it does not fall through to an old configuration.
    """
    for name in names:
        if name in environment:
            return environment[name]
    # Remove in S31.
    for name in names:
        old = name.replace('KARST41', 'BLACKSITE', 1)
        if old in environment:
            _legacy_notice()
            return environment[old]
    return default
