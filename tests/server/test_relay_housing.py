"""Game 7.7/8.7: real rental receipts, historical quotes and private ICE."""

from datetime import timedelta

from tests.test_apartments import housing, housing_content, rent, player
from tests.server.test_relay_benefits import owned


def test_game_7_7_block_adds_one_tripwire_preserves_damage_tier_and_theft_receipt(housing):
    game,caller,_=housing
    apartments,record,_=rent(game,caller)
    p=player(game,caller)
    p.faction='halvard'
    game.core.factions.refresh(p)
    cid=apartments.private.core_id(record)
    encounters=game.core.lattice.encounters
    instance=encounters.spawn(cid,cid)
    encounters.instances[instance.id]=instance
    original=dict(instance.ice)
    next(iter(original.values())).integrity=0
    record['last_hacked_at']=123.0
    owned(game,'block')
    assert instance.graph.spec.tier==record['tier']==1
    assert len(instance.ice)==len(original)+1
    assert next(iter(original.values())).integrity==0
    assert apartments.state['apartments'][record['id']]['last_hacked_at']==123.0
    p.faction=None
    game.core.factions.refresh(p)
    assert set(instance.ice)==set(original)
    assert next(iter(instance.ice.values())).integrity==0
    assert apartments.state['apartments'][record['id']]['last_hacked_at']==123.0


def test_game_7_7_membership_waits_for_discount_invoice_then_allows_unpaid_leave(housing):
    game,caller,_=housing
    apartments,record,_=rent(game,caller)
    p=player(game,caller)
    p.faction='halvard'
    game.core.factions.refresh(p)
    owned(game,'block')
    p.chits_bank=p.chits_hand=0
    game.clock.epoch+=timedelta(days=7)
    avatar=game.core.characters.sim.avatars[caller.session.user_id]
    game.core.world.enter(avatar.actor,'vatside-wake-hall',(8,10))
    game.frames_for(caller)
    game.core.factions.propose(caller.session,'recruiter-cards','leave','halvard')
    assert p.faction=='halvard' and game.core.commerce.pending
    assert any('due rent quote' in row['text'] for frame in game.frames_for(caller)
               if frame.type=='log' for row in frame.data['lines'])
    for _ in range(5):
        game.commit_commerce()
        game.step()
        if p.faction is None:
            break
    assert p.faction is None
    assert apartments.lease(p)['invoice']['amount']==270
    assert p.chits_bank==p.chits_hand==0
    assert game.core.apartments.rent_modifier(p,record['rent_paid_until'])==1
