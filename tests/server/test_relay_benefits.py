"""Game 7.7 consumers; future eligibility is an explicit unit fixture."""

from dataclasses import replace
from blacksite.content.schema import Behaviour
from blacksite.server.npcs.templates import make_actor

import pytest

from tests.server.test_relay_engine import relay_game, content, player
from tests.lattice.test_engine import runners, jack, intent


def owned(game, rid, faction='halvard', at=None):
    owner=game.core.relays
    draft=owner.ledger.fork()
    draft.set_owner(rid,faction,None,owner.now() if at is None else at,owner.rates())
    assert owner.write(draft,interlock=owner.ownership_patch(rid,faction))
    game.commit_commerce()


def test_game_7_7_clinic_fee_uses_strongest_service_factor_and_ends_with_owner(relay_game,monkeypatch):
    game,caller,_,other=relay_game
    p,q=player(game,caller),player(game,other)
    fee=game.core.progression.clinics.service_multiplier
    vendor=game.core.characters.content.vendors['sablier-clinic']
    owned(game,'cold-chain')
    assert fee(p,vendor)==.9 and fee(q,vendor)==1
    monkeypatch.setattr(game.core.contracts.effects,'fee',lambda player,vendor:.8)
    assert fee(p,vendor)==.8
    monkeypatch.setattr(game.core.contracts.effects,'fee',lambda player,vendor:1)
    owned(game,'cold-chain',None)
    assert fee(p,vendor)==1


def test_game_7_7_rent_uses_due_time_ownership_not_present_owner(relay_game):
    game,caller,_,_=relay_game
    p=player(game,caller)
    now=game.core.relays.now()
    owned(game,'block',at=now-100)
    assert game.core.apartments.rent_modifier(p,now-50)==.9
    owned(game,'block',None)
    assert game.core.apartments.rent_modifier(p,now-50)==.9
    assert game.core.apartments.rent_modifier(p,now)==1
    assert game.core.apartments.rent_modifier(p,now-101)==1


def test_game_7_7_future_eligibility_fixture_wires_quality_salvage_and_range(relay_game,monkeypatch):
    game,caller,_,_=relay_game
    owner,p=game.core.relays,player(game,caller)
    active=owner.active
    # Unit provider fixture only: no future map/core is activated or claimed
    # as geography proof. Bell's district is local for the range consumer.
    monkeypatch.setattr(owner,'active',lambda rid:rid in ('bell','yard','crash') or active(rid))
    bell=owner.content.relays['bell']
    monkeypatch.setitem(owner.content.relays,'bell',replace(bell,benefit=replace(bell.benefit,district='Vatside')))
    for rid in ('bell','yard','crash'):
        owned(game,rid)
    assert game.core.fabrication.quality_bonus(p,'oldworks-yards')==.05
    assert game.core.fabrication.quality_bonus(p,'vatside-clinics')==0
    assert game.core.salvage.crash_relay_bonus('scour-ring-3')
    assert not game.core.salvage.crash_relay_bonus('scour-ring-4')
    assert game.core.progression.modifiers(p).bonus('hymn_radius_bonus')==1
    for rid in ('bell','yard','crash'):
        owned(game,rid,None)
    assert game.core.fabrication.quality_bonus(p,'oldworks-yards')==0
    assert not game.core.salvage.crash_relay_bonus('scour-ring-3')
    assert game.core.progression.modifiers(p).bonus('hymn_radius_bonus')==0


def test_game_7_7_zero_discounts_actual_network_gain_not_fixed_costs_or_other_districts(runners,monkeypatch):
    game,caller,_,_=runners
    p=player(game,caller)
    p.faction='halvard'
    owner=game.core.relays
    active=owner.active
    monkeypatch.setattr(owner,'active',lambda rid:rid=='zero' or active(rid))
    presence=jack(game,caller)
    presence.cell=next(c.id for c in owner.lat.sectors.records[presence.sector].cells if c.core_id=='lat-civic-ledger')
    intent(game,caller,'lat.enter',core='lat-civic-ledger')
    owned(game,'zero')
    presence.sector=next(sid for sid,s in owner.lat.sectors.records.items() if s.district=='Old Works')
    presence.trace=0
    owner.lat.encounters.trace(presence,10)
    assert presence.trace==9
    owner.lat.encounters.trace(presence,10,fixed=True)
    assert presence.trace==19
    owned(game,'zero',None)
    owner.lat.encounters.trace(presence,10)
    assert presence.trace==29


def test_game_7_7_patrol_overlay_is_owned_local_and_does_not_reveal_unseen_tiles(relay_game,monkeypatch):
    game,caller,_,_=relay_game
    owner,p=game.core.relays,player(game,caller)
    relay=owner.content.relays['cold-chain']
    monkeypatch.setitem(owner.content.relays,'cold-chain',replace(relay,
        benefit=replace(relay.benefit,kind='patrol_overlay',amount=0)))
    template=replace(next(iter(owner.content.npcs.values())),id='fixture-patrol',name='Fixture patrol',training=False,
        behaviours=(Behaviour('patrol',{'waypoints':[[31,18],[32,18],[34,18]]}),))
    monkeypatch.setitem(owner.content.npcs,template.id,template)
    npc=make_actor(template,'fixture-patrol-body',{})
    owner.world.enter(npc,'vatside-clinics',(34,18))
    assert not owner.benefits.patrols(p)
    owned(game,'cold-chain')
    assert owner.benefits.patrols(p)
    body={'viewport':{'x':31,'y':18,'w':3,'h':1},'tiles':[[0,-1,0]],'objects':[]}
    owner.views.decorate(caller.session,body)
    route=next(r for r in body['patrol_routes'] if r['name']=='Fixture patrol')
    assert route['waypoints']==[{'x':31,'y':18}]
    p.faction=None
    assert not owner.benefits.patrols(p)
