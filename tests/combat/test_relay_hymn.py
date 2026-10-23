"""Game 7.7: Bell adds a tile to the actual restorative recipient radius."""

from dataclasses import replace

from blacksite.server.protocol import Frame
from blacksite.server.rules import combat as rules
from tests.combat.test_engine import cantor_duel, body
from tests.character_helpers import act, place
from tests.server.test_relay_benefits import owned


def test_game_7_7_bell_extends_actual_hymn_without_scaling_installed_radius(cantor_duel,monkeypatch):
    game,caller,ally=cantor_duel
    p=game.core.characters.players[caller.session.player_id]
    p.faction='halvard'
    game.core.factions.refresh(p)
    actor,other=body(game,caller),body(game,ally)
    game.core.combat.allies_provider=lambda source:[actor,other]
    base=max(rules.ABILITY_RANGE,game.core.progression.modifiers(p).bonus('hymn_radius'))
    place(game,ally,'vatside-clinics',(25+int(base)+1,3))
    other.shock=50
    other.cooldowns['last_hit']=game.clock.now_tick()+10000
    act(game,caller,Frame('intent',{'name':'ability','args':{'id':'hymn_steady'}}))
    game.step(4)
    game.commit_commerce()
    assert other.shock==50
    game.step(125)
    owner=game.core.relays
    active=owner.active
    monkeypatch.setattr(owner,'active',lambda rid:rid=='bell' or active(rid))
    bell=owner.content.relays['bell']
    monkeypatch.setitem(owner.content.relays,'bell',replace(bell,benefit=replace(bell.benefit,district='Vatside')))
    owned(game,'bell')  # Explicit local eligibility fixture; no S25 geography proof.
    assert game.core.progression.modifiers(p).bonus('hymn_radius')<=base
    assert actor.modifiers['hymn_radius_bonus']==1
    act(game,caller,Frame('intent',{'name':'ability','args':{'id':'hymn_steady'}}))
    game.step(4)
    assert other.shock<=30
