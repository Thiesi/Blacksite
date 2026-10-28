"""Game 7.4: authenticated operator changes acknowledge the actual receipt."""

import json

import pytest

from blacksite.admin import __main__ as cli
from blacksite.server.protocol import Frame
from tests.harness import ADMIN_SECRET, hello
from tests.server.test_relay_engine import relay_game, content, player


@pytest.mark.parametrize('failure',[False,True])
def test_game_7_4_admin_acknowledges_commit_without_invented_capture_credit(relay_game,failure):
    game,_,_,_=relay_game
    op=game.connect(frame=hello({'user_id':'operator','handle':'SysOp','node_name':'test'},secret=ADMIN_SECRET))
    audits=[]
    game.core.audit=audits.append
    xp={pid:p.xp for pid,p in game.core.characters.players.items()}
    op.send(Frame('admin.relay.set',{'relay':'cold-chain','faction':'halvard'}))
    game.step()
    assert game.core.relays.owner('cold-chain') is None
    assert not any(f.type=='view' for f in game.frames_for(op))
    effects=game.commit_commerce(error=failure)
    result=json.loads(next(f for f in game.frames_for(op) if f.type=='view').data['body']['lines'][0])
    assert result['ok'] is not failure
    assert game.core.relays.owner('cold-chain')==(None if failure else 'halvard')
    assert xp=={pid:p.xp for pid,p in game.core.characters.players.items()}
    assert not game.core.relays.ledger.state['captures']
    assert audits[-1]['target']=={'relay':'cold-chain','faction':'halvard'}
    assert 'relays_state' in effects[0] and 'interlock_state' in effects[0]


def test_game_7_4_caller_cannot_use_admin_and_unknown_relay_is_rejected(relay_game):
    game,caller,_,_=relay_game
    caller.send(Frame('admin.relay.set',{'relay':'cold-chain','faction':'halvard'}))
    assert any(f.type=='bye' and f.data['reason']=='forbidden' for f in game.frames_for(caller))
    assert game.core.relays.owner('cold-chain') is None
    op=game.connect(frame=hello({'user_id':'operator','handle':'SysOp','node_name':'test'},secret=ADMIN_SECRET))
    op.send(Frame('admin.relay.set',{'relay':'missing-relay','faction':'halvard'}))
    game.step()
    result=json.loads(next(f for f in game.frames_for(op) if f.type=='view').data['body']['lines'][0])
    assert not result['ok'] and 'commissioned' in result['error']
    assert not game.core.commerce.pending


@pytest.mark.parametrize('prefix',[[],['admin']])
@pytest.mark.parametrize('ok',[False,True])
def test_game_7_4_cli_relay_set_uses_typed_ids_and_reports_server_failure(tmp_path,monkeypatch,capsys,prefix,ok):
    seen=[]
    async def request(install,command,data=None):
        seen.append((command,data))
        return {'ok':ok,'relay':'cold-chain','faction':'neutral'}
    monkeypatch.setattr(cli,'request',request)
    code=cli.main([*prefix,'relay','set','cold-chain','neutral','--install-dir',str(tmp_path),'--json'])
    assert code==int(not ok)
    assert seen==[('relay.set',{'relay':'cold-chain','faction':'neutral'})]
    assert json.loads(capsys.readouterr().out)['ok'] is ok
