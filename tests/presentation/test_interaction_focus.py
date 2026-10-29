"""Architecture 5.5.2: one E/J decision, unchanged mechanics and disclosure."""

from copy import deepcopy
from dataclasses import asdict, replace
import json
from pathlib import Path
from typing import Any

import pytest

from blacksite.content.loader import load_content
from blacksite.content.schema import ObjectSpec
from blacksite.door.model import Display
from blacksite.layout import compute
from blacksite.server.bus import Event
from blacksite.server.commerce import CommerceMenu
from blacksite.server.lattice.presence import Presence
from blacksite.server.protocol import Frame
from blacksite.server.world.zone import ObjectState
from tests.character_helpers import create, place
from tests.harness import HeadlessServer
from tests.fake_terminal import FakeTerminal
from tests.door.conftest import info
from tests.presentation.interaction_matrix import ORDER, run_matrix


E = Frame('key', {'k': 'e', 't': 0})


@pytest.fixture
def focus_game(repo_root: Path) -> tuple[HeadlessServer, Any]:
    game = HeadlessServer(load_content(repo_root/'src/blacksite/content'), character_state={})
    caller = game.connect()
    create(game, caller, archetype=0, card='none')
    game.commit_characters()
    game.commit_commerce()
    return game, caller


def dispatch(game: HeadlessServer, caller: Any, frame: Frame = E) -> None:
    game.core._echo(Event('input', {'session': caller.session, 'frame': frame, 'tick': game.clock.now_tick()}))


def test_arch_5_5_2_predicted_equals_dispatched_and_pre_p3_behavior(repo_root: Path) -> None:
    result, _ = run_matrix(repo_root)
    baseline = json.loads(Path(__file__).with_name('interaction-baseline.json').read_text())
    assert result['cases'] == baseline['cases']
    assert result['sha256'] == baseline['sha256'], 'E/J behavior differs from the independently executed pre-P3 baseline'
    assert result['handlers'] == baseline['handlers']


@pytest.mark.parametrize('size', [(80, 24), (132, 50)])
@pytest.mark.parametrize('tier', ['16', '256', 'truecolor'])
def test_ui_3_focus_changes_only_existing_hint_cells(focus_game: tuple[HeadlessServer, Any], info: Any,
                                                  size: tuple[int, int], tier: str) -> None:
    game, caller = focus_game
    core = game.core
    caller.session.caps.update(width=size[0], height=size[1])
    place(game, caller, 'vatside-wake-hall', (34, 15))
    game.commit_commerce()
    game.step()
    body = core.characters.sim.views[caller.session.id].previous['body']
    assert body['focus']['id'] == 'wake-outfitter'
    legacy = deepcopy(body)
    legacy.pop('focus')
    legacy.pop('jack_focus')
    legacy['hint'] = 'Tab target  F fire  X weapon  1-5 quick  V abilities  E interact  I inventory  ? help'
    def render(document: dict[str, Any]) -> FakeTerminal:
        model = Display(replace(info, width=size[0], height=size[1], color_depth=tier))
        model.receive(Frame('welcome', {'keymap': asdict(core.characters.content.keymaps),
            'palette': asdict(core.characters.content.palette)}), 0)
        model.receive(Frame('view', {'rev': 1, 'kind': 'zone', 'body': document}), 1)
        terminal = FakeTerminal(*size)
        terminal.write(model.render(1)[0])
        return terminal
    before, after = render(legacy), render(body)
    hint = compute(*size).hint
    changed = {y for y in range(size[1]) if before.grid[y] != after.grid[y]
        or any(before.renditions.get((x, y)) != after.renditions.get((x, y)) for x in range(size[0]))}
    assert changed == {hint.y}
    assert 'E open Sablier Wake Outfitter' in after.screen_text().splitlines()[hint.y]
    assert 'J jack in at Tutorial terminal' in after.screen_text().splitlines()[hint.y]


@pytest.mark.parametrize('kind', ['light', 'camera', 'salvage_field', 'descent_console'])
def test_arch_5_5_2_s25a_underfoot_and_explicit_j(focus_game: tuple[HeadlessServer, Any], kind: str) -> None:
    game, caller = focus_game
    core = game.core
    zone = core.world.zones['vatside-wake-hall']
    terminal = next(obj for obj in zone.objects.values() if obj.spec.kind == 'terminal')
    tile = terminal.spec.tile[0]+1, terminal.spec.tile[1]
    place(game, caller, zone.id, tile)
    game.commit_commerce()
    zone.objects['fixture-prop'] = ObjectState(ObjectSpec('fixture-prop', tile, kind,
        params={'name': 'Sealed season door', 'season_door': True} if kind == 'descent_console' else {}))
    e, jack = core.interaction_views(caller.session)
    assert jack and jack['id'] == terminal.spec.id
    assert e and e['id'] == ('fixture-prop' if kind == 'descent_console' else terminal.spec.id)
    dispatch(game, caller)
    assert (caller.session.player_id in core.lattice.presences) == (kind != 'descent_console')
    if kind == 'descent_console':
        assert caller.session.log_ring[-1]['text'] == 'Sealed season door'
        dispatch(game, caller, Frame('key', {'k': 'j'}))
        assert caller.session.player_id in core.lattice.presences


def test_arch_5_5_2_unseen_winner_is_masked_without_falling_through(focus_game: tuple[HeadlessServer, Any]) -> None:
    game, caller = focus_game
    core = game.core
    zone = core.world.zones['vatside-wake-hall']
    # An opaque intervening wall can hide a cabinet within Interlock's
    # existing three-tile inspection range. Do not change that rule in P3.
    place(game, caller, zone.id, (15, 5))
    zone.objects.clear()
    obj = ObjectState(ObjectSpec('fixture-hidden-cabinet', (18, 5), 'hardware', {'name': 'Hidden cabinet'}))
    zone.objects[obj.spec.id] = obj
    core.lattice.interlock.hardware = {(zone.id, obj.spec.id): {}}
    zone.geometry[16, 5] = 'wall'
    zone.geometry_revision += 1
    result = core.resolve_interaction(caller.session, E)
    assert result.route.name == 'interlock' and result.choice.focus.id == obj.spec.id
    assert core.interaction_views(caller.session)[0] is None
    dispatch(game, caller)
    assert core.lattice.interlock.menus[caller.session.id][:2] == (zone.id, obj.spec.id)


@pytest.mark.parametrize('keymap,key', [('arrows', 'j'), ('vi', 'ctrl-o')])
def test_arch_5_5_2_j_keymap_and_jacked_return(focus_game: tuple[HeadlessServer, Any], keymap: str, key: str) -> None:
    game, caller = focus_game
    core, session = game.core, caller.session
    session.keymap_id = keymap
    avatar = core.characters.sim.avatars[session.user_id]
    lat = core.lattice
    sector = 'lat-vatside'
    cell = lat.sectors.entrance(sector)
    presence = Presence(avatar.actor.id+':presence', avatar.actor.id, sector, cell,
                        ('prg_pick', 'prg_umbrella', None), loaned_rig=True)
    lat.presences[session.player_id] = presence
    avatar.actor.stance = 'jacked'
    focus, jack = core.interaction_views(session)
    assert jack == {'id': avatar.actor.id, 'label': 'street', 'verb': 'jack out to'}
    predicted = core.resolve_interaction(session, Frame('key', {'k': key}))
    assert predicted.route.name == 'lattice'
    dispatch(game, caller, Frame('key', {'k': key}))
    assert session.player_id not in lat.presences or presence.escape is not None


def test_arch_5_5_2_lattice_cells_inspect_before_using_uplinks(focus_game: tuple[HeadlessServer, Any]) -> None:
    game, caller = focus_game
    core, session = game.core, caller.session
    lat = core.lattice
    actor = core.characters.sim.avatars[session.user_id].actor
    inspected = uplinks = 0
    for sector, cells in lat.sectors.cells.items():
        for cell in cells.values():
            presence = Presence(actor.id+':presence', actor.id, sector, cell.id,
                                ('prg_pick', 'prg_umbrella', None), loaned_rig=True)
            lat.presences[session.player_id] = presence
            actor.stance = 'jacked'
            lat.encounters.menus.clear()
            session.log_ring.clear()
            result = core.resolve_interaction(session, E)
            assert result.route.name == 'lattice'
            dispatch(game, caller)
            if result.choice.kind == 'encounter':
                inspected += 1
                assert result.choice.focus.id == sector+':'+cell.id
                assert session.id in lat.encounters.menus
                assert presence.destination is None  # Inspection precedes an uplink.
            elif cell.uplink:
                uplinks += 1
                assert result.choice.focus.id == sector+':'+cell.id
                assert session.id not in lat.encounters.menus
                assert presence.destination == (cell.uplink.sector, cell.uplink.cell) or session.log_ring
            else:
                assert result.choice.focus is None and presence.destination is None
    assert inspected and uplinks


def query_state(game: HeadlessServer, caller: Any) -> dict[str, Any]:
    core = game.core
    return deepcopy({
        'players': [player.record() for player in core.characters.players.values()],
        'identities': core.characters.identities,
        'items': [item.record() for item in core.commerce.items.values()],
        'actors': {key: asdict(actor) for key, actor in core.world.actors.items()},
        'objects': {zid: {oid: asdict(obj) for oid, obj in zone.objects.items()}
                    for zid, zone in core.world.zones.items()},
        'rng': {zid: zone.rng.getstate() for zid, zone in core.world.zones.items()},
        'presence': {pid: asdict(p) for pid, p in core.lattice.presences.items()},
        'commerce': (core.commerce.pending, core.commerce.outbox, core.commerce.waiting),
        'characters_outbox': core.characters.outbox,
        'session': (caller.session.send_queue, caller.session.log_ring, caller.session.pending_prompts),
    })


@pytest.mark.parametrize('jacked', [False, True])
def test_arch_5_5_2_queries_are_pure(focus_game: tuple[HeadlessServer, Any], jacked: bool) -> None:
    game, caller = focus_game
    core, session = game.core, caller.session
    place(game, caller, 'vatside-wake-hall', (34, 15))
    game.commit_commerce()
    if jacked:
        core.lattice.jack_in(session)
    before = query_state(game, caller)
    for key in ('e', 'j'):
        for route in core.input_routes():
            route.query(session, Frame('key', {'k': key}))
        core.resolve_interaction(session, Frame('key', {'k': key}))
    assert query_state(game, caller) == before


@pytest.mark.parametrize('mode', ['commerce', 'chat-key', 'chat-intent', 'travel', 'down'])
def test_arch_5_5_2_modal_and_disabled_states_do_not_advertise_world_targets(
        focus_game: tuple[HeadlessServer, Any], mode: str) -> None:
    game, caller = focus_game
    core, session = game.core, caller.session
    place(game, caller, 'vatside-wake-hall', (34, 15))
    game.commit_commerce()
    frame = E
    if mode == 'commerce':
        core.commerce.menus[session.id] = CommerceMenu('inventory')
        expected = 'commerce'
    elif mode.startswith('chat'):
        # Two tiles from the outfitter counter, so its NPC service does not
        # own E before the chat handler. No NPC placement changes are needed.
        place(game, caller, 'vatside-wake-hall', (36, 15))
        game.commit_commerce()
        session.pending_prompts['chat'] = {'id': 'chat', 'channel': 'say'}
        if mode == 'chat-intent':
            frame = Frame('intent', {'name': 'interact', 'args': {}})
            # Existing chat blocks keys, not Interact intents. Preserve that
            # distinction rather than "fixing" it during presentation work.
            expected = 'terminal'
        else:
            expected = 'chat'
    elif mode == 'travel':
        from blacksite.server.world.exits import schedule
        avatar = core.characters.sim.avatars[session.user_id]
        ex = core.world.zones[avatar.zone].template.meta.exits[0]
        avatar.travel = schedule(replace(ex, kind='lift'), game.clock.now_utc().timestamp())
        expected = 'characters'
    else:
        core.characters.players[session.player_id].progress['combat'] = {'stage': 'down'}
        expected = 'combat'
    result = core.resolve_interaction(session, frame)
    assert result.route.name == expected
    assert result.choice.focus is None or mode == 'chat-intent'
    assert [route.name for route in core.input_routes()] == list(ORDER)
    dispatch(game, caller, frame)
