"""UI 4: production relay cards and travel quotes at both terminal sizes."""

from dataclasses import asdict, replace

import pytest

from blacksite.door.model import Display
from blacksite.server.protocol import Frame, encode
from blacksite.server.relay_views import Panel
from tests.fake_terminal import FakeTerminal
from tests.server.test_relay_engine import content, relay_game
from tests.server.test_relay_passages import passage, passage_content
from tests.server.test_relay_benefits import owned


def render(info, size, content, body):
    display=Display(replace(info,width=size[0],height=size[1],color_depth='16'))
    display.receive(Frame('welcome',{'keymap':asdict(content.keymaps),'palette':asdict(content.palette)}),0)
    frame=Frame('view',{'rev':1,'kind':'menu','body':body})
    encode(frame)
    display.receive(frame,1)
    terminal=FakeTerminal(*size)
    terminal.write(display.render(1)[0])
    assert terminal.cell(size[0]-1,size[1]-1)==' '
    return terminal.screen_text()


@pytest.mark.parametrize('size',[(80,24),(132,50)])
@pytest.mark.parametrize('local',[False,True])
def test_ui_4_relay_cards_keep_actions_and_wide_claim_visible(info,relay_game,size,local):
    game,caller,runner,_=relay_game
    owner=game.core.relays
    owner.start(caller.session,'cold-chain')
    claim=next(iter(owner.claims.active.values()))
    owner.support(runner.session,claim.id)
    body=owner.views.body(caller.session,Panel('cold-chain' if local else ''))
    text=render(info,size,owner.content,body)
    assert 'Esc' in text and ('Cold Chain' in text or 'RELAYS' in text)
    if local:
        assert 'Holder界1' in text and 'Core opening' in text and 'hold' in text


@pytest.mark.parametrize('size',[(80,24),(132,50)])
def test_ui_4_passage_quote_keeps_price_and_free_alternative_visible(info,passage,size):
    game,caller,cable,_=passage
    owner=game.core.relays
    text=render(info,size,owner.content,owner.passages.body(caller.session,cable.id))
    assert '5 chits' in text and 'free stairs' in text and 'Esc/B' in text


@pytest.mark.parametrize('size',[(80,24),(132,50)])
def test_ui_4_owned_relay_defence_does_not_show_another_capture_countdown(info,relay_game,size):
    game,caller,_,_=relay_game
    owner=game.core.relays
    owned(game,'cold-chain')
    owner.start(caller.session,'cold-chain')
    claim=next(iter(owner.claims.active.values()))
    claim.elapsed=7000
    body=owner.views.body(caller.session,Panel('cold-chain'))
    text=render(info,size,owner.content,body)
    assert 'Defending' in text and '700s active' in text
    assert 'Core opening needed' not in text
    zone={'objects':[]}
    owner.views.decorate(caller.session,zone)
    assert zone['hint'].startswith('Defending') and '/480' not in zone['hint']
