"""Game 7.7: actual travel, payment failure, prepaid recovery and free routes."""

from copy import deepcopy
from datetime import timedelta
from pathlib import Path

import pytest

from blacksite.content.loader import load_content
from blacksite.content.validate import validate
from blacksite.server.relay_passages import GATE_INTERVAL_SECONDS, GATE_OPEN_SECONDS, gate_departure
from scripts.relay_fixture import build_passage_fixture
from tests.character_helpers import create, place, state
from tests.harness import HeadlessServer
from tests.server.test_relay_benefits import owned


@pytest.fixture(scope='module')
def passage_content(tmp_path_factory):
    shipped=Path(__file__).parents[2]/'src/blacksite/content'
    local=tmp_path_factory.mktemp('s21-passage-content')
    routes=build_passage_fixture(shipped,local)
    tree=load_content(shipped,local)
    assert not validate(tree)
    return tree,routes


@pytest.fixture
def passage(passage_content):
    content,routes=passage_content
    game=HeadlessServer(deepcopy(content),character_state={})
    caller=game.connect({'user_id':1,'handle':'Travel界','node_name':'test'})
    create(game,caller,name='Passenger界',card='none')
    cable=next(e for e in game.core.world.zones['vatside-clinics'].template.meta.exits if e.id==routes[0])
    place(game,caller,'vatside-clinics',cable.tile)
    game.commit_commerce()
    return game,caller,cable,routes[1]


def test_game_7_7_gate_schedule_is_global_and_free():
    assert (GATE_INTERVAL_SECONDS, GATE_OPEN_SECONDS) == (120, 60)
    assert gate_departure(0)==0 and gate_departure(59.9)==59.9
    assert gate_departure(60)==120 and gate_departure(119.9)==120
    assert gate_departure(120)==120 and gate_departure(3720)==3720
    assert gate_departure(3780)==3840
    assert all(0 <= gate_departure(second/10)-second/10 <= 60
               for second in range(2*120*10))


def test_game_7_7_failed_fare_pays_nothing_then_one_receipt_covers_three_second_ride(passage):
    game,caller,cable,_=passage
    travel=game.core.relays.passages
    p=game.core.characters.players[caller.session.player_id]
    avatar=game.core.characters.sim.avatars[caller.session.user_id]
    quote=travel.quote(caller.session,cable)
    assert quote.cost==5
    assert travel.choose(caller.session,cable.id,quote.row,'f')
    assert p.chits_hand==200 and avatar.travel is None
    game.commit_commerce(error=True)
    assert p.chits_hand==200 and not p.progress.get('paid_passes') and avatar.travel is None
    travel.choose(caller.session,cable.id,quote.row,'f')
    effect=game.commit_commerce()[0]
    assert p.chits_hand==195 and p.progress['paid_passes'] and avatar.travel
    assert effect['player']['zone']=='vatside-clinics'
    game.step(29)
    assert avatar.zone=='vatside-clinics'
    game.step()
    game.commit_commerce()
    assert avatar.zone==cable.target_zone and not p.progress['paid_passes']
    assert p.chits_hand==195


def test_game_7_7_paid_pass_survives_server_restart_without_second_charge(passage,passage_content):
    game,caller,cable,_=passage
    travel=game.core.relays.passages
    quote=travel.quote(caller.session,cable)
    travel.choose(caller.session,cable.id,quote.row,'f')
    receipt=game.commit_commerce()[0]
    saved=state(game)
    # Simulate a stop after the fare receipt, before the departure checkpoint.
    saved['players']=[receipt['player']]
    restored=HeadlessServer(deepcopy(passage_content[0]),character_state=saved,clock=game.clock)
    returning=restored.connect({'user_id':1,'handle':'Travel界','node_name':'test'})
    restored.commit_commerce()
    p=restored.core.characters.players[returning.session.player_id]
    travel=restored.core.relays.passages
    quote=travel.quote(returning.session,cable)
    assert quote.cost==0 and quote.source=='prepaid' and p.chits_hand==195
    travel.choose(returning.session,cable.id,quote.row,'f')
    restored.step(30)
    restored.commit_commerce()
    assert p.chits_hand==195 and not p.progress['paid_passes']


@pytest.mark.parametrize('offline_seconds', [0, 4])
def test_game_7_7_saved_inflight_arrival_consumes_pass_after_restart(passage,passage_content,offline_seconds):
    game,caller,cable,_=passage
    travel=game.core.relays.passages
    travel.choose(caller.session,cable.id,travel.quote(caller.session,cable).row,'f')
    game.commit_commerce()
    saved=state(game)
    assert saved['players'][0]['progress']['travel']
    assert saved['players'][0]['progress']['paid_trip']
    game.clock.epoch+=timedelta(seconds=offline_seconds)
    restored=HeadlessServer(deepcopy(passage_content[0]),character_state=saved,clock=game.clock)
    returning=restored.connect({'user_id':1,'handle':'Travel界','node_name':'test'})
    restored.step(30)
    restored.commit_commerce()
    p=restored.core.characters.players[returning.session.player_id]
    assert p.zone==cable.target_zone and p.chits_hand==195
    assert not p.progress.get('paid_passes') and not p.progress.get('paid_trip')


def test_game_7_7_instant_fast_gate_persists_arrival_without_reusable_ticket(passage):
    game,caller,_,gate_id=passage
    zone=game.core.world.zones['terraces-blocks']
    gate=next(e for e in zone.template.meta.exits if e.id==gate_id)
    place(game,caller,zone.id,gate.tile)
    game.commit_commerce()
    travel=game.core.relays.passages
    travel.choose(caller.session,gate.id,travel.quote(caller.session,gate).row,'f')
    game.commit_commerce()
    p=game.core.characters.players[caller.session.player_id]
    assert p.zone==gate.target_zone and p.chits_hand==175
    assert not p.progress.get('paid_passes') and not p.progress.get('paid_trip')
    saved=[effect['player'] for effect in game.core.characters.outbox if effect['action']=='save']
    assert saved and all(row['zone']==gate.target_zone and not row['progress'].get('paid_passes') for row in saved)


def test_game_7_7_ordinary_gate_and_stairs_do_not_require_a_paid_pass(passage):
    game,caller,cable,gate_id=passage
    owner=game.core.relays
    p=game.core.characters.players[caller.session.player_id]
    travel=owner.passages
    travel.choose(caller.session,cable.id,travel.quote(caller.session,cable).row,'s')
    game.step(10)
    game.commit_commerce()
    assert p.chits_hand==200 and not p.progress.get('paid_passes')
    zone=game.core.world.zones['terraces-blocks']
    gate=next(e for e in zone.template.meta.exits if e.id==gate_id)
    place(game,caller,zone.id,gate.tile)
    game.commit_commerce()
    game.clock.epoch+=timedelta(seconds=(61-owner.now()%120)%120)
    travel.choose(caller.session,gate.id,travel.quote(caller.session,gate).row,'e')
    avatar=game.core.characters.sim.avatars[caller.session.user_id]
    assert avatar.travel.departure==gate_departure(owner.now()) and not avatar.travel.departed
    assert p.chits_hand==200


def test_game_7_7_ownership_quote_change_never_turns_free_choice_into_payment(passage):
    game,caller,cable,_=passage
    p=game.core.characters.players[caller.session.player_id]
    p.faction='halvard'
    owned(game,'cold-chain')
    travel=game.core.relays.passages
    quote=travel.quote(caller.session,cable)
    assert quote.cost==0 and quote.source=='member'
    owned(game,'cold-chain',None)
    assert not travel.choose(caller.session,cable.id,quote.row,'f')
    assert p.chits_hand==200 and not game.core.commerce.pending
