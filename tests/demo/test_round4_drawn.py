"""Round4 decisions #185: inputs, warning credit, watch and cover parity."""

from dataclasses import replace

import pytest

from karst41.server.dialogue import eligible_offers
from karst41.server.dialogue import Facts
from karst41.content.schema import Offer
from scripts.demo_sodium.content import load_demo_content
from karst41.server.protocol import Frame
from tests.character_helpers import act, place
from tests.demo.test_truce_standin import boot, body, spawn, two_players


def row(repo_root, monkeypatch):
    game, caller = boot(repo_root, monkeypatch)
    place(game, caller, 'sodium-row', (60, 12))
    return game, caller, body(game, caller), game.core.demo_weapons


def test_first_fire_draws_without_a_target_or_ammo_spent(repo_root, monkeypatch):
    game, caller, actor, drawn = row(repo_root, monkeypatch)
    inventory = {i.id: i.stack for i in game.core.commerce.items.values()}
    drawn.combat.fire(actor.id)
    assert drawn.drawn(actor)
    assert not game.core.commerce.pending
    assert {i.id: i.stack for i in game.core.commerce.items.values()} == inventory
    assert not actor.marked and not game.core.npcs.provocations
    assert actor.stance == 'normal'


def test_witness_credit_requires_two_seconds_and_no_second_warning(repo_root, monkeypatch):
    game, caller, actor, drawn = row(repo_root, monkeypatch)
    other = spawn(game, 'sodium-row', 'npc-sodium-regular', (61, 13), group='regular')
    drawn.draw(actor)
    start = game.clock.now_tick()
    assert other.id in drawn.draws[actor.id].witnesses
    assert drawn.warn(actor, other, start + 19) is False
    assert drawn.warn(actor, other, start + 20) is True
    assert not any('raises a weapon at you' in line['text'] for line in caller.session.log_ring)


def test_real_fire_path_waits_then_settles_one_shot(repo_root, monkeypatch):
    game, caller, actor, drawn = row(repo_root, monkeypatch)
    other = spawn(game, 'sodium-row', 'npc-sodium-regular', (61, 13), group='regular')
    drawn.combat.fire(actor.id, other.id)
    assert drawn.drawn(actor)
    drawn.combat.fire(actor.id, other.id)
    assert actor.cooldowns.get('weapon', 0) <= game.clock.now_tick()
    assert not game.core.commerce.pending
    game.step(20)
    drawn.combat.fire(actor.id, other.id)
    game.commit_commerce()
    assert actor.cooldowns['weapon'] > game.clock.now_tick()
    assert drawn.combat.warnings[actor.id, other.id] == drawn.draws[actor.id].tick


def test_drawn_offers_close_except_the_authored_vesper_exception():
    content = load_demo_content()
    vesper = content.dialogue['vesper']
    assert vesper.drawn_open and eligible_offers(vesper, Facts(drawn=True))
    regular = replace(content.dialogue['row-street-regular'], offers=(Offer('vendor', 'Trade', 'v', 'vesper'),))
    assert eligible_offers(regular, Facts())
    assert not eligible_offers(regular, Facts(drawn=True))
    assert not eligible_offers(regular, Facts(provoked=True))


def test_late_target_still_gets_a_per_target_warning(repo_root, monkeypatch):
    game, caller, actor, drawn = row(repo_root, monkeypatch)
    drawn.draw(actor)
    game.step(21)
    other = spawn(game, 'sodium-row', 'npc-sodium-regular', (61, 13), group='late')
    now = game.clock.now_tick()
    assert not drawn.warn(actor, other, now)
    assert drawn.combat.warnings[actor.id, other.id] == now
    assert not drawn.warn(actor, other, now + 19)
    assert drawn.warn(actor, other, now + 20)


def test_zone_entry_cannot_reuse_the_draw_or_an_old_warning(repo_root, monkeypatch):
    game, caller, actor, drawn = row(repo_root, monkeypatch)
    other = spawn(game, 'sodium-row', 'npc-sodium-regular', (61, 13), group='regular')
    drawn.draw(actor)
    start = game.clock.now_tick()
    assert drawn.warn(actor, other, start + 20)
    place(game, caller, 'core-plaza', (5, 3))
    place(game, caller, 'sodium-row', (60, 12))
    assert drawn.drawn(actor)
    assert not drawn.warn(actor, other, game.clock.now_tick())


def test_one_watcher_per_zone_and_immediate_transfer(repo_root, monkeypatch):
    game, caller, second, actor, peer = two_players(repo_root, monkeypatch)
    drawn = game.core.demo_weapons
    one = spawn(game, 'sodium-row', 'npc-row-enforcer', (64, 12), group='watch-one')
    two = spawn(game, 'sodium-row', 'npc-row-enforcer', (65, 13), group='watch-two')
    drawn.draw(actor)
    drawn.draw(peer)
    watch = drawn.watchers['sodium-row']
    assert watch.player == actor.id
    assert len(drawn.watchers) == 1
    assert sum(w.guard in (one.id, two.id) for w in drawn.watchers.values()) == 1
    drawn.holster(actor)
    assert drawn.watchers['sodium-row'].player == peer.id
    assert drawn.watchers['sodium-row'].guard == watch.guard
    assert not actor.marked
    assert any('Better.' in line['text'] for line in caller.session.log_ring)


def test_watcher_stops_three_tiles_away_without_attacking(repo_root, monkeypatch):
    game, caller, actor, drawn = row(repo_root, monkeypatch)
    guard = spawn(game, 'sodium-row', 'npc-row-enforcer', (66, 12), group='watch')
    hp = actor.health
    drawn.draw(actor)
    game.step(50)
    assert 2 <= drawn.distance(guard, actor) <= 4
    assert guard.target is None and actor.health == hp
    assert not game.core.npcs.provocations
    drawn.holster(actor)
    game.step(51)
    assert 'sodium-row' not in drawn.watchers


def test_drawn_refuses_halo_and_holster_opens_it(repo_root, monkeypatch):
    game, caller, actor, drawn = row(repo_root, monkeypatch)
    door = next(e for e in game.core.world.zones['sodium-row'].template.meta.exits
                if e.target_zone == 'sodium-tin-halo')
    drawn.draw(actor)
    assert 'Put it away first.' in drawn.sim.travel_refusal(caller.session, door)
    drawn.holster(actor)
    assert drawn.sim.travel_refusal(caller.session, door) is None


def test_jack_and_down_clear_transient_draw_state(repo_root, monkeypatch):
    game, caller, actor, drawn = row(repo_root, monkeypatch)
    for stance in ('jacked', 'down', 'dead', 'sleeper'):
        actor.stance = 'normal'
        drawn.draw(actor)
        actor.stance = stance
        drawn.refresh(game.clock.now_tick())
        assert not drawn.drawn(actor) and actor.id not in drawn.draws


def test_toggle_key_works_in_both_keymaps(repo_root, monkeypatch):
    game, caller, actor, drawn = row(repo_root, monkeypatch)
    for keymap, key in [('arrows', 'D'), ('vi', 'd')]:
        caller.session.keymap_id = keymap
        act(game, caller, Frame('key', {'k': key, 't': 0}))
        assert drawn.drawn(actor)
        act(game, caller, Frame('key', {'k': key, 't': 0}))
        assert not drawn.drawn(actor)


def test_fleeing_contact_never_opens_a_page_and_deduplicates(repo_root, monkeypatch):
    game, caller, actor, drawn = row(repo_root, monkeypatch)
    other = spawn(game, 'sodium-row', 'npc-sodium-regular', (61, 13), group='regular')
    other.behaviour['state'] = 'flee'
    dialogue = game.core.dialogue
    contact = next(c for c in dialogue.contacts(game.core.world.zones['sodium-row']) if c.target == other.id)
    for _ in range(3):
        dialogue.open(caller.session, contact, game.clock.now_tick())
    assert caller.session.id not in dialogue.menus
    assert sum(line['text'] == "Sodium regular won't stop." for line in caller.session.log_ring) == 1


def test_provoked_facts_use_only_reaction_group(repo_root, monkeypatch):
    game, caller, actor, drawn = row(repo_root, monkeypatch)
    regular = spawn(game, 'sodium-row', 'npc-sodium-regular', (61, 13), group='regular')
    warden = spawn(game, 'sodium-row', 'npc-plainclothes-warden', (62, 13), group='warden')
    zone = game.core.world.zones['sodium-row']
    zone.template = replace(zone.template, meta=replace(zone.template.meta, spawners=tuple(
        replace(s, poses_as='regular') if s.id == 'warden' else s for s in zone.template.meta.spawners)))
    game.core.npcs.provocations['sodium-row', 'regular', actor.id] = game.core.combat.now() + 300
    dialogue = game.core.dialogue
    facts = [dialogue.facts(caller.session, dialogue.content.dialogue[c.talker], c)
             for c in dialogue.contacts(zone) if c.target in (regular.id, warden.id)]
    assert len(facts) == 2 and all(f.provoked for f in facts)
    assert all(not eligible_offers(dialogue.content.dialogue['row-street-regular'], f) for f in facts)


def test_drawn_frame_preserves_stance_and_map_glyph(repo_root, monkeypatch):
    game, caller, second, actor, peer = two_players(repo_root, monkeypatch)
    drawn = game.core.demo_weapons
    drawn.draw(actor)
    peer.target = actor.id
    target = drawn.sim.target_provider(peer)
    assert target['drawn'] is True and target['stance'] == 'normal'
    assert drawn.sim.me_provider(caller.session)['drawn'] is True
    game.step(2)
    frames = game.frames_for(second)
    body_ = next(f.data['body'] for f in reversed(frames) if f.type == 'view' and f.data.get('kind') == 'zone')
    entry = next(a for a in body_['actors'] if a['id'] == actor.id)
    nearby = next(a for a in body_['nearby'] if a['id'] == actor.id)
    assert nearby['drawn'] is True and entry['glyph_id'] == 'actor-player'


@pytest.mark.parametrize("approach", [(62, 12), (62, 11)])
def test_watcher_keeps_room_when_the_drawer_approaches(repo_root, monkeypatch, approach):
    game, caller, actor, drawn = row(repo_root, monkeypatch)
    guard = spawn(game, 'sodium-row', 'npc-row-enforcer', (63, 12), group='watch')
    drawn.draw(actor)
    place(game, caller, 'sodium-row', approach)
    hp = actor.health
    game.step(15)
    assert 2 <= drawn.distance(guard, actor) <= 4
    assert guard.target is None and actor.health == hp
    assert not game.core.npcs.provocations
