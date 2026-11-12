"""S11's tick budget in CI (owner, 2026-11-12).

A p99 at or above BLOCK_MS fails the check. A p99 at or above WARN_MS
posts a GitHub warning annotation and passes. S29a's bot run later
becomes the real gate against the architecture's 40 ms budget.
"""

from collections.abc import Callable

BLOCK_MS = 20.0
WARN_MS = 10.0


def verdict(p99_ms: float) -> str:
    """'block', 'warn' or 'pass' for one measured p99."""
    if p99_ms >= BLOCK_MS:
        return 'block'
    if p99_ms >= WARN_MS:
        return 'warn'
    return 'pass'


def enforce(p99_ms: float, label: str, emit: Callable[[str], None] = print) -> str:
    """Fail on a block, annotate a warning, and return the verdict."""
    result = verdict(p99_ms)
    if result == 'block':
        raise AssertionError(f'{label}: tick p99 {p99_ms:.3f} ms is at or over the '
                             f'{BLOCK_MS:g} ms limit')
    if result == 'warn':
        emit(f'::warning title=S11 tick budget::{label}: tick p99 {p99_ms:.3f} ms is at or over '
             f'{WARN_MS:g} ms (warning only; the check blocks at {BLOCK_MS:g} ms)')
    return result
