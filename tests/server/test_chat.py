"""Game design §11/§14: deterministic audience, privacy and chat limits."""

from pathlib import Path
import json

import pytest

from blacksite.content.loader import load_content
from blacksite.server.chat import CHAT_COLUMNS, SAY_RADIUS, LOG_LINE_BYTES, sanitize
from blacksite.server.clock import ManualClock
from blacksite.server.logging import Logs
from blacksite.server.protocol import Frame, encode
from blacksite.server.sessions import CHAT_PER_WINDOW, CHAT_WINDOW_SECONDS, LOG_RING_LINES, LOG_REPLAY_LINES
from blacksite.server.storage.db import Storage
from tests.character_helpers import act, create, place, state
from tests.harness import HeadlessServer


@pytest.fixture
def social(repo_root: Path):
    game=HeadlessServer(load_content(repo_root/'src/blacksite/content'),character_state={})
    a=game.connect({'user_id':1,'handle':'First界','node_name':'test'})
    create(game,a,name='Alpha')
    b=game.connect({'user_id':2,'handle':'Second界','node_name':'test'})
    create(game,b,name='Beta')
    place(game,a,'core-plaza',(10,5));place(game,b,'core-plaza',(15,5))
    game.frames_for(a);game.frames_for(b)
    return game,a,b


def send(game,client,**args):
    act(game,client,Frame('intent',{'name':'chat','args':{'channel':'say',**args}}))


def lines(game,client):
    frames=game.frames_for(client)
    for frame in frames: encode(frame)
    return [line for f in frames if f.type=='log' for line in f.data['lines']]


def test_say_radius_20(social):
    game,a,b=social
    assert SAY_RADIUS==20
    place(game,b,'core-plaza',(30,5))
    send(game,a,text='edge')
    assert lines(game,b)[-1]['text']=='Alpha: edge'
    place(game,b,'core-plaza',(30,6))
    send(game,a,text='outside')
    assert not lines(game,b)


def test_shout_whole_zone(social):
    game,a,b=social
    place(game,b,'core-plaza',(80,30))
    send(game,a,channel='shout',text='hello')
    assert lines(game,b)[-1]['channel']=='shout'
    place(game,b,'sodium-row',(10,5))
    send(game,a,channel='shout',text='another zone')
    assert not lines(game,b)


def test_whisper_by_handle_or_name(social):
    game,a,b=social
    c=game.connect({'user_id':3,'handle':'Third','node_name':'test'})
    create(game,c,name='Gamma');game.frames_for(c)
    place(game,b,'sodium-row',(10,5))
    for target in ('bEtA','Second界'):
        send(game,a,channel='whisper',target=target,text='private')
        received=lines(game,b)
        assert received[-1]['text']=='Alpha (First界) -> Beta (Second界): private'
        assert lines(game,a)[-1]['channel']=='whisper'
        assert not lines(game,c)


def test_ambiguous_whisper_never_guesses(social):
    game,a,b=social
    c=game.connect({'user_id':3,'handle':'Beta','node_name':'test'})
    create(game,c,name='Gamma');game.frames_for(c)
    send(game,a,channel='whisper',target='Beta',text='secret')
    assert not lines(game,b) and not lines(game,c)
    assert any(f.type=='toast' and 'unique' in f.data['text'] for f in game.frames_for(a))


def test_rate_limit_4_per_5s_toast(social):
    game,a,b=social
    assert (CHAT_PER_WINDOW,CHAT_WINDOW_SECONDS)==(4,5)
    for i in range(6): a.send(Frame('intent',{'name':'chat','args':{'channel':'say','text':str(i)}}))
    game.step()
    frames=game.frames_for(a)
    assert sum(f.type=='log' for f in frames)==4
    assert sum(f.type=='toast' and 'four lines' in f.data['text'] for f in frames)==2
    assert len(lines(game,b))==4
    game.step(50)
    send(game,a,text='later')
    assert lines(game,b)[-1]['text']=='Alpha: later'


def test_ansi_stripped():
    assert sanitize('\x1b[31mred\x1b[0m\x1b]0;title\x07!')=='red!'
    assert sanitize('\x9b2Jhello\x9dtitle\x9c')=='hello'
    assert sanitize('a\x1bPpayload\x1b\\b')=='ab'


def test_control_chars_stripped():
    assert sanitize('a\n\r\t\x00\x7f\x85\u202eb')=='ab'
    assert sanitize('e\u0301')=='é'


def test_200_columns_cap_display_width():
    assert CHAT_COLUMNS==200
    assert sanitize('界'*200)=='界'*100
    assert len(sanitize('x'+'\u0300'*5000).encode())<=LOG_LINE_BYTES


def test_ignore_blocks_all_channels(social):
    game,a,b=social
    act(game,b,Frame('intent',{'name':'ignore','args':{'name':'Alpha'}}))
    game.frames_for(b)
    for channel in ('say','shout','whisper'):
        send(game,a,channel=channel,text='blocked',target='Beta')
    act(game,a,Frame('intent',{'name':'emote','args':{'id':'wave','target':'Beta'}}))
    assert not lines(game,b)
    saved=state(game)
    restored=HeadlessServer(game.core.world.content,character_state=saved,clock=game.clock)
    again=restored.connect({'user_id':2,'handle':'Second界','node_name':'test'})
    assert restored.core.chat.settings(again.session)['ignored']==[a.session.user_id]


def test_report_writes_row_and_audit(social,tmp_path):
    game,a,b=social
    act(game,a,Frame('intent',{'name':'report','args':{'name':'Beta','text':'unsafe\x1b[31m behavior'}}))
    assert not any(f.type=='toast' and f.data['text']=='Reported.' for f in game.frames_for(a))
    chat=game.core.chat
    effect=chat.outbox.pop()
    store=Storage(tmp_path/'world.db',game.clock)
    logs=Logs(tmp_path,game.clock)
    try:
        store.report(effect['row']);logs.audit(effect['row']);chat.committed(effect,True)
        row=json.loads(store.db.execute('SELECT data FROM reports').fetchone()[0])
        assert row['reporter']==a.session.player_id and row['target']==b.session.player_id
        assert row['reporter_user']==a.session.user_id and row['target_user']==b.session.user_id
        assert row['text']=='unsafe behavior'
        assert store.db.execute('SELECT count(*) FROM audit').fetchone()[0]==1
        assert json.loads((tmp_path/'audit.log').read_text(encoding='utf-8'))['action']=='report'
        assert any(f.type=='toast' and f.data['text']=='Reported.' for f in game.frames_for(a))
    finally: logs.close();store.close()


def test_failed_report_does_not_claim_success(social):
    game,a,b=social
    act(game,a,Frame('intent',{'name':'report','args':{'name':'Beta','text':'something'}}))
    game.core.chat.committed(game.core.chat.outbox.pop(),False)
    assert any(f.type=='toast' and 'could not be saved' in f.data['text'] for f in game.frames_for(a))


def test_offline_report_and_reversible_identity_ignore(social):
    game,a,b=social
    game.core.sessions.disconnect(a.session)
    act(game,b,Frame('intent',{'name':'report','args':{'name':'Alpha','text':'after logout'}}))
    assert game.core.chat.outbox[-1]['row']['target']==a.session.player_id
    act(game,b,Frame('intent',{'name':'ignore','args':{'name':'Alpha'}}))
    assert game.core.chat.settings(b.session)['ignored']==[a.session.user_id]
    act(game,b,Frame('intent',{'name':'ignore','args':{'name':'Alpha','enabled':False}}))
    assert game.core.chat.settings(b.session)['ignored']==[]


def test_ring_replays_50_on_reconnect(social):
    game,a,b=social
    assert (LOG_RING_LINES,LOG_REPLAY_LINES)==(500,50)
    for i in range(550):
        game.core.chat.emit(a.session,'system',str(i))
        game.frames_for(a)
    ring=a.session.log_ring
    assert len(ring)==500 and ring[0]['text']=='50'
    game.core.sessions.disconnect(a.session)
    again=game.connect({'user_id':1,'handle':'First界','node_name':'test'})
    # S25b arrival prose is itself a log-ring line. Reconnect emits it,
    # then replays the latest fifty lines with stable IDs for client
    # deduplication. The replay includes 49 system lines and that arrival.
    frames=game.frames_for(again)
    for frame in frames: encode(frame)
    replay=next(frame.data['lines'] for frame in frames if frame.type=='log' and frame.data.get('replay'))
    assert len(replay)==50 and replay[0]['text']=='501' and replay[-1]['channel']=='zone'
    assert [line['id'] for line in replay]==[line['id'] for line in list(again.session.log_ring)[-50:]]
    assert not a.session.log_ring
    act(game,again,Frame('intent',{'name':'resync','args':{}}))
    assert [line['id'] for line in lines(game,again)]==[line['id'] for line in replay]
    assert len(again.session.log_ring)==500


def test_fixed_and_free_form_emotes_share_chat_budget(social):
    game,a,b=social
    game.core.chat.command(a.session,'say','/me waves',game.clock.now_tick())
    assert lines(game,b)[-1]['text']=='Alpha waves'
    game.core.chat.command(a.session,'say','/wave Beta',game.clock.now_tick())
    assert lines(game,b)[-1]['text']=='Alpha waves at you.'
    assert lines(game,a)[-1]['text']=='You wave at Beta.'
    assert set(game.core.world.content.emotes)=={'wave','nod','shrug','salute','point','laugh','sigh','bow','glare','spit'}


def test_group_routing_uses_server_membership(social):
    game,a,b=social
    send(game,a,channel='faction',text='not a member',target='unmoored')
    assert not lines(game,b)
    game.core.characters.players[a.session.player_id].faction='unmoored'
    game.core.characters.players[b.session.player_id].faction='unmoored'
    send(game,a,channel='faction',text='members only')
    assert lines(game,b)[-1]['channel']=='faction'
    game.core.chat.crew_of=lambda s:'crew1'
    send(game,a,channel='crew',text='crew only')
    assert lines(game,b)[-1]['channel']=='crew'
    send(game,a,channel='system',text='forged notice')
    assert not lines(game,b)


def test_prompt_line_sanitization_and_forged_line(social):
    game,a,b=social
    act(game,a,Frame('key',{'k':'enter','t':0}))
    pid=a.session.pending_prompts['chat']['id']
    act(game,a,Frame('line',{'id':'wrong','text':'forged'}))
    assert not lines(game,b)
    act(game,a,Frame('line',{'id':pid,'text':'hello\x1b[2J'}))
    assert lines(game,b)[-1]['text']=='Alpha: hello'


def test_replay_budget_handles_quotes_wide_and_combining_text(social):
    game,a,b=social
    for _ in range(50):
        game.core.chat.emit(a.session,'system','"'*100+'界'*20+'x'+'\u0300'*600)
        game.frames_for(a)
    a.session.replay_log()
    replay=next(f for f in game.frames_for(a) if f.type=='log')
    assert len(replay.data['lines'])==50
    assert len(encode(replay))<65536


@pytest.mark.parametrize('channel',['whisper','crew','faction'])
def test_private_prompt_never_executes_public_commands(social,channel):
    game,a,b=social
    game.core.chat.command(a.session,channel,'/shout private text',game.clock.now_tick())
    assert not lines(game,b)
    assert not lines(game,a)
