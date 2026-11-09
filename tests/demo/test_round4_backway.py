"""Round 4: the locked latch tells the same truth as its Lattice binding."""

from dataclasses import replace

from karst41.server.interaction import Interaction
from tests.character_helpers import place
from tests.demo.test_truce_standin import boot


def test_locked_halo_door_names_its_core_without_opening(repo_root, monkeypatch):
    game, caller = boot(repo_root, monkeypatch)
    place(game, caller, 'sodium-tin-halo', (30, 5))
    sim = game.core.characters.sim
    zone = game.core.world.zones['sodium-tin-halo']
    door = zone.objects['halo-back-room']
    sim.interact(caller.session, sim.avatars[caller.session.user_id],
                 game.clock.now_tick(), choice=Interaction(value=door))
    assert caller.session.log_ring[-1]['text'] == 'Locked. The latch runs off the Tin Halo core.'
    assert not door.open


def test_locked_line_is_generic_and_hides_private_core_name(repo_root, monkeypatch):
    game, _ = boot(repo_root, monkeypatch)
    content = game.core.world.content
    core = content.cores['lat-tin-halo']
    sim = game.core.characters.sim
    content.cores[core.id] = replace(core, name='Other house')
    assert sim.locked_line('sodium-tin-halo', 'halo-back-room') == (
        'Locked. The latch runs off the Other house core.')
    content.cores[core.id] = replace(core, owner_kind='private', name='Never disclose this')
    assert sim.locked_line('sodium-tin-halo', 'halo-back-room') == (
        'Locked. The latch runs off a private core.')
    content.cores[core.id] = replace(core, template=True)
    assert sim.locked_line('sodium-tin-halo', 'halo-back-room') == 'Locked.'
    assert sim.locked_line('sodium-tin-halo', 'unbound-door') == 'Locked.'


def test_back_room_label_keeps_the_control_label(repo_root, monkeypatch):
    game, _ = boot(repo_root, monkeypatch)
    core = game.core.world.content.cores['lat-tin-halo']
    room = next(room for room in core.rooms if room.id == 'room-3')
    assert room.label == 'Back room'
    assert next(c for c in room.controls if c.id == 'back-door').label == 'back door'
