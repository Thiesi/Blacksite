"""Game 10: consent, live membership and privacy through production Core."""

from pathlib import Path

import pytest

from blacksite.content.loader import load_content
from blacksite.server.protocol import Frame
from blacksite.server.progression import Grant
from blacksite.server.rules.character import grade_threshold
from blacksite.server.skills import Use
from tests.character_helpers import act, create, place
from tests.harness import HeadlessServer


@pytest.fixture(scope='module')
def content():
    return load_content(Path(__file__).parents[2]/'src/blacksite/content')


@pytest.fixture
def callers(content):
    game = HeadlessServer(content, character_state={})
    clients = []
    for uid in (1, 2, 3):
        caller = game.connect({'user_id': uid, 'handle': f'Wide界{uid}', 'node_name': 'test'})
        create(game, caller, archetype=3 if uid == 1 else 1, name=f'Caller界{uid}')
        place(game, caller, 'vatside-wake-hall', (8+uid, 10))
        clients.append(caller)
    return game, *clients


def invite(game, source, target):
    crews = game.core.crews
    crews.perform(source.session, 'invite', target.session.player_id)
    invitation = next(i for i in crews.registry.invites.values() if i.target == target.session.player_id)
    crews.perform(target.session, 'accept', invitation.id)
    return crews.registry.crew_of(source.session.player_id)


def test_game_10_invite_accept_chat_and_leave_remove_audience(callers):
    game, one, two, outsider = callers
    crew = invite(game, one, two)
    chat, crews = game.core.chat, game.core.crews
    assert crew.members == (one.session.player_id, two.session.player_id)
    assert {s.id for s in chat.recipients(one.session, 'crew')} == {one.session.id, two.session.id}
    crews.perform(two.session, 'leave')
    assert not chat.recipients(one.session, 'crew')
    assert not crews.registry.crews


def test_game_11_ignored_identity_cannot_send_crew_invitation(callers):
    game, source, target, _ = callers
    chat, crews = game.core.chat, game.core.crews
    name = game.core.characters.players[source.session.player_id].name
    chat.ignore(target.session, name)
    game.frames_for(target)
    with pytest.raises(ValueError, match='not accepting'):
        crews.perform(source.session, 'invite', target.session.player_id)
    assert not crews.registry.invites and not game.frames_for(target)
    chat.ignore(target.session, name, enabled=False)
    crew = invite(game, source, target)
    assert crew.members == (source.session.player_id, target.session.player_id)


def test_game_10_leader_logout_transfers_to_oldest_and_dissolves_at_one(callers):
    game, one, two, three = callers
    crew = invite(game, one, two)
    invite(game, one, three)
    game.core.sessions.disconnect(one.session)
    assert crew.leader == two.session.player_id
    assert crew.members == (two.session.player_id, three.session.player_id)
    game.core.sessions.disconnect(two.session)
    assert not game.core.crews.registry.crews


def test_game_10_marked_hostile_crew_damage_refused_and_pickup_requires_crew(callers):
    game, one, two, outsider = callers
    invite(game, one, two)
    combat = game.core.combat
    a, b, c = [game.core.characters.sim.avatars[x.session.user_id].actor for x in (one, two, outsider)]
    b.marked = True
    a.faction, b.faction = 'halvard', 'sable'
    assert combat.relation(a, b) == 'allied'
    assert not combat.legal(a, b) and not combat.permits_indirect(a, b)
    b.stance, b.health = 'down', 0
    game.core.characters.players[b.id].progress['combat'] = {'killer': 'npc'}
    c.x, c.y = a.x, a.y
    assert not combat.pickup(c, b)
    assert combat.pickup(a, b)
    assert b.health > 0 and b.stance == 'normal'


def test_game_10_roster_private_location_redacted_and_marked_colour_preserved(callers):
    game, one, two, _ = callers
    crew = invite(game, one, two)
    crews = game.core.crews
    a, b = [game.core.characters.sim.avatars[x.session.user_id].actor for x in (one, two)]
    b.behaviour['private_owner'] = b.id
    crew.beacon = (a.id, b.id)
    row = next(r for r in crews.roster(a.id) if r['id'] == b.id)
    assert row['zone'] == 'private' and row['direction'] == ''
    body = {'me': {}, 'actors': [], 'nearby': [], 'objects': [], 'viewport': {'w': 10}}
    crews.decorate(one.session, body)
    assert not body['objects']
    b.behaviour.pop('private_owner')
    b.marked = True
    body['actors'] = [{'id': b.id, 'role': 'player_hostile'}]
    body['nearby'] = [{'id': b.id, 'role': 'player_hostile', 'relation': '!'}]
    crews.decorate(one.session, body)
    assert body['actors'][0]['role'] == 'player_hostile'
    assert body['nearby'][0]['relation'] == '+'
    assert body['objects'][0]['id'] == 'crew-beacon'


def test_game_10_g_menu_confirmation_cancel_and_stale_selection(callers):
    game, one, two, _ = callers
    invite(game, one, two)
    act(game, one, Frame('key', {'k': 'g', 't': 0}))
    crews = game.core.crews
    assert one.session.id in crews.menus
    screen = crews.menus[one.session.id]
    row = crews.body(one.session, screen)['rows'][screen.cursor]['id']
    act(game, one, Frame('intent', {'name': 'menu_select', 'args': {'key': 'l', 'row': row}}))
    assert screen.confirmation == ('leave', '')
    act(game, one, Frame('intent', {'name': 'menu_close', 'args': {}}))
    assert screen.confirmation is None and crews.crew_id(one.session.player_id)
    one.send(Frame('intent', {'name': 'menu_select', 'args': {'key': 'l', 'row': row},
        'request_id': 'stale', 'expected_revision': one.session.view_revision+1}))
    game.step()
    assert screen.confirmation is None


def reward(game, source, grant, *, error=False):
    player = game.core.characters.players[source.session.player_id]
    engine = game.core.progression
    patch, identity, result = engine.reward_patch(player, grant)
    game.core.commerce.settle(player, patch, game.core.commerce.items,
        game.core.commerce.caches, game.core.commerce.serial, lambda success: None, identity)
    game.core.crews.add_rewards(game.core.commerce.outbox[-1], player, grant)
    return game.commit_commerce(error=error)


def test_game_10_guarded_xp_same_source_amount_and_rollback(callers):
    game, one, two, outsider = callers
    invite(game, one, two)
    players = [game.core.characters.players[c.session.player_id] for c in (one, two, outsider)]
    for p, grade in zip(players, (5, 7, 5)):
        p.grade, p.xp = grade, grade_threshold(grade)
    game.step(102)
    before = [p.xp for p in players]
    grant = Grant('combat', 'npc-receipt', True, scope='npc-slot', opponent_grade=8)
    reward(game, one, grant, error=True)
    assert [p.xp for p in players] == before
    reward(game, one, grant)
    assert players[0].xp-before[0] == players[1].xp-before[1] == 26
    assert players[2].xp == before[2]
    reward(game, one, grant)
    assert players[1].xp-before[1] == 26


def test_game_10_late_join_needs_contribution_and_recipient_run_cap(callers):
    game, one, two, _ = callers
    invite(game, one, two)
    player = game.core.characters.players[two.session.player_id]
    before = player.xp
    reward(game, one, Grant('combat', 'first', True, scope='first', opponent_grade=1))
    assert player.xp == before
    game.core.crews.contribution(player.id, Use('weapon_hit', 'kinetic', 'real-hit', True, threat=True))
    reward(game, one, Grant('run', 'data-1', True, scope='core-a', core='core-a', tier=2))
    assert player.xp-before == 80
    reward(game, one, Grant('run', 'data-2', True, scope='core-a', core='core-a', tier=2))
    assert player.xp-before == 80


def test_game_10_same_tick_npc_drops_rotate_through_source_queue(callers):
    from dataclasses import replace
    from blacksite.content.schema import LootEntry
    from blacksite.server.npcs.templates import make_actor

    game, one, two, _ = callers
    crew = invite(game, one, two)
    crews, commerce = game.core.crews, game.core.commerce
    crews.registry.loot_mode(one.session.player_id, 'round_robin')
    content = game.core.loop.content
    original = content.npcs['npc-maintenance-drone']
    template = replace(original, loot=(LootEntry('ammo_9x', 1),))
    content.npcs[template.id] = template
    source = game.core.world.actors[one.session.player_id]
    try:
        for index in range(2):
            target = make_actor(template, f'fixture-double-drop:{index}',
                                {'home': (12+index, 10), 'phase': 0})
            game.core.world.enter(target, source.zone, (12+index, 10))
            game.core.npcs.died(source, target)
        assert len(commerce.outbox) == 1 and len(commerce.waiting) == 1
        game.commit_commerce()
        recipients = [cache['crew_offer']['recipient'] for cache in commerce.caches.values()]
        assert recipients == [one.session.player_id, two.session.player_id]
        assert crew.loot_version == 2 and crew.next_loot == 0
    finally:
        content.npcs[original.id] = original


def test_game_10_frozen_cache_offer_victim_exemption_and_failed_rotation(callers):
    game, one, two, victim = callers
    crew = invite(game, one, two)
    crews, commerce = game.core.crews, game.core.commerce
    crews.registry.loot_mode(one.session.player_id, 'round_robin')
    cache = {'victim': victim.session.player_id, 'killer': one.session.player_id,
             'private_until': game.clock.now_utc().timestamp()+60}
    effect = {'caches': {'drop': cache}, 'callback': lambda success: None}
    crews.stage_cache(effect, 'drop', one.session.player_id)
    now = game.clock.now_utc().timestamp()
    assert crews.cache_permits(victim.session.player_id, cache, now)
    assert not crews.cache_permits(two.session.player_id, cache, now)
    effect['callback'](False)
    assert crew.next_loot == 0
    effect['callback'](True)
    assert crew.next_loot == 1
    crews.registry.loot_mode(one.session.player_id, 'ffa')
    assert not crews.cache_permits(two.session.player_id, cache, now)
    assert crews.cache_permits(two.session.player_id, cache, now+10)
    crews.perform(two.session, 'leave')
    assert crews.cache_permits(two.session.player_id, cache, now+10)


def test_game_10_data_offer_frozen_mode_utc_deadline_and_commit_rotation(callers):
    game, one, two, _ = callers
    crew = invite(game, one, two)
    crews = game.core.crews
    crews.registry.loot_mode(one.session.player_id, 'round_robin')
    offer = crews.check_data(one.session.player_id, 'unit-1')
    with pytest.raises(ValueError, match='round-robin'):
        crews.check_data(two.session.player_id, 'unit-1')
    crews.registry.loot_mode(one.session.player_id, 'ffa')
    with pytest.raises(ValueError, match='round-robin'):
        crews.check_data(two.session.player_id, 'unit-1')
    game.step(100)
    assert crews.check_data(two.session.player_id, 'unit-1').recipient == one.session.player_id
    assert crews.registry.commit_offer(offer)
    assert crew.next_loot == 1


def test_game_10_guarding_uses_elapsed_ticks_and_roster_uses_real_integrity_max(callers):
    from blacksite.server.crews import GUARD_SECONDS, SILT_SHARE_SECONDS
    from blacksite.server.lattice.presence import Presence
    game, one, two, _ = callers
    invite(game, one, two)
    crews = game.core.crews
    game.step()
    game.clock.advance(GUARD_SECONDS*10)
    game.step()
    assert (one.session.player_id, two.session.player_id) in crews.guarded_at
    presence = Presence('crew-presence', two.session.player_id, 'lat-core', 'entry', (),
                        integrity=75, integrity_max=150)
    game.core.lattice.presences[two.session.player_id] = presence
    assert next(r for r in crews.roster(one.session.player_id) if r['id'] == two.session.player_id)['hp_pct'] == 50
    crews.remember_silt(one.session.player_id, ('sector', 'entrance'), 'seed')
    assert crews.shared_silt(two.session.player_id, ('sector', 'elsewhere')) is None
    game.clock.advance(SILT_SHARE_SECONDS*10)
    assert crews.shared_silt(two.session.player_id, ('sector', 'entrance')) is None


def test_game_10_crew_event_text_loads_and_formats(callers):
    game, *_ = callers
    crews = game.core.crews
    assert len(crews.messages) == 15
    assert crews.text('friendly_fire') == "You don't shoot crew."
    for message in crews.messages:
        assert crews.text(message, name='Wide界', mode='round robin')
