"""Demo only: round 3's rulings (#170). The Halo, Vesper's work, being hunted, the arrival notice."""

from datetime import datetime, timezone

import pytest

from blacksite.content.loader import load_content
from blacksite.server import demo_doors
from blacksite.server.protocol import Frame
from blacksite.server.views import presentation
from tests.character_helpers import act, place
from tests.demo.test_truce_standin import body, boot, spawn


def row(repo_root, monkeypatch, tile=(60, 12)):
    game, caller = boot(repo_root, monkeypatch)
    place(game, caller, 'sodium-row', tile)
    truce = game.core.combat.hostile_hook.__self__
    sim = game.core.characters.sim
    door = next(e for e in game.core.world.zones['sodium-row'].template.meta.exits
                if e.target_zone == 'sodium-tin-halo')
    return game, caller, truce, sim, door


def shoot_an_npc(game, caller):
    guard = spawn(game, 'sodium-row', 'npc-row-enforcer', (62, 12), group='enforcers')
    regular = spawn(game, 'sodium-row', 'npc-sodium-regular', (61, 13), group='regulars')
    game.core.combat.exchange(body(game, caller), regular)
    return guard


def test_someone_sable_is_answering_is_refused_with_the_time_left(repo_root, monkeypatch):
    game, caller, truce, sim, door = row(repo_root, monkeypatch)
    shoot_an_npc(game, caller)
    assert not body(game, caller).marked
    assert sim.travel_refusal(caller.session, door) == (
        'The bouncer doesn\'t move. "Sable\'s still asking about you. Try me in 5 min."')


def test_the_door_opens_when_the_answer_ends(repo_root, monkeypatch):
    game, caller, truce, sim, door = row(repo_root, monkeypatch)
    shoot_an_npc(game, caller)
    for key in list(game.core.npcs.provocations):
        game.core.npcs.provocations[key] = game.core.combat.now() - 1
    assert sim.travel_refusal(caller.session, door) is None
    assert not truce.hunted(caller.session.player_id)


def test_killing_the_guards_does_not_end_the_answer(repo_root, monkeypatch):
    game, caller, truce, sim, door = row(repo_root, monkeypatch)
    guard = shoot_an_npc(game, caller)
    game.core.world.leave(guard)
    assert truce.hunted(caller.session.player_id)
    assert 'Try me in' in sim.travel_refusal(caller.session, door)


def test_the_longer_of_mark_and_answer_wins(repo_root, monkeypatch):
    game, caller, truce, sim, door = row(repo_root, monkeypatch)
    shoot_an_npc(game, caller)
    truce.breakers[caller.session.player_id] = game.core.combat.now() + 14*60 - 5
    assert sim.travel_refusal(caller.session, door) == (
        'The bouncer looks at your red name. "Not tonight. Not after the Row. 14 min."')
    truce.breakers[caller.session.player_id] = game.core.combat.now() + 30
    assert 'Try me in 5 min' in sim.travel_refusal(caller.session, door)


def test_a_time_under_a_minute_never_says_zero(repo_root, monkeypatch):
    game, caller, truce, sim, door = row(repo_root, monkeypatch)
    truce.breakers[caller.session.player_id] = game.core.combat.now() + 1
    assert '1 min' in sim.travel_refusal(caller.session, door)


def test_the_plainclothes_warden_does_not_change_being_hunted(repo_root, monkeypatch):
    game, caller, truce, sim, door = row(repo_root, monkeypatch)
    spawn(game, 'sodium-row', 'npc-row-enforcer', (62, 12), group='enforcers')
    spawn(game, 'sodium-row', 'npc-plainclothes-warden', (61, 13), group='plainclothes-warden')
    pid = caller.session.player_id
    game.core.npcs.provocations[('sodium-row', 'plainclothes-warden', pid)] = game.core.combat.now() + 300
    assert not truce.hunted(pid)
    assert sim.travel_refusal(caller.session, door) is None


def test_shooting_the_warden_is_answered_like_shooting_a_regular(repo_root, monkeypatch):
    results = []
    for key in ('npc-plainclothes-warden', 'npc-sodium-regular'):
        game, caller, truce, sim, door = row(repo_root, monkeypatch)
        spawn(game, 'sodium-row', 'npc-row-enforcer', (62, 12), group='enforcers')
        target = spawn(game, 'sodium-row', key, (61, 13), group='street')
        game.core.combat.exchange(body(game, caller), target)
        results.append((truce.hunted(caller.session.player_id), sim.travel_refusal(caller.session, door)))
    assert results[0] == results[1] and results[0][0] is True


def me_views(game, caller):
    return [f.data['body']['me'] for f in game.frames_for(caller)
            if f.type == 'view' and isinstance(f.data.get('body', {}).get('me'), dict)]


def test_the_view_declares_hunted(repo_root, monkeypatch):
    game, caller, truce, sim, door = row(repo_root, monkeypatch)
    game.step(2)
    assert me_views(game, caller)[-1]['hunted'] is False
    shoot_an_npc(game, caller)
    game.step(2)
    assert me_views(game, caller)[-1]['hunted'] is True


def toasts(game, caller):
    return [f.data['text'] for f in game.frames_for(caller) if f.type == 'toast']


def test_first_arrival_gets_the_price_once(repo_root, monkeypatch):
    game, caller = boot(repo_root, monkeypatch)
    avatar = game.core.characters.sim.avatars[caller.session.user_id]
    game.frames_for(caller)
    place(game, caller, 'sodium-row', (60, 12))
    game.core.characters.sim.discover(caller.session, avatar)
    line = 'Fire: Sable comes, no Halo. At a player: Marked 15m, no work.'
    assert toasts(game, caller).count(line) == 1
    game.core.characters.sim.discover(caller.session, avatar)
    assert toasts(game, caller).count(line) == 0


def test_the_notice_lines_fit_their_limits():
    assert len('Fire: Sable comes, no Halo. At a player: Marked 15m, no work.') <= 63


def test_vesper_board_closes_to_a_marked_player_and_says_how_long(repo_root, monkeypatch):
    game, caller = boot(repo_root, monkeypatch)
    place(game, caller, 'sodium-tin-halo', (9, 7))  # beside the contract board at (9, 6)
    panels = game.core.contracts.panels
    player = game.core.characters.players[caller.session.player_id]
    assert panels.station(caller.session, 'halo-contract-board') == 'vesper'
    player.marked_until = datetime.fromtimestamp(game.core.combat.now() + 14*60 - 5, timezone.utc).isoformat()
    with pytest.raises(ValueError, match='Come back in 14 min'):
        panels.station(caller.session, 'halo-contract-board')


def test_an_npc_attack_leaves_vesper_open(repo_root, monkeypatch):
    game, caller, truce, sim, door = row(repo_root, monkeypatch)
    shoot_an_npc(game, caller)
    truce.vesper_refuses(caller.session.player_id)  # raises nothing


def test_enforcers_talk_and_stay_security(repo_root, monkeypatch):
    game, caller, truce, sim, door = row(repo_root, monkeypatch)
    guard = spawn(game, 'sodium-row', 'npc-row-enforcer', (61, 12), group='enforcers')
    assert game.core.dialogue.contact(caller.session, guard.id) is not None
    assert presentation.true_class(guard, game.core.world.content) == 'security'


def test_vesper_offers_hide_from_the_marked(repo_root):
    content = load_content(repo_root/'src/blacksite/content')
    gated = [o for o in content.dialogue['vesper'].offers if o.kind in ('contract', 'vendor')]
    assert gated and all('not_marked' in o.when for o in gated)


def test_the_alley_door_says_what_it_is(repo_root, monkeypatch):
    game, caller, truce, sim, door = row(repo_root, monkeypatch, tile=(89, 24))
    seen = []
    demo_doors.install(game.core, lambda message, **fields: seen.append(fields))
    avatar = sim.avatars[caller.session.user_id]
    choice = sim.interaction_target(avatar)
    assert choice.focus.label == "The Halo's back door" and len(choice.focus.label) <= 21
    act(game, caller, Frame('key', {'k': 'e', 't': 0}))
    game.step()
    assert 'No handle this side.' in [line.get('text', '') for line in caller.session.log_ring]
    assert seen[-1]['exit'] == 'row-halo-back-door' and seen[-1]['outcome'] == 'No handle this side.'
    assert avatar.zone == 'sodium-row'


def killed_and_back(game, caller):
    player = game.core.characters.players[caller.session.player_id]
    game.core.combat.respawn(player, body(game, caller))
    game.commit_commerce()
    game.step()
    return player


def test_dying_settles_the_debt_with_the_keeper(repo_root, monkeypatch):
    game, caller, truce, sim, door = row(repo_root, monkeypatch)
    guard = shoot_an_npc(game, caller)
    assert truce.hunted(caller.session.player_id)
    killed_and_back(game, caller)
    assert not truce.hunted(caller.session.player_id)
    assert sim.travel_refusal(caller.session, door) is None
    assert not game.core.npcs.hostile(guard, body(game, caller))
    said = [line.get('text', '') for line in caller.session.log_ring]
    assert 'Sable considers it settled.' in said
    assert said.index('Sable considers it settled.') > next(i for i, t in enumerate(said) if t.startswith('You wake'))


def test_a_clean_respawn_says_nothing_about_sable(repo_root, monkeypatch):
    game, caller, truce, sim, door = row(repo_root, monkeypatch)
    killed_and_back(game, caller)
    assert not any('settled' in line.get('text', '') for line in caller.session.log_ring)


def test_dying_does_not_settle_a_mark(repo_root, monkeypatch):
    game, caller, truce, sim, door = row(repo_root, monkeypatch)
    guard = shoot_an_npc(game, caller)
    player = game.core.characters.players[caller.session.player_id]
    now = game.core.combat.now()
    until = datetime.fromtimestamp(now + 14*60 - 5, timezone.utc).isoformat()
    player.marked_until = until
    body(game, caller).marked = True
    truce.breakers[player.id] = now + 14*60 - 5
    killed_and_back(game, caller)
    assert player.marked_until == until
    assert 'Sable considers it settled. The Mark stays.' in [line.get('text', '') for line in caller.session.log_ring]
    assert 'Not after the Row. 14 min' in sim.travel_refusal(caller.session, door)
    with pytest.raises(ValueError, match='Come back in 14 min'):
        truce.vesper_refuses(player.id)
    # The keeper is finished with them; the Mark's open season is someone else's.
    assert not truce.hunted(player.id)
    assert not game.core.npcs.hostile(guard, body(game, caller))
