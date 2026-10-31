"""A7 / UI 2: stable fitting zones and the existing server scroll margin."""

from dataclasses import replace
from pathlib import Path

import pytest

from blacksite.content.loader import ContentTree, load_content
from blacksite.door.present.zone import origin
from blacksite.layout import compute
from blacksite.server.views.zone_view import camera
from blacksite.server.world.actors import Actor
from blacksite.server.world.zone import ZoneInstance

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope='module')
def content() -> ContentTree:
    return load_content(ROOT/'src/blacksite/content')


@pytest.mark.parametrize('size', [(80,24),(132,50)])
@pytest.mark.parametrize('fit_x,fit_y', [(True,True),(True,False),(False,True),(False,False)])
def test_ui_2_origin_stays_still_and_large_axes_use_server_margin(
        content: ContentTree, size: tuple[int,int], fit_x: bool, fit_y: bool) -> None:
    layout = compute(*size)
    field = layout.viewport
    width = field.width-10 if fit_x else field.width+30
    height = field.height-6 if fit_y else field.height+20
    original = content.zones['core-plaza']
    template = replace(original,meta=replace(original.meta,objects=(),exits=(),spawners=(),pockets=()),
                       grid=tuple(tuple('floor' for _ in range(width))
                                                            for _ in range(height)))
    zone = ZoneInstance(template,content.tiles,7)
    actor = Actor('test:camera','Camera界',zone=zone.id,x=0,y=0)
    vp = None
    seen = [set(),set()]
    # Walk every cell along each axis, then back to both clamped edges.
    for axis,limit,fits in ((0,width,fit_x),(1,height,fit_y)):
        for position in (*range(limit),*range(limit-2,-1,-1)):
            if axis == 0:
                actor.x = position
            else:
                actor.y = position
            old = vp
            vp = camera(actor,zone,*size,vp)
            body = {'viewport':vp,'actors':[{'role':'player_self','x':actor.x,'y':actor.y}]}
            at = origin(body,layout)
            assert at == (field.x+(field.width-vp['w'])//2,field.y+(field.height-vp['h'])//2)
            assert field.x <= at[0]+actor.x-vp['x'] < field.right
            assert field.y <= at[1]+actor.y-vp['y'] < field.bottom
            for n,key in enumerate(('x','y')):
                seen[n].add(vp[key])
            key,span = ('x','w') if axis == 0 else ('y','h')
            if fits:
                assert vp[key] == 0
            elif old is not None and 4 <= position-old[key] < old[span]-4:
                assert vp[key] == old[key], 'must not scroll outside the four-tile edge margin'
            assert 0 <= vp[key] <= limit-vp[span]
        assert vp[key] == 0
        if not fits:
            assert max(seen[axis]) == limit-(field.width if axis == 0 else field.height)
    # Origin depends on disclosed dimensions, never the actor's position.
    body['actors'] = []
    assert origin(body,layout) == at
