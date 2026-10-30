"""Test-only caller provenance by controlled, width-preserving rerender.

Only declared input at caller-owned model fields is substituted. Authored
text with identical characters or even the same full string is untouched.
The two renders differ precisely where that caller input reaches cells.
Production display code and emitted primary ANSI bytes are unchanged.
"""

from copy import deepcopy
from dataclasses import replace
from typing import Any, Callable

from blacksite.door.cells import cell_width
from blacksite.door.model import Display
from blacksite.server.protocol import Frame
from tests.harness import CALLER_INPUTS


class CallerFrame(bytes):
    caller_shadow: bytes
    caller_inputs: list[dict[str, str]]

    def __new__(cls, raw: bytes, shadow: bytes, inputs: list[dict[str, str]]) -> 'CallerFrame':
        obj = super().__new__(cls, raw)
        obj.caller_shadow, obj.caller_inputs = shadow, inputs
        return obj


def shadow_text(text: str) -> str:
    result = []
    for char in text:
        width = cell_width(char)
        if width == 2:
            result.append('\u8a9e' if char != '\u8a9e' else '\u754c')
        elif width == 0:
            result.append('\u0300' if char != '\u0300' else '\u0301')
        else:
            result.append('?' if char != '?' else '!')
    return ''.join(result)


def substitute(record: dict[str, Any], field: str, origin: str,
               sources: list[dict[str, str]]) -> None:
    value = record.get(field)
    declared = next((source for source in CALLER_INPUTS if source.text == value), None)
    if declared is not None:
        record[field] = shadow_text(declared.text)
        sources.append({'input': declared.id, 'origin': origin, 'text': declared.text})


def render_with_provenance(render: Callable[[Display, float], tuple[bytes, Frame | None]],
                           model: Display, now: float) -> tuple[bytes, Frame | None]:
    shadow = Display.__new__(Display)
    shadow.__dict__.update(deepcopy({key: value for key, value in vars(model).items()
                                    if not key.startswith('_caller_')}))
    shadow.previous = getattr(model, '_caller_previous', None)
    sources: list[dict[str, str]] = []
    raw = dict(shadow.info.raw)
    substitute(raw, 'handle', 'door_info.handle', sources)
    shadow.info = replace(shadow.info, raw=raw)
    kind, body = shadow.kind, shadow.body
    if kind == 'wake':
        kind, body = body.get('kind'), body.get('body', {})
    if kind == 'zone':
        for field in ('name', 'handle'):
            substitute(body.get('me', {}), field, f'zone.me.{field}', sources)
    elif kind == 'lattice':
        for index, peer in enumerate(body.get('presences', [])):
            substitute(peer, 'name', f'lattice.presences[{index}].name', sources)
    output, ack = render(model, now)
    shadow_output, _ = render(shadow, now)
    model._caller_previous = shadow.previous
    return CallerFrame(output, shadow_output, sources), ack
