"""Demo only: the record of door attempts changes nothing and keeps the words."""

from karst41.server import demo_doors
from karst41.server.interaction import Interaction
from tests.character_helpers import place
from tests.demo.test_truce_standin import body, boot


def rig(repo_root, monkeypatch, **kw):
    game, caller = boot(repo_root, monkeypatch, **kw)
    seen = []
    demo_doors.install(game.core, lambda message, **fields: seen.append((message, fields)))
    place(game, caller, 'sodium-row', (89, 12))
    sim = game.core.characters.sim
    avatar = sim.avatars[caller.session.user_id]
    door = next(e for e in game.core.world.zones['sodium-row'].template.meta.exits if e.id == 'to-sodium-tin-halo')
    return game, caller, sim, avatar, door, seen


def test_a_refusal_keeps_its_words_and_the_state_behind_it(repo_root, monkeypatch):
    game, caller, sim, avatar, door, seen = rig(repo_root, monkeypatch, bouncer=True)
    truce = game.core.combat.hostile_hook.__self__
    truce.breakers[caller.session.player_id] = game.core.combat.now() + 900
    body(game, caller).marked = True
    sim.interact(caller.session, avatar, 0, choice=Interaction(value=door))
    message, fields = seen[-1]
    assert message == 'demo door'
    assert 'Not tonight' in fields['outcome']
    assert fields['exit'] == 'to-sodium-tin-halo' and fields['marked'] is True
    assert avatar.zone == 'sodium-row'
    assert any('Not tonight' in line.get('text', '') for line in caller.session.log_ring)


def test_going_through_is_recorded_and_still_works(repo_root, monkeypatch):
    game, caller, sim, avatar, door, seen = rig(repo_root, monkeypatch)
    sim.interact(caller.session, avatar, game.core.world.zones['sodium-row'].tick, choice=Interaction(value=door))
    assert seen[-1][1]['outcome'] == 'went through'
    assert avatar.zone == 'sodium-tin-halo'  # the door still works
    assert seen[-1][1]['zone'] == 'sodium-row'


def test_demo_off_records_nothing(repo_root, monkeypatch):
    game, caller = boot(repo_root, monkeypatch, demo=False)
    seen = []
    original = game.core.characters.sim.interact
    demo_doors.install(game.core, lambda message, **fields: seen.append(message))
    assert game.core.characters.sim.interact == original and not seen
