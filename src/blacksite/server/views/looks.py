"""P6: caller-masked place records; charting never changes sight or memory."""

from dataclasses import asdict
from typing import Any
from collections.abc import Callable

from blacksite.content.loader import ContentTree
from blacksite.content import schema as s
from blacksite.content.places import DEFAULT_THEME, mark_cells, region_tiles, theme_over


def masked(content: ContentTree, zone: s.Zone, known: set[s.Tile],
           visible: set[s.Tile], *, known_at: Callable[[s.Tile], bool] | None = None,
           ground_only_at: Callable[[s.Tile], bool] | None = None) -> dict[str, Any] | None:
    look = content.looks.get(zone.id)
    themes = content.themes.themes if content.themes else {}
    if look is None or look.theme not in themes:
        return None
    base = theme_over(DEFAULT_THEME, themes[look.theme])
    whole_known = known_at if known_at is not None else known.__contains__
    def dressed(at: s.Tile) -> bool:
        return whole_known(at) and not (ground_only_at and ground_only_at(at))
    result: dict[str, Any] = {'theme': asdict(base), 'regions': [], 'signs': [],
                              'marks': [], 'glints': [], 'names': {}}
    for region in look.regions:
        cells = region_tiles(region)
        theme = themes[region.theme]
        disclosed = cells & known
        if not disclosed:
            continue
        if theme.pattern == 'rings':
            if all(whole_known(at) for at in cells):
                result['regions'].append({'theme': asdict(theme),
                    **({'rect': list(region.rect)} if region.rect else {'circle': list(region.circle)})})
            continue
        # Row runs reveal neither the undisclosed shape nor its centre.
        for y in sorted({y for x, y in disclosed}):
            xs = sorted(x for x, ty in disclosed if ty == y)
            start = end = xs[0]
            for x in [*xs[1:], None]:
                if x is not None and x == end + 1:
                    end = x
                    continue
                result['regions'].append({'theme': asdict(theme), 'rect': [start, y, end - start + 1, 1]})
                start = end = x
    for sign in look.signs:
        cells = {(sign.at[0] + i, sign.at[1]) for i in range(len(sign.text))}
        if cells & known and all(dressed(at) for at in cells):
            result['signs'].append(asdict(sign))
    for mark in look.marks:
        cells = mark_cells(mark)
        # Text is meaningful whole, like signs. A lane line is tile-local.
        if mark.at is not None:
            if any(at in known for at,ch in cells) and all(dressed(at) for at, ch in cells):
                result['marks'].append({'at': list(mark.at), 'text': mark.text, 'role': mark.role})
        else:
            result['marks'].extend({'at': list(at), 'text': ch, 'role': mark.role}
                                   for at, ch in cells if at in known and dressed(at))
    result['glints'] = [list(at) for at in look.glints if at in known and dressed(at)]
    if result['glints']:
        result['glint_role'] = look.glint_role
    visible_ids = {zone.tile_at(at) for at in visible & known}
    result['names'] = {tid: text for tid, text in look.names.items() if tid in visible_ids}
    # Ambient is intentionally not transmitted; its emission is P8.
    return result
