"""S25b: retained #66 engineering probes; new homes stay with C1/S25c."""

from collections import deque
from copy import deepcopy
from itertools import combinations
from pathlib import Path
from random import Random
from typing import Any

import pytest

from blacksite.content.loader import ContentTree, load_content
from blacksite.content.schema import Region, Tile, Zone
from blacksite.content.validate import validate
from blacksite.server.protocol import Frame
from scripts import build_city_content as author
from tests.character_helpers import act, create, place
from tests.harness import HeadlessServer


@pytest.fixture(scope='module')
def city_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp('commissioned-city')
    author.build(path)
    return path


@pytest.fixture(scope='module')
def city(city_path: Path) -> ContentTree:
    return load_content(city_path)


def reachable(city: ContentTree, zone: Zone, blocked: set[Tile]) -> set[Tile]:
    start = zone.meta.spawn
    assert start is not None
    seen, pending = {start}, deque([start])
    while pending:
        x, y = pending.popleft()
        for tile in ((x-1, y), (x+1, y), (x, y-1), (x, y+1)):
            tid = zone.tile_at(tile)
            if tid is not None and tile not in seen and tile not in blocked:
                definition = city.tiles[tid]
                if definition.passable and not definition.hazard:
                    seen.add(tile)
                    pending.append(tile)
    return seen


def test_game_5_1_complete_city_matches_exact_gazetteer_sizes_and_return_exits(city: ContentTree) -> None:
    assert validate(city) == []
    expected = author.gazetteer()
    assert set(city.zones) == set(expected)
    assert len(city.zones) == 34 and len(city.sectors) == 11
    assert 'blacksite-l1' not in city.zones
    for zid, zone in city.zones.items():
        assert (zone.width, zone.height) == (expected[zid]['width'], expected[zid]['height']), zid
        assert {ex.target_zone for ex in zone.meta.exits} >= set(expected[zid]['neighbours']), zid
        for ex in zone.meta.exits:
            assert any(back.target_zone == zid for back in city.zones[ex.target_zone].meta.exits), (zid, ex.id)
        assert not any(obj.params.get('unavailable_target') for obj in zone.meta.objects), zid


def test_s25b_exit_markers_and_corrected_geographic_anchors(city: ContentTree) -> None:
    for zone in city.zones.values():
        for ex in zone.meta.exits:
            assert zone.tile_at(ex.tile) == ('floor' if ex.hidden else 'exit'), (zone.id, ex.id)
    ring = {o.id: o for o in city.zones['scour-ring-4'].meta.objects}
    assert ring['season-artifact-west'].tile[0] < ring['season-artifact-east'].tile[0]
    foot = city.zones['under-shaft-foot']
    objects = {o.id: o for o in foot.meta.objects}
    assert objects['shaft-cage-lift'].kind == 'lift'
    cage_exit = next(ex for ex in foot.meta.exits if ex.target_zone == 'spire-shaft-head')
    assert objects['shaft-cage-lift'].tile == cage_exit.tile
    assert not city.tiles[foot.tile_at(cage_exit.tile)].hazard
    season = objects['season-door'].tile
    assert objects['season-door'].kind == 'descent_console' and season[1] > foot.height*3//4
    for oid in ('choir-shrine', 'halvard-marker'):
        assert sum(abs(a-b) for a, b in zip(objects[oid].tile, season)) <= 2
    main = city.zones['oldworks-main']
    drop = next(ex for ex in main.meta.exits if ex.target_zone == 'oldworks-drop')
    assert drop.hidden and drop.tile[1] > main.height//2


def test_s25b_preserves_s08_terrain_hardware_and_deferred_homes(city: ContentTree) -> None:
    baseline = load_content(author.SHIPPED)
    for zid in author.read(author.SHIPPED/'bundles/m1-zone-preview.json')['members']['zones']:
        before, after = baseline.zones[zid], city.zones[zid]
        markers = {ex.tile: 'floor' if ex.hidden else 'exit' for ex in after.meta.exits}
        for y, row in enumerate(before.grid):
            for x, tile in enumerate(row):
                assert after.tile_at((x, y)) == markers.get((x, y), tile), (zid, x, y)
        objects = {o.id: o for o in after.meta.objects}
        for obj in before.meta.objects:
            if obj.kind == 'hardware':
                assert objects[obj.id].params.get('name') == obj.params.get('name'), (zid, obj.id)
            elif obj.kind == 'apartment_door':
                assert objects[obj.id] == obj
    assert len(city.sectors['lat-terraces'].cells) == 36
    assert not any(obj.housing for zone in city.zones.values() for obj in zone.meta.objects)
    assert city.cores['lat-outworks-seal'].tier == baseline.cores['lat-outworks-seal'].tier == 5


def test_s25b_gate_nine_binding_covers_restored_landing_route(city: ContentTree) -> None:
    wall = city.zones['tramyard-wall-gate']
    landing = city.zones['scour-landing']
    exits = {ex.target_zone: ex for ex in wall.meta.exits}
    assert exits[landing.id].kind == 'gate'
    assert any(ex.target_zone == wall.id for ex in landing.meta.exits)
    panel = next(o for o in wall.meta.objects if o.id == 'gatehouse-east-gate-nine-outbound')
    assert panel.kind == 'gate'
    assert set(panel.params['exits']) == {exits['scour-ring-1'].id, exits[landing.id].id}


def test_game_5_1_every_public_anchor_has_a_route_outside_private_rooms_and_hazards(city: ContentTree) -> None:
    hubs = set(author.read(author.SHIPPED/'bundles/m1-zone-preview.json')['members']['zones'])
    for zid, zone in city.zones.items():
        private = {tile for obj in zone.meta.objects if obj.housing
                   for tile in Region(*obj.housing.origin, 6, 4).tiles()}
        closed = {obj.tile for obj in zone.meta.objects if obj.params.get('locked')}
        # Check the worst combination of every authored blocking layout,
        # rather than testing each service only while the others are idle.
        blocking = {change.tile for layout in zone.meta.layouts for change in layout.changes
                    if not city.tiles[change.tile_id].passable or city.tiles[change.tile_id].hazard}
        base = reachable(city, zone, private | closed)
        seen = reachable(city, zone, private | closed | blocking)
        for ex in zone.meta.exits:
            assert ex.tile in seen or any((ex.tile[0]+dx, ex.tile[1]+dy) in seen
                for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0))), (zid, ex.id)
        for obj in zone.meta.objects:
            # A running gantry may make its own machine inaccessible.
            # Its hardware, services and outward paths must stay reachable.
            public = obj.essential or obj.kind in ('hardware', 'vendor', 'bank', 'apartment_door', 'workshop')
            if zid in hubs and not public:
                continue  # S08 decorative/controlled rooms retain C1's geometry gate.
            routes = seen if public else base
            assert obj.tile in routes or any((obj.tile[0]+dx, obj.tile[1]+dy) in routes
                for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0))), (zid, obj.id)


def test_game_5_5_spawner_pads_and_patrols_have_an_ordinary_public_escape(city: ContentTree) -> None:
    for zid, zone in city.zones.items():
        blocked = {obj.tile for obj in zone.meta.objects if obj.params.get('locked')}
        seen = reachable(city, zone, blocked)
        for spawner in zone.meta.spawners:
            candidates = spawner.region.tiles() if spawner.region else [spawner.tile]
            for tile in candidates:
                if tile is not None and tile not in blocked:
                    definition = city.tiles[zone.tile_at(tile)]
                    if definition.passable and not definition.hazard:
                        assert tile in seen, (zid, spawner.id, tile, 'sealed spawn room')
            for behaviour in city.npcs[spawner.npc].behaviours:
                for point in behaviour.params.get('waypoints', ()):
                    assert tuple(point) in seen, (zid, spawner.id, point, 'sealed patrol route')


def test_game_7_7_all_16_relays_and_ordinary_cores_use_live_hardware(city: ContentTree) -> None:
    assert len(city.relays) == 16
    for rid, relay in city.relays.items():
        assert city.active('relays', rid)
        terminal = next(obj for obj in city.zones[relay.zone].meta.objects if obj.id == relay.terminal)
        assert terminal.params['relay'] == rid and terminal.params['vendor'] == relay.vendor
        assert city.active('vendors', relay.vendor) and city.active('cores', relay.core)
    for cid, core in city.cores.items():
        if core.template or core.training:
            continue
        assert city.active('cores', cid), cid
        assert len(core.hardware) == (2 if cid == 'lat-shaft' else 1), cid
        for hardware in core.hardware:
            obj = next(obj for obj in city.zones[hardware.zone].meta.objects if obj.id == hardware.object_id)
            assert obj.tile == hardware.tile and obj.params['core'] == cid, cid


def test_game_5_5_shaft_patrols_cannot_seal_the_public_hardware_alcove(city: ContentTree) -> None:
    zone = city.zones['spire-shaft-head']
    hardware = next(obj for obj in zone.meta.objects if obj.id == 'shaft-hardware')
    # Both shipped heavies patrol the same narrow approach. They can meet
    # nose to nose, so an admitted caller needs room to walk past them.
    patrol = city.npcs['npc-halvard-heavy-spire-shaft-head'].behaviours[0]
    assert patrol.params['waypoints'] == [[15, 25], [23, 25]]
    for occupied in combinations(((x, 25) for x in range(15, 24)), 2):
        seen = reachable(city, zone, set(occupied))
        assert any((hardware.tile[0]+dx, hardware.tile[1]+dy) in seen
                   for dx, dy in ((0, 0), (0, 1), (0, -1), (1, 0), (-1, 0))), occupied


def test_game_5_5_hostile_shaft_crew_does_not_injure_itself_before_callers_arrive(city: ContentTree) -> None:
    game = HeadlessServer(deepcopy(city), character_state={})
    caller = game.connect()
    create(game, caller)
    zone = game.core.world.zones['under-shaft-foot']
    zone.activate('cohort-acceptance', game.clock.now_tick())
    game.step(30)
    crew = [actor for actor in zone.actors.values()
            if actor.behaviour.get('spawner') == 'old-maintenance-crew']
    assert len(crew) == 4
    siblings = {actor.id for actor in crew}
    assert all(actor.target not in siblings and actor.health == actor.health_max for actor in crew)
    # They remain a live threat to a nearby intruder. Move through the
    # headless world's normal admission helper, without altering NPCs.
    origin = crew[0].position
    approach = game.core.world.free_tile(zone.id, (origin[0], origin[1]-2))
    place(game, caller, zone.id, approach)
    game.commit_commerce()
    game.step(6)
    assert any(actor.target == caller.session.player_id for actor in crew)




def test_game_8_2_halls_have_public_care_bank_vat_and_actual_member_counter(city: ContentTree) -> None:
    assert len(city.faction_sites) == 8
    for site in city.faction_sites.values():
        assert city.active('faction_sites', site.id)
        zone = city.zones[site.hall]
        assert any(obj.params.get('vendor') == site.vendor for obj in zone.meta.objects), site.id
        assert any(obj.kind == 'bank' for obj in zone.meta.objects), site.id
        clinics = [obj for obj in zone.meta.objects if obj.params.get('vendor') == 'sablier-clinic']
        assert clinics and all(obj.essential for obj in clinics), site.id
        assert site.vat is not None
        assert any(obj.kind == 'vat' and obj.tile == site.vat.tile
                   for obj in city.zones[site.vat.zone].meta.objects), site.id
        for obj in clinics:
            assert zone.meta.safety in ('safe', 'pocket') or any(p.contains(obj.tile) for p in zone.meta.pockets)
    assert city.faction_sites['site-halvard'].hall == 'spire-mezzanine'
    assert city.vendors['halvard-security'].zone == 'spire-mezzanine'
    assert city.vendors['landing-trade'].salvage_multiplier == 1.2
    assert all(city.vendors[vid].salvage_multiplier == 1 for vid in (
        'ferrymen-waystation', 'ferrymen-market-buyer', 'kestrel-surplus'))


def test_game_5_2_and_8_4_undercity_water_sight_and_scour_grade_fields(city: ContentTree) -> None:
    assert city.tiles['water'].movement_cost == 2
    assert city.tiles['floor'].movement_cost == 1
    for zid, zone in city.zones.items():
        if zid.startswith('under-'):
            assert zone.meta.sight_radius == author.gazetteer()[zid]['sight_radius']
    drowned = city.zones['under-drowned']
    assert sum(tid == 'water' for row in drowned.grid for tid in row) >= drowned.width*drowned.height*.3
    hunters = next(sp for sp in drowned.meta.spawners if sp.npc == 'npc-water-hunter')
    assert hunters.region and all(drowned.tile_at(tile) == 'water' for tile in hunters.region.tiles())
    for ring in range(1, 5):
        fields = [obj for obj in city.zones[f'scour-ring-{ring}'].meta.objects if obj.kind == 'salvage_field']
        assert len(fields) == 1 and fields[0].params['ring'] == ring


def test_game_7_5_relay_zero_reserve_opens_a_useful_separate_workers_passage(city: ContentTree) -> None:
    service = city.services['relay-zero']
    reserve = next(choice for choice in service.allocations if choice.id == 'reserve')
    binding = next(effect.binding for effect in reserve.effects
                   if effect.params.get('what') == 'credential')
    assert binding is not None and binding.control != 'relay_open'
    controls = {control.id: control for room in city.cores[binding.core].rooms
                for control in room.controls}
    control = controls[binding.control]
    assert control.permission == 'contract' and control.scope == 'mission'
    assert control.action == 'open' and control.reset_seconds == 1200
    ordinary = controls['relay_open']
    assert ordinary.permission == 'public' and ordinary.target.object == 'relay-zero'
    zone = city.zones[service.zone]
    gate = next(obj for obj in zone.meta.objects if obj.id == control.target.object)
    assert gate.kind == 'door' and gate.params['locked'] and not gate.params['open']

    # Compare actual cardinal routes from the repair mast to the public
    # workshop counter, which sells the worker's software and rig. The
    # closed passage must retain an ordinary route and save real walking
    # when opened, rather than merely grant an already-public permission.
    def distance(blocked: set[Tile]) -> int:
        start = city.cores[binding.core].hardware[0].tile
        vendor = city.vendors['oldworks-bench']
        end = next(obj.tile for obj in zone.meta.objects if obj.id == vendor.object_id)
        pending, seen = deque([(start, 0)]), {start}
        while pending:
            (x, y), steps = pending.popleft()
            if (x, y) == end:
                return steps
            for tile in ((x-1, y), (x+1, y), (x, y-1), (x, y+1)):
                tid = zone.tile_at(tile)
                if tid is not None and tile not in seen | blocked:
                    definition = city.tiles[tid]
                    if definition.passable and not definition.hazard:
                        seen.add(tile)
                        pending.append((tile, steps+1))
        raise AssertionError('The workers passage must retain a public return')

    assert distance({gate.tile}) - distance(set()) >= 8

    game = HeadlessServer(deepcopy(city), character_state={})
    caller = game.connect()
    create(game, caller)
    player = game.core.characters.players[caller.session.player_id]
    owner = game.core.contracts
    assert not owner.control_permit(player.id, binding.core, binding.control)
    node = owner.state.services.nodes[service.id]
    node.state, node.allocation = 'allocated', 'reserve'
    node.roster, node.allocation_expires = (player.id,), owner.now()+1200
    assert owner.control_permit(player.id, binding.core, binding.control)
    assert not owner.control_permit('another-caller', binding.core, binding.control)
    assert not owner.control_permit(player.id, binding.core, 'relay_open')
    # Replay a committed opening receipt, isolating the authored target
    # from channel timing, which is covered by the S15 controller tests.
    interlock = game.core.lattice.interlock
    live_gate = game.core.world.zones[service.zone].objects[gate.id]
    game.core.npcs.spawners.process(game.core.world.zones[service.zone], owner.now())
    assert live_gate.open is False
    interlock.state['effects'][binding.core+':'+binding.control] = {
        'core': binding.core, 'control': binding.control, 'revision': control.revision,
        'enabled': True, 'starts': owner.now(), 'expires': owner.now()+1200,
        'serial': 1, 'actor': player.id}
    interlock.compose()
    assert live_gate.open is True
    game.clock.advance(12001)
    interlock.compose()
    assert live_gate.open is False
    assert not owner.control_permit(player.id, binding.core, binding.control)


def test_game_7_5_real_services_and_event_sources_are_commissioned(city: ContentTree) -> None:
    for service in city.services.values():
        assert city.active('services', service.id) and city.active('contracts', service.contract)
        zone = city.zones[service.zone]
        assert set(service.target_objects) <= {obj.id for obj in zone.meta.objects}
        giver = city.contracts[service.contract].giver
        assert any(obj.essential and obj.params.get('contract_handler') == giver
                   for obj in zone.meta.objects), (service.id, 'missing local public work-order board')
    for event in ('ring-fall', 'exhale', 'convoy'):
        assert city.active('events', event)
    event = city.events['ring-fall']
    assert all(effect.params['npc'] == 'npc-halvard-recovery'
               for effect in event.effects if effect.type == 'npc_spawn')
    assert city.npcs['npc-halvard-recovery'].faction == 'halvard'
    # Finale authorization stays owned by S26; geography cannot fake it.
    outworks = city.zones['under-outworks']
    exit_ = next(ex for ex in outworks.meta.exits if ex.target_zone == 'under-shaft-foot')
    assert exit_.requirement is None
    assert {layout.id for layout in outworks.meta.layouts} >= {'exhale-shortcut'}


def test_game_7_5_and_9_4_warm_stack_board_preserves_the_five_story_inspections(city: ContentTree) -> None:
    game = HeadlessServer(deepcopy(city), character_state={})
    caller = game.connect()
    create(game, caller)
    owner = game.core.contracts
    game.commit_commerce()
    pid = caller.session.player_id
    # Isolate an already accepted canonical story. Travel, unlock pacing
    # and its earlier chapters are separate acceptance obligations.
    draft = owner.state.fork()
    tid = 'sab-red-s1-4-candles'
    # The current pre-season build does not offer this later chapter.
    draft.engine.templates[tid] = owner.content.contracts[tid]
    job = draft.engine.accept(draft.engine.story_offer(tid, pid),
                              (owner.participant(pid),), owner.now())
    owner.write(draft)
    game.commit_commerce()
    zone = game.core.world.zones['sink-floor']
    for index in range(1, 6):
        tile = zone.objects[f'warm-stack-{index}'].spec.tile
        place(game, caller, zone.id, game.core.world.free_tile(zone.id, tile))
        act(game, caller, Frame('key', {'k': 'e', 't': 0}))
        game.commit_commerce()
        current = owner.state.engine.instances[job.id]
        assert sum(current.stages[0].counts.values()) == index
        assert caller.session.id not in owner.panels.menus
    assert current.state == 'complete'
    place(game, caller, zone.id, zone.objects['warm-stack-1'].spec.tile)
    act(game, caller, Frame('key', {'k': 'e', 't': 0}))
    panel = owner.panels.menus[caller.session.id]
    assert panel.handler == 'sable'
    assert any(row['id'] == 'service:sump' for row in owner.panels.rows(caller.session, panel))


def test_game_5_6_three_cable_stations_keep_an_independent_free_route(city: ContentTree) -> None:
    for zid in ('sink-rim', 'sink-terraces'):
        cables = [ex for ex in city.zones[zid].meta.exits if ex.kind == 'cable']
        assert len(cables) == 3 and len({ex.tile for ex in cables}) == 3
        assert all(ex.relay == 'cable' and ex.requirement is None for ex in cables)
        alternative = next(ex for ex in city.zones[zid].meta.exits if ex.id.startswith('free-ladder-'))
        assert alternative.relay is None and alternative.requirement is None and alternative.kind == 'ladder'
        for ex in cables:
            assert any(back.tile == ex.target_tile and back.target_tile == ex.tile
                       for back in city.zones[ex.target_zone].meta.exits)


def test_game_12_convoy_road_and_impact_sites_do_not_mask_each_other(city: ContentTree) -> None:
    assert city.tiles['convoy-road'].cover == 0 and city.tiles['convoy-road'].hazard is None
    route = city.routes['scour-convoy-road']
    assert route.speed == 2 and len(route.waypoints) == 3
    for waypoint in route.waypoints:
        zone = city.zones[waypoint.zone]
        assert sum(tid == 'convoy-road' for row in zone.grid for tid in row) > 20
        assert any(obj.id == 'convoy-road-marker' for obj in zone.meta.objects)
    for effect in city.events['ring-fall'].effects:
        if effect.type not in ('hazard', 'npc_spawn'):
            continue
        zone = city.zones[effect.zone]
        assert effect.region and all(zone.tile_at(tile) != 'convoy-road' for tile in effect.region.tiles())
        assert not set(effect.region.tiles()).intersection(
            [obj.tile for obj in zone.meta.objects]+[ex.tile for ex in zone.meta.exits])
    far = city.zones['scour-ring-4']
    assert len([obj for obj in far.meta.objects if obj.kind == 'cache' and obj.id.startswith('season-artifact-')]) == 2


@pytest.mark.parametrize('role,grade,health,damage,cooldown,accuracy,range_,kind', [
    ('dog', 1, 30, 6, 1.5, 60, 1, 'kinetic'),
    ('feral', 5, 75, 10, 1.5, 60, 1, 'kinetic'),
    ('water-hunter', 7, 90, 12, 1.5, 65, 1, 'kinetic'),
    ('blind-swarm', 6, 55, 8, 1, 60, 1, 'chemical'),
    ('apex', 16, 180, 20, 1.5, 70, 1, 'kinetic'),
    ('old-maintenance', 10, 100, 12, 1.5, 65, 6, 'energy'),
    ('custodian-recovery', 20, 200, 20, 1.5, 70, 8, 'energy'),
])
def test_game_5_5_initial_creature_profiles_match_documented_numbers(city: ContentTree,
        role: str, grade: int, health: int, damage: int, cooldown: float,
        accuracy: int, range_: int, kind: str) -> None:
    npc = city.npcs['npc-'+role]
    assert (npc.grade, npc.health, npc.xp) == (grade, health, 20)
    assert npc.attack and (npc.attack.damage, npc.attack.cooldown, npc.attack.accuracy,
                          npc.attack.range, npc.attack.damage_type) == (damage, cooldown, accuracy, range_, kind)


def test_authoring_can_regenerate_from_its_own_published_tree(city_path: Path,
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(author, 'SHIPPED', city_path)
    author.build(tmp_path/'regenerated')
    regenerated = load_content(tmp_path/'regenerated')
    assert validate(regenerated) == []
    assert len(regenerated.zones['terraces-blocks'].meta.objects) == len(
        load_content(city_path).zones['terraces-blocks'].meta.objects)
    assert len(regenerated.sectors['lat-terraces'].cells) == 36
    for file in city_path.rglob('*'):
        if file.is_file():
            assert file.read_bytes() == (tmp_path/'regenerated'/file.relative_to(city_path)).read_bytes(), file




def test_game_5_6_season_console_underfoot_is_not_stolen_by_adjacent_telemetry(city: ContentTree) -> None:
    game = HeadlessServer(deepcopy(city), character_state={})
    caller = game.connect()
    create(game, caller, archetype=0)
    console = next(obj for obj in city.zones['under-shaft-foot'].meta.objects if obj.params.get('season_door'))
    place(game, caller, 'under-shaft-foot', console.tile)
    assert game.core.lattice.terminal(game.core.combat.actor(game.core.characters.players[caller.session.player_id])) is None
    act(game, caller, Frame('key', {'k': 'e', 't': 0}))
    assert caller.session.player_id not in game.core.lattice.presences
    assert any(frame.type == 'log' and any('season door is sealed' in line['text'].lower()
               for line in frame.data['lines']) for frame in game.frames_for(caller))
    # The corrected southern console is not a public Lattice terminal.
    act(game, caller, Frame('key', {'k': 'j', 't': 0}))
    assert caller.session.player_id not in game.core.lattice.presences




def test_game_8_4_real_ring_nodes_never_require_an_interrupted_harvest_on_a_hazard(city: ContentTree) -> None:
    game = HeadlessServer(deepcopy(city), character_state={})
    salvage = game.core.salvage
    salvage.tick()
    game.commit_commerce()
    # The authored rings expose actual failures at seeds 3, 9 and 5 on
    # rings 2, 3 and 4. Damage interrupts a two-second harvest, so those
    # nodes cannot be collected and eventually fill the shared node cap.
    for ring in range(1, 5):
        zid = f'scour-ring-{ring}'
        zone = game.core.world.zones[zid]
        for seed in range(32):
            draft = deepcopy(salvage.state)
            draft['zones'][zid]['nodes'] = {}
            assert salvage.spawn(zid, draft, Random(seed))
            node = next(iter(draft['zones'][zid]['nodes'].values()))
            tile = tuple(node['tile'])
            assert zone.passable(tile) and zone.tiles[zone.tile_id(tile)].hazard is None, (zid, seed, tile)


def test_game_5_2_closed_exhale_crossing_recovers_to_reachable_public_ground(city: ContentTree) -> None:
    game = HeadlessServer(deepcopy(city), character_state={})
    caller = game.connect()
    create(game, caller)
    world = game.core.world
    zone = world.zones['under-outworks']
    crossing = next(layout for layout in zone.template.meta.layouts if layout.id == 'exhale-shortcut')
    saved_tile = crossing.changes[0].tile
    assert not zone.passable(saved_tile)  # The published opening has expired.
    actor = game.core.characters.sim.avatars[caller.session.user_id].actor
    tile = world.free_tile(zone.id, saved_tile, actor)
    assert tile in reachable(city, zone.template, set())
    assert zone.passable(tile) and not zone.tiles[zone.tile_id(tile)].hazard


def test_game_5_6_real_citadel_lockdown_and_gatehouse_restore_share_one_lift(city: ContentTree) -> None:
    game = HeadlessServer(deepcopy(city), character_state={})
    caller = game.connect()
    create(game, caller)
    manager = game.core.characters
    player = manager.players[caller.session.player_id]
    player.faction, player.standing['halvard'] = 'halvard', 10
    interlock = game.core.lattice.interlock
    close = interlock.controls['lat-halvard-citadel', 'executive-lift-lockdown']
    opened = interlock.controls['lat-gatehouse', 'public-lifts']
    assert close.target == opened.target and close.action == 'close' and opened.action == 'open'
    assert close.reset_seconds == 300 and close.safety_policy == 'route'
    assert close.alternate_route == 'to-core-plaza'
    zone = game.core.world.zones[close.target.zone]
    panel = zone.objects[close.target.object]
    assert panel.spec.params['exits'] == ['to-spire-mezzanine']
    interlock.check_effect(close, player.id, 'lat-halvard-citadel')
    gate = next(ex for ex in zone.template.meta.exits if ex.id == 'to-spire-mezzanine')
    place(game, caller, zone.id, gate.tile)
    game.commit_commerce()
    avatar = manager.sim.avatars[caller.session.user_id]
    now = interlock.now()

    # Replay actual persisted control receipts on the commissioned panel.
    # Channel/receipt atomicity is covered by the S15 controller tests.
    def receipt(core: str, control: Any, serial: int, enabled: bool) -> None:
        interlock.state['serial'] = serial
        interlock.state['effects'][core+':'+control.id] = {
            'core': core, 'control': control.id, 'revision': control.revision,
            'enabled': enabled, 'starts': now, 'expires': now+control.reset_seconds,
            'serial': serial, 'actor': player.id}
        interlock.compose()

    receipt('lat-halvard-citadel', close, 1, False)
    assert (zone.id, gate.id) in manager.sim.locked_exits
    assert (zone.id, 'to-core-plaza') not in manager.sim.locked_exits
    assert ('spire-mezzanine', 'to-spire-atrium') not in manager.sim.locked_exits
    manager.sim.interact(caller.session, avatar, game.clock.now_tick())
    assert avatar.travel is None
    assert any(frame.type == 'log' and any('controls keep' in line['text'] for line in frame.data['lines'])
               for frame in game.frames_for(caller))
    receipt('lat-gatehouse', opened, 2, True)
    assert (zone.id, gate.id) not in manager.sim.locked_exits
    player.standing['halvard'] = 0
    manager.sim.interact(caller.session, avatar, game.clock.now_tick())
    assert avatar.travel is None  # Restoring machinery grants no admission credential.
    player.standing['halvard'] = 10
    manager.sim.interact(caller.session, avatar, game.clock.now_tick())
    assert avatar.travel is not None
    game.step(10)
    assert avatar.zone == 'spire-mezzanine'


def test_game_5_6_exact_relay_tile_opens_its_card_despite_nearby_hardware(city: ContentTree) -> None:
    game = HeadlessServer(deepcopy(city), character_state={})
    caller = game.connect()
    create(game, caller)
    owner = game.core.relays
    for rid, relay in city.relays.items():
        terminal = next(obj for obj in city.zones[relay.zone].meta.objects if obj.id == relay.terminal)
        place(game, caller, relay.zone, terminal.tile)
        game.commit_commerce()  # Acknowledge real exploration receipts.
        act(game, caller, Frame('intent', {'name': 'interact', 'args': {}}))
        if relay.requires_level:
            assert not owner.active(rid) and caller.session.id not in owner.views.menus
            continue  # S26 owns this published level gate, even after mapping.
        assert caller.session.id in owner.views.menus, (rid, game.core.lattice.interlock.menus)
        assert owner.views.menus[caller.session.id].relay == rid
        act(game, caller, Frame('key', {'k': 'escape', 't': 0}))
        assert caller.session.id not in owner.views.menus
    hardware = next(obj for obj in city.zones['terraces-blocks'].meta.objects if obj.id == 'block-relay-hardware')
    place(game, caller, 'terraces-blocks', hardware.tile)
    game.commit_commerce()
    act(game, caller, Frame('intent', {'name': 'interact', 'args': {}}))
    assert game.core.lattice.interlock.menus[caller.session.id][:2] == ('terraces-blocks', hardware.id)
