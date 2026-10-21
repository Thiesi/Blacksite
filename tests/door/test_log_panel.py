"""Terminal UI §2/§5/§6: coloured wrapping, scrollback and prompt isolation."""

from dataclasses import asdict, replace

import pytest

from blacksite.content.loader import load_content
from blacksite.door.cells import display_width
from blacksite.door.log import rows
from blacksite.door.model import Display
from blacksite.server.protocol import Frame
from tests.fake_terminal import FakeTerminal


def test_wrap_by_display_width():
    result=rows([{'channel':'say','text':'界'*100,'role':'chan_say'}],78)
    assert len(result)==3
    assert all(display_width(row['text'])<=78 for row in result)
    assert ''.join(row['text'] for row in result).count('界')==100
    assert all(row['role']=='chan_say' for row in result)


@pytest.mark.parametrize('width,height',[(80,24),(132,50)])
@pytest.mark.parametrize('tier',['16','256','truecolor'])
def test_channel_prefix_colours(info,repo_root,width,height,tier):
    content=load_content(repo_root/'src/blacksite/content')
    model=Display(replace(info,width=width,height=height,color_depth=tier))
    model.receive(Frame('welcome',{'proto':1,'server_version':'test','player':None,'keymap':{},'palette':asdict(content.palette),'motd':''}),0)
    messages=[{'channel':channel,'role':role,'text':'Wide界: hello','at':'now'} for channel,role in
              [('system','chan_sys'),('faction','chan_faction'),('whisper','chan_whisper')]]
    model.receive(Frame('log',{'lines':messages}),0)
    term=FakeTerminal(width,height);term.write(model.render(0)[0])
    screen=term.screen_text()
    assert '[sys]' in screen and '[fac]' in screen and '[whisper]' in screen and 'Wide界' in screen
    cell=model.previous.cells[model.layout.log.y+2][model.layout.log.x]
    assert cell.style==model.palette.style('chan_whisper')
    assert term.cell(width-1,height-1)==' '  # Replay rejects autowrap writes.


def test_scrollback_paging(info):
    model=Display(info)
    model.connected=True
    for i in range(550):
        model.receive(Frame('log',{'lines':[{'id':str(i),'channel':'system','text':f'line {i}','role':'chan_sys'}]}),0)
    assert len(model.logs)==500 and model.logs[0]['text']=='line 50'
    model.receive(Frame('log',{'lines':[dict(model.logs[-1])],'replay':True}),0)
    assert len(model.logs)==500
    model.key('ctrl-p',1)
    assert model.local['title']=='SCROLLBACK'
    model.key('pagedown',2)
    assert model.local_page==1
    model.resize(replace(info,width=132,height=50))
    assert model.local_page==0
    term=FakeTerminal(132,50);term.write(model.render(3)[0])
    assert 'Page 1/' in term.screen_text()
    model.key('escape',4)
    assert model.local is None


def test_prompt_swallows_movement_keys(info):
    model=Display(info);model.connected=True
    model.receive(Frame('prompt',{'id':'chat:1','label':'Say','kind':'line','max_len':200}),0)
    assert model.key('up',1)==[]
    assert model.key('h',1)==[] and model.key('j',1)==[]
    model.key('界',1)
    result=model.key('enter',2)
    assert result==[Frame('line',{'id':'chat:1','text':'hj界'})]
    model.receive(Frame('prompt',{'id':'chat:2','label':'Say','kind':'line','max_len':200}),3)
    assert model.key('escape',4)==[Frame('intent',{'name':'prompt_cancel','args':{'id':'chat:2'}})]
