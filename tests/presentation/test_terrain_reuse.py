"""A8 preserves UI 2 disclosure, neighbour edges and terminal bytes."""

from copy import deepcopy
from dataclasses import asdict
from pathlib import Path

import pytest

from blacksite.content.loader import load_content
from blacksite.door.cells import CellBuffer
from blacksite.door.palette import Palette
from blacksite.door.present import zone
from blacksite.door.present.paint import Paint
from blacksite.layout import compute
from tests.presentation.test_places import view


@pytest.fixture(scope='module')
def content():
    root = Path(__file__).resolve().parents[2]
    return load_content(root/'src/blacksite/content', root/'tests/fixtures/p6')


@pytest.mark.parametrize('tier', ['16', '256', 'truecolor'])
@pytest.mark.parametrize('size', [(80, 24), (132, 50)])
def test_ui_2_reused_rows_follow_in_place_disclosure_and_neighbour_changes(content, tier, size):
    body, *_ = view(content, *size)
    body['viewport'] = dict(x=0, y=0, w=5, h=5)
    body['legend'] = [dict(id='floor', glyph='·', role='floor', plain=True, wall=False),
                      dict(id='wall', glyph='█', role='wall', wall=True)]
    body['tiles'] = [[1]*5 for _ in range(5)]
    body['remembered'] = [[1]*5 for _ in range(5)]
    body['charted'] = [[-1]*5 for _ in range(5)]
    body['hazards'] = []
    palette = asdict(content.palette)
    cached = Paint(Palette(palette, tier))
    layout = compute(*size)
    previous = None
    for step in range(10):
        if step == 1:  # A floor in the next row exposes a formerly solid roof edge.
            body['tiles'][3][2] = 0
        elif step == 2:
            body['tiles'][3][2] = -2
            body['remembered'][3][2] = 0
        elif step == 3:
            body['tiles'][3][2] = -1
            body['remembered'][3][2] = -1
            body['charted'][3][2] = 0
        elif step == 4:
            body['charted'][3][2] = -1
        elif step == 5:
            body['tiles'][3][2] = 0
            body['hazards'] = [dict(tiles=[[2, 3]])]
        elif step == 6:
            body['hazards'].clear()
        elif step == 7:  # Index stays the same, but its rule shape changes.
            body['legend'][1] = dict(id='cover-1', glyph='=', role='thing_cover', wall=False)
        elif step == 8:
            body['looks'] = deepcopy(body['looks'])
            body['looks']['marks'] = [dict(at=[2, 3], text='X', role='thing_exit')]
        # Step 9 deliberately reuses unchanged terrain.
        buffers = []
        for paint in (cached, Paint(Palette(palette, tier))):
            buffer = CellBuffer(*size)
            zone.terrain(buffer, body, layout, paint)
            buffers.append(buffer)
        assert buffers[0].full() == buffers[1].full(), step
        assert buffers[0].diff(previous) == buffers[1].diff(previous), step
        previous = buffers[0]
    # Neither row snapshots nor subsequent painting mutate protocol data.
    saved = deepcopy(body)
    zone.terrain(CellBuffer(*size), body, layout, cached)
    assert body == saved
