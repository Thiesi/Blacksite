"""Round 4 movement budgets, swapped homes, talk reach and shared shy steps."""

from dataclasses import replace

from karst41.content.schema import Post, Spawner
from tests.character_helpers import place
from tests.demo.test_truce_standin import body, boot


def rig(repo_root, monkeypatch):
    game, caller = boot(repo_root, monkeypatch)
    zone = game.core.world.zones['sodium-row']
    zone.template = replace(zone.template, meta=replace(zone.template.meta, moving_budget=4))
    return game, caller, zone, game.core.npcs.posts


def add(game, zone, sid, homes, errands=(), *, npc='npc-sodium-regular', crowd=None, seated=False, swap=False):
    posts = tuple(Post(tile, home=True, seated=seated and index == 0, swap=swap)
                  for index, tile in enumerate(homes)) + tuple(Post(tile) for tile in errands)
    spec = Spawner(sid, npc, len(homes), 60, posts=posts, crowd=crowd)
    zone.template = replace(zone.template, meta=replace(zone.template.meta,
        spawners=zone.template.meta.spawners + (spec,)))
    game.core.npcs.spawners.process(zone, game.core.combat.now())
    actors = [a for a in zone.actors.values() if a.behaviour.get('spawner') == sid]
    for actor in actors:
        actor.behaviour['post_until'] = 0
    return actors


def test_holding_never_draws_rng_or_moves(repo_root, monkeypatch):
    game, _, zone, posts = rig(repo_root, monkeypatch)
    actor, = add(game, zone, 'still', [(20, 12)], [(25, 12)])
    actor.behaviour['post_until'] = 1000
    def forbidden(*args, **kwargs):
        raise AssertionError('holding must not draw randomness')
    monkeypatch.setattr(zone.rng, 'randint', forbidden)
    monkeypatch.setattr(zone.rng, 'choices', forbidden)
    before = actor.position
    for tick in range(100):
        posts.act(actor, zone, tick, set())
    assert actor.position == before


def test_zone_budget_includes_paused_trips_and_shy_steps(repo_root, monkeypatch):
    game, caller, zone, posts = rig(repo_root, monkeypatch)
    actors = [add(game, zone, f'crowd-{i}', [(20+i*3, 12)], [(20+i*3, 20)])[0] for i in range(6)]
    for actor in actors:
        posts.act(actor, zone, 10, set())
    assert sum(bool(a.behaviour.get('post_trip')) for a in actors) == 4
    paused = actors[0]
    place(game, caller, zone.id, (paused.x, paused.y+1))
    before = paused.position
    posts.act(paused, zone, 20, set())
    assert paused.position == before and paused.id in posts.reserved_ids(zone, 20)
    drawer = body(game, caller)
    drawer.behaviour['drawn'] = True
    shy = actors[-1]
    before = shy.position
    assert posts.shy(shy, zone, 20, drawer, set())
    assert shy.position == before and len(posts.reserved_ids(zone, 20)) == 4


def test_swap_reserves_two_slots_and_exchanges_homes_atomically(repo_root, monkeypatch):
    game, _, zone, posts = rig(repo_root, monkeypatch)
    pair = add(game, zone, 'bar', [(27, 4), (34, 9)], seated=True, swap=True)
    seat = next(a for a in pair if posts.post_at(a, a.position).seated)
    partner = next(a for a in pair if a is not seat)
    original = seat.position, partner.position
    busy = [add(game, zone, f'busy-{i}', [(20+i*2, 12)])[0] for i in range(3)]
    for actor in busy:
        posts.start(actor, (actor.x, 20))
    posts.act(seat, zone, 10, set())
    assert (posts.home(seat), posts.home(partner)) == original
    assert not seat.behaviour.get('post_trip') and not partner.behaviour.get('post_trip')
    busy[-1].behaviour['post_trip'] = False
    posts.act(seat, zone, 11, set())
    assert (posts.home(seat), posts.home(partner)) == original[::-1]
    assert seat.behaviour['post_trip'] and partner.behaviour['post_trip']
    assert len(posts.reserved_ids(zone, 11)) == 4
    assert partner.behaviour['post_wait'] == seat.id
    doorway_position = partner.position
    posts.act(partner, zone, 12, set())
    assert partner.position == doorway_position
    for tick in range(12, 250):
        for actor in pair:
            posts.act(actor, zone, tick, game.core.npcs.spawners.reserved(zone))
    assert seat.position == original[1] and partner.position == original[0]
    assert not seat.behaviour['post_trip'] and not partner.behaviour['post_trip']


def test_warden_uses_its_counterparts_crowd_slot(repo_root, monkeypatch):
    game, _, zone, posts = rig(repo_root, monkeypatch)
    regular, = add(game, zone, 'regular', [(30, 12)], [(30, 20)], crowd='middle')
    warden, = add(game, zone, 'cover', [(32, 12)], [(32, 20)], npc='npc-plainclothes-warden', crowd='middle')
    posts.act(regular, zone, 1, set())
    posts.act(warden, zone, 1, set())
    assert regular.behaviour['post_trip']
    assert not warden.behaviour.get('post_trip')
    assert posts.reserved_ids(zone, 1) == {regular.id}


def test_shy_is_one_step_and_seats_stay_put(repo_root, monkeypatch):
    game, caller, zone, posts = rig(repo_root, monkeypatch)
    actor, = add(game, zone, 'street', [(30, 12)])
    seated, = add(game, zone, 'seat', [(30, 14)], seated=True)
    place(game, caller, zone.id, (28, 12))
    drawer = body(game, caller)
    drawer.behaviour['drawn'] = True
    before = actor.position
    posts.shy(actor, zone, 100, drawer, set())
    assert abs(actor.x-before[0]) + abs(actor.y-before[1]) == 1
    assert posts.reserved_ids(zone, 100) == {actor.id}
    after = actor.position
    posts.shy(actor, zone, 110, drawer, set())
    assert actor.position == after
    posts.shy(seated, zone, 110, drawer, set())
    assert seated.position == (30, 14)


def test_talk_reach_pauses_start_and_flight_returns_home(repo_root, monkeypatch):
    game, caller, zone, posts = rig(repo_root, monkeypatch)
    actor, = add(game, zone, 'street', [(30, 12)], [(30, 20)])
    place(game, caller, zone.id, (29, 12))
    before = actor.position
    posts.act(actor, zone, game.clock.now_tick(), set())
    assert actor.position == before and not actor.behaviour.get('post_trip')
    place(game, caller, 'core-plaza', (15, 10))
    game.core.world.enter(actor, zone.id, (30, 18))
    posts.interrupt(actor)
    for tick in range(100, 160):
        posts.act(actor, zone, tick, set())
    assert actor.position == posts.home(actor) == (30, 12)
    assert not actor.behaviour['post_trip']


def test_drawer_cannot_pin_the_shy_step_with_talk_reach(repo_root, monkeypatch):
    game, caller, zone, posts = rig(repo_root, monkeypatch)
    actor, = add(game, zone, 'street', [(30, 12)])
    place(game, caller, zone.id, (29, 12))
    drawer = body(game, caller)
    drawer.behaviour['drawn'] = True
    before = actor.position
    posts.shy(actor, zone, 100, drawer, set())
    assert actor.position != before


def test_shying_cancels_a_counter_hold_and_returns_home(repo_root, monkeypatch):
    game, caller, zone, posts = rig(repo_root, monkeypatch)
    actor, = add(game, zone, 'street', [(30, 12)], [(30, 18)])
    game.core.world.enter(actor, zone.id, (30, 18))
    actor.behaviour['post_until'] = 10000
    place(game, caller, zone.id, (28, 18))
    drawer = body(game, caller)
    drawer.behaviour['drawn'] = True
    posts.shy(actor, zone, 100, drawer, set())
    assert actor.behaviour['post_goal'] == (30, 12)
    assert posts.reserved_ids(zone, 100) == {actor.id}
    for tick in range(101, 130):
        posts.shy(actor, zone, tick, drawer, set())
    assert actor.position == (30, 12)


def test_arrival_keeps_its_step_in_this_ticks_budget(repo_root, monkeypatch):
    game, _, zone, posts = rig(repo_root, monkeypatch)
    zone.template = replace(zone.template, meta=replace(zone.template.meta, moving_budget=1))
    first, = add(game, zone, 'first', [(20, 12)], [(21, 12)])
    second, = add(game, zone, 'second', [(25, 12)], [(26, 12)])
    posts.start(first, (21, 12))
    posts.act(first, zone, 100, set())
    assert first.position == (21, 12) and not first.behaviour['post_trip']
    posts.act(second, zone, 100, set())
    assert second.position == (25, 12)
    assert posts.reserved_ids(zone, 100) == {first.id}
    posts.act(second, zone, 101, set())
    assert second.position == (26, 12)


def test_interrupted_swap_preserves_new_homes_and_releases_waiter(repo_root, monkeypatch):
    game, _, zone, posts = rig(repo_root, monkeypatch)
    pair = add(game, zone, 'bar', [(27, 4), (34, 9)], seated=True, swap=True)
    seat = next(a for a in pair if posts.post_at(a, a.position).seated)
    partner = next(a for a in pair if a is not seat)
    homes = posts.home(seat), posts.home(partner)
    posts.act(seat, zone, 10, set())
    assert partner.behaviour.get('post_wait') == seat.id
    posts.interrupt(seat)
    assert 'post_wait' not in partner.behaviour
    assert (posts.home(seat), posts.home(partner)) == homes[::-1]


def test_holstering_allows_a_later_draw_to_shy_again(repo_root, monkeypatch):
    game, caller, zone, posts = rig(repo_root, monkeypatch)
    actor, = add(game, zone, 'street', [(30, 12)])
    place(game, caller, zone.id, (28, 12))
    drawer = body(game, caller)
    drawer.behaviour['drawn'] = True
    posts.shy(actor, zone, 100, drawer, set())
    before = actor.position
    drawer.behaviour['drawn'] = False
    posts.act(actor, zone, 101, set())
    drawer.behaviour['drawn'] = True
    posts.shy(actor, zone, 110, drawer, set())
    assert actor.position != before
