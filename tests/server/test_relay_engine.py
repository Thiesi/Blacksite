"""Game 7.4: source transactions and explicit participation through Core."""

from pathlib import Path

import pytest

from blacksite.content.loader import load_content
from blacksite.server.protocol import Frame
from blacksite.server.storage.db import Storage
from tests.character_helpers import act, create, place
from tests.harness import HeadlessServer
from tests.lattice.test_engine import runners, intent, jack
from tests.lattice.test_interlock import control_room


@pytest.fixture(scope='module')
def content():
    return load_content(Path(__file__).parents[2]/'src/blacksite/content')


@pytest.fixture
def relay_game(content):
    game=HeadlessServer(content,character_state={})
    clients=[]
    for uid,tile in ((1,(31,18)),(2,(33,18)),(3,(32,19))):
        client=game.connect({'user_id':uid,'handle':f'Wide界{uid}','node_name':'test'})
        create(game,client,name=f'Holder界{uid}')
        player=game.core.characters.players[client.session.player_id]
        player.faction='halvard' if uid<3 else 'choir'
        game.core.factions.refresh(player)
        place(game,client,'vatside-clinics',tile)
        clients.append(client)
    game.commit_commerce()
    return game,*clients


def player(game,client):
    return game.core.characters.players[client.session.player_id]


def test_game_7_4_capture_durable_ownership_reward_and_failure_retry(relay_game,tmp_path):
    game,holder,runner,bystander=relay_game
    owner=game.core.relays
    before=[player(game,c).xp for c in (holder,runner,bystander)]
    owner.start(holder.session,'cold-chain')
    claim=next(iter(owner.claims.active.values()))
    owner.support(runner.session,claim.id)
    owner.control_committed(runner.session.player_id,'lat-relay-cold-chain','relay_open',claim.id)
    claim.elapsed=claim.required
    owner.capture(claim.id)
    assert owner.owner('cold-chain') is None and player(game,holder).xp==before[0]
    game.commit_commerce(error=True)
    assert owner.owner('cold-chain') is None and player(game,holder).xp==before[0]
    owner.capture(claim.id)
    effects=game.commit_commerce()
    assert owner.owner('cold-chain')=='halvard'
    assert game.core.lattice.interlock.owned('lat-relay-cold-chain')=='halvard'
    assert [player(game,c).xp-before[i] for i,c in enumerate((holder,runner,bystander))]==[100,100,0]
    assert player(game,holder).standing.get('halvard',0)-player(game,bystander).standing.get('halvard',0)==15
    store=Storage(tmp_path/'world.db',game.clock)
    try:
        for effect in effects:
            store.commerce_write(effect)
        saved=store.character_state()
        assert saved['relays']==owner.record()
        assert saved['interlock']['cores']['lat-relay-cold-chain']['owner_faction']=='halvard'
        assert {p['id']:p['xp'] for p in saved['players']}=={
            player(game,holder).id:player(game,holder).xp,
            player(game,runner).id:player(game,runner).xp}
    finally:
        store.close()


def test_game_7_4_old_claim_channel_cannot_credit_replacement(relay_game):
    game,holder,runner,_=relay_game
    owner=game.core.relays
    owner.start(holder.session,'cold-chain')
    first=next(iter(owner.claims.active.values()))
    owner.support(runner.session,first.id)
    captured_context=owner.claim_of(runner.session.player_id,'lat-relay-cold-chain','relay_open')
    owner.withdraw(holder.session.player_id)
    owner.start(holder.session,'cold-chain')
    second=next(iter(owner.claims.active.values()))
    owner.support(runner.session,second.id)
    owner.control_committed(runner.session.player_id,'lat-relay-cold-chain','relay_open',captured_context)
    assert not second.hacked and second.required==4800


def test_game_7_4_counter_rechecks_membership_and_committed_ownership(relay_game):
    game,holder,runner,opponent=relay_game
    owner=game.core.relays
    owner.start(holder.session,'cold-chain')
    claim=next(iter(owner.claims.active.values()))
    claim.elapsed=claim.required
    owner.capture(claim.id)
    game.commit_commerce()
    assert game.core.commerce.vendor(runner.session,'cold-chain-relay')[0].faction=='halvard'
    with pytest.raises(ValueError,match='current holder'):
        game.core.commerce.vendor(opponent.session,'cold-chain-relay')
    player(game,runner).faction=None
    with pytest.raises(ValueError,match='current holder'):
        game.core.commerce.vendor(runner.session,'cold-chain-relay')


def test_game_7_4_menu_escape_does_not_start_claim_and_stale_choice_refused(relay_game):
    game,holder,_,_=relay_game
    owner=game.core.relays
    act(game,holder,Frame('key',{'k':'e','t':0}))
    assert holder.session.id in owner.views.menus
    act(game,holder,Frame('intent',{'name':'menu_select','args':{'row':'status','key':'h'},
        'expected_revision':holder.session.view_revision+1,'request_id':'stale-hold'}))
    assert not owner.claims.active
    act(game,holder,Frame('intent',{'name':'menu_close','args':{}}))
    assert holder.session.id not in owner.views.menus and not owner.claims.active


def test_game_7_4_verified_runner_disconnect_keeps_credit_holder_disconnect_aborts(relay_game):
    game,holder,runner,_=relay_game
    owner=game.core.relays
    owner.start(holder.session,'cold-chain')
    claim=next(iter(owner.claims.active.values()))
    owner.support(runner.session,claim.id)
    owner.control_committed(runner.session.player_id,'lat-relay-cold-chain','relay_open',claim.id)
    owner.disconnect(runner.session.player_id)
    assert runner.session.player_id in claim.hacked
    assert runner.session.player_id in claim.supporters
    owner.withdraw(runner.session.player_id)
    assert claim.required==1800 and len(claim.participants())==1
    owner.disconnect(holder.session.player_id)
    assert not owner.claims.active


def test_game_7_4_claim_card_uses_wide_holder_name_and_actual_progress(relay_game):
    game,holder,runner,_=relay_game
    owner=game.core.relays
    owner.start(holder.session,'cold-chain')
    act(game,runner,Frame('key',{'k':'e','t':0}))
    panel=owner.views.menus[runner.session.id]
    body=owner.views.body(runner.session,panel)
    assert body['rows'][1]['cells'][0]==player(game,holder).name
    assert body['rows'][1]['cells'][2].endswith('/480s')
    assert float(body['rows'][1]['cells'][2].split('/')[0])>0


def test_game_3_5_hold_xp_is_paid_once_with_live_health_not_stale_player_snapshot(relay_game):
    game,holder,_,_=relay_game
    owner=game.core.relays
    owner.start(holder.session,'cold-chain')
    claim=next(iter(owner.claims.active.values()))
    claim.elapsed=6000
    p=player(game,holder)
    p.xp=295
    actor=game.core.world.actors[p.id]
    actor.health=40
    before_max=actor.health_max
    assert owner.hold_xp()
    game.commit_commerce()
    assert p.xp==305 and p.grade==2
    assert actor.health<=41*actor.health_max/before_max
    assert not owner.hold_xp()


@pytest.mark.parametrize('replace_claim,fail_save',[(False,False),(False,True),(True,False)])
def test_game_7_4_real_control_channel_binds_original_claim_and_waits_for_commit(runners,replace_claim,fail_save):
    game,holder,runner,_=runners
    owner=game.core.relays
    p=player(game,holder)
    p.faction='halvard'
    game.core.factions.refresh(p)
    place(game,holder,'vatside-clinics',(31,18))
    place(game,runner,'vatside-clinics',(33,18))
    owner.start(holder.session,'cold-chain')
    first=next(iter(owner.claims.active.values()))
    owner.support(runner.session,first.id)
    place(game,runner,'core-plaza',(30,5))
    presence=jack(game,runner)
    # Isolate the source channel from S13 route traversal. The entrance is
    # an actual shipped sector/cell, not an alias in production content.
    sector,cell=next((sector.id,cell.id) for sector in game.core.lattice.sectors.records.values()
        for cell in sector.cells if cell.core_id=='lat-relay-cold-chain')
    presence.sector,presence.cell=sector,cell
    intent(game,runner,'lat.enter',core='lat-relay-cold-chain')
    control_room(game,presence,'relay_open')  # Explicit isolated ICE fixture.
    intent(game,runner,'lat.flip',control='relay_open')
    procedure=presence.procedure
    assert procedure.relay_claim==first.id
    if replace_claim:
        owner.withdraw(holder.session.player_id)
        owner.start(holder.session,'cold-chain')
        current=next(iter(owner.claims.active.values()))
        # The runner is still in the core, so retain the original accepted
        # participant as a labelled fixture for the replacement-race test.
        owner.claims.support(current.id,owner.participant(player(game,runner)))
    else:
        current=first
    game.step(procedure.until-game.clock.now_tick())
    assert game.core.commerce.pending and not current.hacked
    game.commit_commerce(error=fail_save)
    assert bool(current.hacked)==(not replace_claim and not fail_save)
