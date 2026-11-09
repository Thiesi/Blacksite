"""Demo only: round 1's most likely trap. A shot regular parked on the Halo door and took E."""

from karst41.server import demo_doors
from karst41.server.protocol import Frame
from tests.character_helpers import act, place
from tests.demo.test_truce_standin import body, boot, spawn

DOOR = (90, 12)


def press_e(game, caller):
    act(game, caller, Frame('key', {'k': 'e', 't': 0}))
    game.commit_commerce()
    game.step()


def beside(game, npc, tile):
    npc.x, npc.y = tile
    game.core.world.zones['sodium-row'].position_update(npc)


def test_a_fleeing_regular_never_stands_on_the_door(repo_root, monkeypatch):
    game, caller = boot(repo_root, monkeypatch)
    place(game, caller, 'sodium-row', (60, 12))
    regular = spawn(game, 'sodium-row', 'npc-sodium-regular', (62, 12), group='regulars')
    game.core.combat.exchange(body(game, caller), regular)
    for _ in range(600):
        game.step()
        assert regular.position != DOOR


def test_a_wanderer_outside_its_region_walks_home(repo_root, monkeypatch):
    game, caller = boot(repo_root, monkeypatch)
    place(game, caller, 'sodium-row', (20, 12))
    regular = spawn(game, 'sodium-row', 'npc-sodium-regular', (62, 12), group='regulars')
    beside(game, regular, (88, 12))
    game.step(400)
    assert regular.position == (62, 12)


def test_on_the_door_e_goes_through_even_with_a_talker_beside_you(repo_root, monkeypatch):
    game, caller = boot(repo_root, monkeypatch)
    place(game, caller, 'sodium-row', DOOR)
    regular = spawn(game, 'sodium-row', 'npc-sodium-regular', (89, 12), group='regulars')
    regular.behaviour['region'] = None
    focus, _ = game.core.interaction_views(caller.session)
    assert focus['verb'] == 'go to'
    press_e(game, caller)
    assert game.core.characters.sim.avatars[caller.session.user_id].zone == 'sodium-tin-halo'


def test_off_the_door_a_talker_still_answers_and_it_is_recorded(repo_root, monkeypatch):
    game, caller = boot(repo_root, monkeypatch)
    seen = []
    demo_doors.install(game.core, lambda message, **fields: seen.append(fields))
    place(game, caller, 'sodium-row', (89, 12))
    spawn(game, 'sodium-row', 'npc-sodium-regular', (89, 11), group='regulars')
    press_e(game, caller)
    assert caller.session.id in game.core.dialogue.menus
    assert seen[-1]['exit'] == 'to-sodium-tin-halo' and seen[-1]['outcome'].startswith('a talker took E')
