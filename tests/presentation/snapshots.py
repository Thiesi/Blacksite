"""Semantic glyph/style snapshots, strict CP437 diagnostics and packets."""

from dataclasses import asdict
import json
from pathlib import Path
from typing import Any, Iterable

from blacksite.content.cp437 import round_trips
from tests.ansi_style import Rendition
from tests.fake_terminal import FakeTerminal

TIERS = ('16', '256', 'truecolor')
GLYPH_TIERS = ('cp437',)  # V2 adds modern here when its shipped path exists.


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))+'\n'


def runs(values: Iterable[int]) -> list[list[int]]:
    result: list[list[int]] = []
    for value in values:
        if result and result[-1][1] == value:
            result[-1][0] += 1
        else:
            result.append([1, value])
    return result


def snapshot(terminal: FakeTerminal) -> dict[str, Any]:
    styles = {terminal.renditions.get((x, y), Rendition())
        for y in range(terminal.height) for x in range(terminal.width)}
    ordered = sorted(styles, key=lambda style: canonical(asdict(style)))
    indexes = {style: n for n, style in enumerate(ordered)}
    return {'schema': 1, 'width': terminal.width, 'height': terminal.height,
        'glyph_rows': terminal.screen_text().split('\n'),
        'styles': [asdict(style) for style in ordered],
        'style_rows': [runs(indexes[terminal.renditions.get((x, y), Rendition())]
                            for x in range(terminal.width)) for y in range(terminal.height)]}


def cp437_problems(terminal: FakeTerminal) -> list[dict[str, Any]]:
    """Inspect every cell, including caller text. Never silently exempt it."""
    return [{'x': x, 'y': y, 'glyph': glyph,
             'codepoints': [f'U+{ord(ch):04X}' for ch in glyph if not round_trips(ch)]}
        for y, row in enumerate(terminal.grid) for x, glyph in enumerate(row)
        if any(not round_trips(ch) for ch in glyph)]


def write_packet(directory: Path, terminal: FakeTerminal, context: dict[str, Any]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    if any(directory.iterdir()):
        raise FileExistsError(f'packet scenario directory must be empty: {directory}')
    replay = FakeTerminal(terminal.width, terminal.height)
    frames = []
    problems = []
    for index, raw in enumerate(terminal.frames):
        replay.write(raw)
        stem = f'{index:04}'
        (directory/(stem+'.ans')).write_bytes(raw)
        (directory/(stem+'.txt')).write_text(replay.screen_text()+'\n', encoding='utf-8', newline='\n')
        body = {**context, 'frame': index, 'base_frame': index-1 if index else None,
                'snapshot': snapshot(replay), 'cp437_problems': cp437_problems(replay)}
        problems.extend({'frame': index, **problem} for problem in body['cp437_problems'])
        (directory/(stem+'.json')).write_text(canonical(body), encoding='utf-8', newline='\n')
        frames.append(stem)
    (directory/'context.json').write_text(canonical({**context, 'frames': frames,
        'ansi': 'ordered byte-preserved frames; replay from 0000 for deltas',
        'cp437_pass': not problems,
        'cp437_problems': problems}), encoding='utf-8', newline='\n')


def assert_golden(root: Path, name: str, terminal: FakeTerminal, tier: str, *,
                  update: bool = False, trim: bool = False, glyph_tier: str = 'cp437',
                  packet: Path | None = None) -> None:
    if tier not in TIERS or glyph_tier not in GLYPH_TIERS:
        raise ValueError('unimplemented golden colour/glyph tier')
    text = terminal.screen_text()
    if trim:
        text = '\n'.join(row.rstrip() for row in text.splitlines())
    path = root/(name+'.txt')
    style_path = root/'styles'/glyph_tier/tier/(name+'.json')
    actual = canonical(snapshot(terminal))
    if update:
        style_path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text+'\n', encoding='utf-8', newline='\n')
        style_path.write_text(actual, encoding='utf-8', newline='\n')
    if packet:
        write_packet(packet/glyph_tier/tier/name, terminal,
                     {'scenario': name, 'colour_tier': tier, 'glyph_tier': glyph_tier})
    assert path.read_text(encoding='utf-8') == text+'\n', f'glyph golden differs: {path}'
    assert style_path.is_file(), f'missing style golden: {style_path}; run --update-goldens'
    assert style_path.read_text(encoding='utf-8') == actual, f'style golden differs: {style_path}'
