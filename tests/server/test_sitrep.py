"""Social privacy from game design §11; real names in visible nearby."""

from blacksite.server.protocol import Frame
from tests.character_helpers import act
from tests.server.test_chat import social


def body(game,client):
    return game.core.characters.sim.external_views[client.session.id][1]


def test_lists_online_with_zone(social):
    game,a,b=social
    act(game,a,Frame('intent',{'name':'resync','args':{}}))
    zone=[f.data['body'] for f in game.frames_for(a)
          if f.type=='view' and f.data['kind']=='zone'][-1]
    assert zone['nearby'][0]['name']=='Beta'
    act(game,a,Frame('key',{'k':'W','t':0}))
    rows=body(game,a)['rows']
    assert {r['cells'][0] for r in rows}=={'Alpha','Beta'}
    assert rows[1]['cells']==['Beta','Second界','Freelance','Meridian Plaza','body']


def test_hidden_symmetric(social):
    game,a,b=social
    act(game,b,Frame('intent',{'name':'settings','args':{'sitrep_hidden':True}}))
    for caller in (a,b): act(game,caller,Frame('intent',{'name':'sitrep','args':{}}))
    assert body(game,a)['rows'][1]['cells'][3]=='hidden'
    assert all(r['cells'][3]=='hidden' for r in body(game,b)['rows'])
    assert 'Meridian Plaza' not in str(body(game,b))
    act(game,b,Frame('intent',{'name':'menu_select','args':{'key':'h'}}))
    assert all(r['cells'][3]=='Meridian Plaza' for r in body(game,b)['rows'])


def test_close_sitrep_restores_full_zone(social):
    game,a,b=social
    act(game,a,Frame('key',{'k':'w','t':0}))
    game.frames_for(a)
    act(game,a,Frame('intent',{'name':'menu_close','args':{}}))
    assert a.session.id not in game.core.chat.sitreps
    assert any(f.type=='view' and f.data['kind']=='zone' for f in game.frames_for(a))


def test_privacy_action_rejects_stale_or_duplicate_request(social):
    game,a,b=social
    act(game,a,Frame('key',{'k':'W','t':0}))
    frame=Frame('intent',{'name':'menu_select','args':{'key':'h'},'request_id':'one','expected_revision':a.session.view_revision})
    a.send(frame);a.send(frame);game.step()
    assert game.core.chat.settings(a.session)['sitrep_hidden'] is True
    a.send(frame);game.step()
    assert game.core.chat.settings(a.session)['sitrep_hidden'] is True
