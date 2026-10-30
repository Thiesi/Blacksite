"""Presentation groups for already selected E/J targets (terminal UI 11)."""

from collections.abc import Mapping


def focus_context(focus: Mapping[str, str] | None, jack: Mapping[str, str] | None,
                  jack_key: str = 'J') -> list[tuple[str, str]]:
    """Group aliases only when both keys have the same target and verb."""
    if focus and jack and focus['id'] == jack['id'] and focus['verb'] == jack['verb']:
        return [(f"E/{jack_key} {focus['verb']}", focus['label'])]
    return [(f"{key} {target['verb']}", target['label'])
            for key, target in (('E', focus), (jack_key, jack)) if target]
