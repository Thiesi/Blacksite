"""P8: one emitter for barks and zone ambience (architecture 5.5.3, game 13.4)."""

from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from random import Random

import pytest

from karst41.content.loader import load_content
from karst41.content.schema import Bark
from karst41.server import ambience as amb
from karst41.server.clock import TICK_HZ
from karst41.server.dialogue import BarkScheduler
from karst41.server.npcs.templates import make_actor
from karst41.server.protocol import Frame
from tests.character_helpers import act, create, place
from tests.harness import HeadlessServer

ROW = 'sodium-row'
TRAM = 'A tram goes over somewhere above the roofs. The puddles shiver.'


@pytest.fixture(scope='module')
def shipped():
    return load_content(Path(__file__).parents[1]/'src/karst41/content')


def quiet(content):
    """No spawners: every speaker in a test is placed by the test."""
    content = deepcopy(content)
    content.zones = {k: replace(z, meta=replace(z.meta, spawners=())) for k, z in content.zones.items()}
    return content


def caller(game, uid, tile=(25, 6), zone=ROW):
    client = game.connect({'user_id': uid, 'handle': f'Ear{uid}', 'node_name': 'P8'})
    create(game, client, name=f'Ear{uid}', card='none')
    if tile is not None:  # None: stay where creation leaves the caller (the Wake Hall).
        place(game, client, zone, tile)
    game.frames_for(client)
    return client


def regular(game, aid, tile, template='npc-sodium-regular'):
    actor = make_actor(game.core.characters.content.npcs[template], aid,
                       {'spawner': aid, 'home': tile, 'pause': 1 << 40})  # Holds still; wander isn't under test.
    game.core.world.enter(actor, ROW, tile)
    return actor


def lines(game, client, kinds=('ambient', 'speech')):
    out = []
    for frame in game.frames_for(client):
        if frame.type == 'log':
            out += [line for line in frame.data['lines'] if line['kind'] in kinds]
    return out


def run(game, clients, seconds):
    """Step second by second; return {client index: [(second, line)]}."""
    heard = {i: [] for i in range(len(clients))}
    for second in range(seconds):
        game.step(TICK_HZ)
        for i, client in enumerate(clients):
            heard[i] += [(second, line) for line in lines(game, client)]
    return heard


def emitter(game):
    return game.core.dialogue.ambience


# --- the stream --------------------------------------------------------------

def test_p8_stream_is_derived_per_zone_and_never_zone_rng(shipped):
    assert amb.stream(ROW).random() == amb.stream(ROW).random()
    assert amb.stream(ROW).random() != amb.stream('core-plaza').random()

    def states(enabled):
        game = HeadlessServer(deepcopy(shipped), character_state={})
        if not enabled:
            game.core.dialogue.ambience.tick = lambda *args: None
        caller(game, 1)
        game.step(200 * TICK_HZ)
        return {zid: zone.rng.getstate() for zid, zone in game.core.world.zones.items()}

    # The simulation's draws are identical with the emitter on or off.
    assert states(True) == states(False)


def test_p8_same_seed_and_inputs_give_the_same_lines_on_the_same_ticks(shipped):
    def heard():
        game = HeadlessServer(deepcopy(shipped), character_state={})
        client = caller(game, 1)
        return [(s, line['kind'], line['text']) for s, line in run(game, [client], 300)[0]]
    first = heard()
    assert first and first == heard()


# --- barks -------------------------------------------------------------------

def test_p8_bark_needs_a_caller_within_six_tiles(shipped):
    game = HeadlessServer(quiet(shipped), character_state={})
    near, far = caller(game, 1, (25, 6)), caller(game, 2, (38, 6))
    regular(game, 'r1', (31, 6))  # 6 tiles from near, 7 from far.
    heard = run(game, [near, far], 5)
    assert [line['text'] for _, line in heard[0]] == ['Sodium regular: ' + TRAM]
    assert heard[0][0][1]['speaker'] == 'Sodium regular' and heard[0][0][1]['speaker_role'] == 'civilian'
    assert heard[1] == []


def test_p8_bark_keeps_its_talkers_interval_and_an_authored_one(shipped):
    game = HeadlessServer(quiet(shipped), character_state={})
    client = caller(game, 1)
    regular(game, 'r1', (27, 6))
    times = [s for s, line in run(game, [client], 200)[0] if line['kind'] == 'speech']
    assert len(times) == 3 and all(b - a == 90 for a, b in zip(times, times[1:]))
    content = quiet(shipped)
    talker = content.dialogue['row-street-regular']
    content.dialogue['row-street-regular'] = replace(talker, barks=(Bark(TRAM, 1, 30),))
    game = HeadlessServer(content, character_state={})
    client = caller(game, 1)
    regular(game, 'r1', (27, 6))
    times = [s for s, line in run(game, [client], 100)[0] if line['kind'] == 'speech']
    assert len(times) == 4 and all(b - a == 30 for a, b in zip(times, times[1:]))


def test_p8_bark_weights_pick_by_authored_weight(shipped):
    talker = replace(shipped.dialogue['row-street-regular'], barks=(Bark('rare', 1, 1), Bark('common', 9, 1)))
    rng, picks = amb.stream(ROW), []
    for n in range(400):
        scheduler = BarkScheduler()
        picks.append(scheduler.choose(talker, n, rng, nearby=True, interacting=False, key='x').text)
    assert 300 < picks.count('common') < 400


def test_p8_a_talker_is_silent_while_anyone_talks_to_it(shipped):
    game = HeadlessServer(quiet(shipped), character_state={})
    client = caller(game, 1, (26, 6))
    actor = regular(game, 'r1', (27, 6))
    act(game, client, Frame('key', {'k': 'e', 't': 0}))
    game.commit_commerce()
    assert game.core.dialogue.talking(actor.id)
    lines(game, client)
    heard = run(game, [client], 60)
    assert not [line for _, line in heard[0] if line['kind'] == 'speech' and TRAM in line['text']]


def test_p8_covered_npc_barks_as_its_cover_until_it_reveals_itself(shipped):
    game = HeadlessServer(quiet(shipped), character_state={})
    unrevealed, revealed = caller(game, 1, (25, 6)), caller(game, 2, (25, 7))
    warden = regular(game, 'w1', (27, 6), 'npc-plainclothes-warden')
    warden.reveal_against(game.core.world.actors[revealed.session.player_id])
    heard = run(game, [unrevealed, revealed], 3)
    (_, cover), = heard[0]
    (_, true), = heard[1]
    assert (cover['speaker'], cover['speaker_role']) == ('Sodium regular', 'civilian')
    assert true['speaker'] == warden.name and true['speaker_role'] == 'warden'
    assert cover['id'] != true['id'] and TRAM in cover['text'] and TRAM in true['text']


# --- drops and the budget ------------------------------------------------------

def test_p8_a_dropped_bark_still_spends_its_interval(shipped):
    game = HeadlessServer(quiet(shipped), character_state={})
    client = caller(game, 1)
    game.step()
    emitter(game).callers[client.session.id].last_line = game.clock.now_tick()  # Budget spent.
    actor = regular(game, 'r1', (27, 6))
    heard = run(game, [client], 5)
    assert heard[0] == []
    voice = emitter(game).zones[ROW]
    assert voice.barks.next_due[actor.id] > game.clock.now_tick() + 80 * TICK_HZ


def test_p8_one_bark_reaches_one_caller_and_is_dropped_for_another(shipped):
    game = HeadlessServer(quiet(shipped), character_state={})
    fresh, spent = caller(game, 1, (25, 6)), caller(game, 2, (25, 7))
    game.step()
    emitter(game).callers[spent.session.id].last_line = game.clock.now_tick()
    regular(game, 'r1', (27, 6))
    heard = run(game, [fresh, spent], 3)
    assert len(heard[0]) == 1 and heard[1] == []


def test_p8_several_talkers_never_burst_when_the_budget_reopens(shipped):
    game = HeadlessServer(quiet(shipped), character_state={})
    client = caller(game, 1)
    for n, x in enumerate((22, 24, 27, 29)):
        regular(game, f'r{n}', (x, 6))
    heard = run(game, [client], 240)[0]
    times = [s for s, _ in heard]
    assert len(times) >= 4 and all(b - a >= amb.LINE_BUDGET_SECONDS for a, b in zip(times, times[1:]))


# --- zone ambience ---------------------------------------------------------------

def test_p8_ambience_only_where_authored_at_its_cadence(shipped):
    game = HeadlessServer(quiet(shipped), character_state={})
    row, hall = caller(game, 1), caller(game, 2, zone='vatside-wake-hall', tile=None)
    assert ROW in shipped.looks and shipped.looks[ROW].ambient
    assert 'vatside-wake-hall' not in shipped.looks or not shipped.looks['vatside-wake-hall'].ambient
    heard = run(game, [row, hall], 400)
    times = [s for s, line in heard[0] if line['kind'] == 'ambient']
    assert all(line['text'] in shipped.looks[ROW].ambient and line['role'] == 'log_ambient'
               and 'speaker' not in line for _, line in heard[0])
    assert len(times) >= 4
    assert all(amb.AMBIENT_SECONDS <= b - a <= amb.AMBIENT_SECONDS + amb.AMBIENT_JITTER_SECONDS + 1
               for a, b in zip(times, times[1:]))
    assert not [line for _, line in heard[1] if line['kind'] == 'ambient']


def test_p8_budget_spans_barks_and_ambience(shipped):
    game = HeadlessServer(deepcopy(shipped), character_state={})
    client = caller(game, 1)
    for n, x in enumerate((22, 24, 27, 29)):
        regular(game, f'x{n}', (x, 6))
    heard = run(game, [client], 600)[0]
    kinds = {line['kind'] for _, line in heard}
    times = [s for s, _ in heard]
    assert kinds == {'ambient', 'speech'}
    assert all(b - a >= amb.LINE_BUDGET_SECONDS for a, b in zip(times, times[1:]))


# --- suppression --------------------------------------------------------------------

def test_p8_suppressed_while_threatened(shipped):
    game = HeadlessServer(quiet(shipped), character_state={})
    client = caller(game, 1, (26, 6))
    hostile = make_actor(game.core.characters.content.npcs['npc-wake-drone'], 'drone', {'home': (24, 6)})
    hostile.marked = True  # Combat's relation: a Marked target is hostile to anyone.
    game.core.world.enter(hostile, ROW, (24, 6))
    me = game.core.world.actors[client.session.player_id]
    me.target = hostile.id
    assert game.core.dialogue.threatened(client.session, me)
    regular(game, 'r1', (27, 6))
    assert run(game, [client], 100)[0] == []


def test_p8_hunted_alone_is_not_threatened(shipped):
    game = HeadlessServer(quiet(shipped), character_state={})
    client = caller(game, 1)
    player = game.core.characters.players[client.session.player_id]
    from karst41.server import truce
    player.keeper_answer = {'keeper': 'sable', 'zone': ROW, 'until': truce.iso(game.core.combat.now() + 300)}
    assert not game.core.dialogue.threatened(client.session, game.core.world.actors[player.id])


def test_p8_suppressed_while_travelling(shipped):
    game = HeadlessServer(quiet(shipped), character_state={})
    client = caller(game, 1)
    game.step()
    avatar = game.core.characters.sim.avatars[client.session.user_id]
    avatar.travel, travel = object(), avatar.travel  # Any travel state suppresses.
    assert not emitter(game).admit(client.session, game.clock.now_tick())
    avatar.travel = travel
    assert emitter(game).admit(client.session, game.clock.now_tick())


def test_p8_ten_second_hold_after_a_danger_or_combat_line(shipped):
    game = HeadlessServer(quiet(shipped), character_state={})
    client = caller(game, 1)
    game.step()
    client.session.emit('You are hit.', kind='combat', channel='zone', role='log_combat',
                        at=game.clock.now_utc().isoformat())
    start, gate = game.clock.now_tick(), emitter(game)
    assert not gate.admit(client.session, start)
    assert not gate.admit(client.session, start + (amb.DANGER_HOLD_SECONDS * TICK_HZ - 1))
    assert gate.admit(client.session, start + amb.DANGER_HOLD_SECONDS * TICK_HZ)
    # A bark that fires inside the hold is dropped and still spends its interval.
    game2 = HeadlessServer(quiet(shipped), character_state={})
    other = caller(game2, 1)
    game2.step()
    other.session.emit('Danger.', kind='danger', channel='zone', role='log_danger',
                       at=game2.clock.now_utc().isoformat())
    regular(game2, 'r1', (27, 6))
    assert run(game2, [other], 30)[0] == []


# --- reconnect ---------------------------------------------------------------------

def test_p8_reconnect_never_replays_ambience_and_drops_session_state(shipped):
    game = HeadlessServer(quiet(shipped), character_state={})
    client = caller(game, 1)
    regular(game, 'r1', (27, 6))
    heard = run(game, [client], 5)[0]
    assert [line for _, line in heard if TRAM in line['text']]
    assert not [line for line in client.session.log_ring if TRAM in line.get('text', '')]
    sid = client.session.id
    game.core.sessions.disconnect(client.session)
    game.step(2)
    assert sid not in emitter(game).callers
    again = game.connect({'user_id': 1, 'handle': 'Ear1', 'node_name': 'P8'})
    game.step(2)
    replayed = [line for frame in game.frames_for(again) if frame.type == 'log' and frame.data.get('replay')
                for line in frame.data['lines']]
    assert not [line for line in replayed if TRAM in line['text'] or line['kind'] == 'ambient']
