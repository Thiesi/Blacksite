"""S25: exercise the complete authored geography before shipping its files."""

from collections import Counter, deque
from copy import deepcopy
from pathlib import Path
from random import Random

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


def test_game_5_1_every_public_anchor_has_a_route_outside_private_rooms_and_hazards(city: ContentTree) -> None:
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
            routes = seen if public else base
            assert obj.tile in routes or any((obj.tile[0]+dx, obj.tile[1]+dy) in routes
                for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0))), (zid, obj.id)


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


def test_game_8_7_24_homes_do_not_reuse_public_entry_uplinks_or_population(city: ContentTree) -> None:
    zone = city.zones['terraces-blocks']
    homes = [obj for obj in zone.meta.objects if obj.housing]
    assert len(homes) == 24
    assert Counter(obj.housing.class_id for obj in homes) == {
        'apt_terrace_cell': 8, 'apt_terrace_flat': 8, 'apt_terrace_corner': 8}
    sector = city.sectors['lat-terraces']
    assert len(sector.cells) == 48 and sector.layout_size == (8, 6)
    assert len({cell.pos for cell in sector.cells}) == 48
    assigned = {obj.housing.cell for obj in homes}
    assert len(assigned) == 24
    for cell in sector.cells:
        if cell.id in assigned:
            assert cell.id != sector.entry and cell.uplink is None
            assert cell.access_kind == 'public' and not cell.core_id and not cell.core_placeholder
    private = {tile for obj in homes for tile in Region(*obj.housing.origin, 6, 4).tiles()}
    for spawner in zone.meta.spawners:
        assert not private.intersection(spawner.region.tiles() if spawner.region else [spawner.tile])
    assert any(obj.params.get('letting') for obj in zone.meta.objects)


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
    for zid, zone in city.zones.items():
        if zid.startswith('under-'):
            assert zone.meta.sight_radius == 5
    drowned = city.zones['under-drowned']
    assert sum(tid == 'water' for row in drowned.grid for tid in row) >= drowned.width*drowned.height*.3
    hunters = next(sp for sp in drowned.meta.spawners if sp.npc == 'npc-water-hunter')
    assert hunters.region and all(drowned.tile_at(tile) == 'water' for tile in hunters.region.tiles())
    for ring in range(1, 5):
        fields = [obj for obj in city.zones[f'scour-ring-{ring}'].meta.objects if obj.kind == 'salvage_field']
        assert len(fields) == 1 and fields[0].params['ring'] == ring


def test_game_7_5_real_services_and_event_sources_are_commissioned(city: ContentTree) -> None:
    for service in city.services.values():
        assert city.active('services', service.id) and city.active('contracts', service.contract)
        zone = city.zones[service.zone]
        assert set(service.target_objects) <= {obj.id for obj in zone.meta.objects}
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
    assert len(regenerated.sectors['lat-terraces'].cells) == 48
    for file in city_path.rglob('*'):
        if file.is_file():
            assert file.read_bytes() == (tmp_path/'regenerated'/file.relative_to(city_path)).read_bytes(), file


def test_game_8_7_real_resident_can_leave_a_closed_room_without_blocking_city_controls(city: ContentTree) -> None:
    # Production's hex world origin sorts before the residence door ID.
    game = HeadlessServer(deepcopy(city), character_state={}, origin='0-city-test')
    owner = game.connect()
    create(game, owner)
    manager = game.core.characters
    player = manager.players[owner.session.player_id]
    player.grade, player.chits_bank = 5, 20000
    player.update_personhood(manager.identity(player.bbs_user_id), game.clock.now_utc())
    apartments = game.core.apartments
    assert len(apartments.geometry.units) == 24
    unit = next(unit for unit in apartments.geometry.units.values() if unit.definition.id == 'apt_terrace_cell')
    letting = next(obj for obj in city.zones['terraces-blocks'].meta.objects if obj.id == 'letting-office')
    place(game, owner, unit.zone, letting.tile)
    apartments.propose(owner.session, 'rent', {'target': letting.id, 'unit': unit.id})
    assert apartments.lease(player) is None
    game.commit_commerce()
    record = apartments.lease(player)
    assert record and record['unit'] == unit.id
    place(game, owner, unit.zone, unit.anchor.doorstep)
    apartments.door(owner.session, unit)
    actor = game.core.combat.actor(player)
    zone = game.core.world.zones[unit.zone]
    assert unit.region.contains(actor.position) and not zone.allows_hostile(actor.position)
    assert zone.objects[unit.door].open is False
    # Apartment exit is an explicit resident/visitor action. A closed
    # private door must not freeze unrelated public geometry operations.
    assert zone.safe_geometry({})
    assert not zone.safe_geometry({actor.position: 'wall'})
    hatch = next(obj for obj in zone.objects.values() if obj.spec.id == 'stairwell-c-parcel-hatch')
    assert zone.set_door(hatch.spec.id, True)
    assert zone.set_door(hatch.spec.id, False)
    for _ in range(2):
        act(game, owner, Frame('intent', {'name': 'move', 'args': {'dir': 'down'}}))
    assert actor.position == unit.tile(unit.anchor.vestibule)
    act(game, owner, Frame('intent', {'name': 'interact', 'args': {}}))
    assert actor.position == unit.anchor.doorstep
    # A delivery key dropped beside the dedicated doorstep must not make
    # E open the apartment core log instead of entering the resident's home.
    issued = next(i for i in player.inventory if game.core.commerce.items[i].key_for == player.apartment_id)
    place(game, owner, unit.zone, (unit.anchor.doorstep[0]-1, unit.anchor.doorstep[1]))
    game.core.commerce.propose(owner.session, 'inv.drop', {'item': issued})
    game.commit_commerce()
    assert issued not in player.inventory
    place(game, owner, unit.zone, unit.anchor.doorstep)
    act(game, owner, Frame('intent', {'name': 'interact', 'args': {}}))
    assert unit.region.contains(actor.position)
    assert owner.session.id not in game.core.lattice.interlock.log_menus


def test_game_5_6_season_console_underfoot_is_not_stolen_by_adjacent_telemetry(city: ContentTree) -> None:
    game = HeadlessServer(deepcopy(city), character_state={})
    caller = game.connect()
    create(game, caller, archetype=0)
    console = next(obj for obj in city.zones['under-shaft-foot'].meta.objects if obj.params.get('season_door'))
    place(game, caller, 'under-shaft-foot', console.tile)
    assert game.core.lattice.terminal(game.core.combat.actor(game.core.characters.players[caller.session.player_id]))
    act(game, caller, Frame('key', {'k': 'e', 't': 0}))
    assert caller.session.player_id not in game.core.lattice.presences
    assert any(frame.type == 'log' and any('season door is sealed' in line['text'].lower()
               for line in frame.data['lines']) for frame in game.frames_for(caller))
    # J remains the explicit alternative even while standing on the prop.
    act(game, caller, Frame('key', {'k': 'j', 't': 0}))
    assert caller.session.player_id in game.core.lattice.presences


def test_architecture_6_1_crowded_real_blocks_share_the_public_escape_search(city: ContentTree) -> None:
    from blacksite.server.clock import ManualClock
    from blacksite.server.housing_geometry import HousingGeometry
    from blacksite.server.world.actors import Actor
    from blacksite.server.world.registry import World

    world = World(deepcopy(city), {zid: 0 for zid in city.zones})
    homes = HousingGeometry(world, ManualClock(), {})
    zone = world.zones['terraces-blocks']
    assert len(homes.units) == 24
    for n in range(30):
        actor = Actor(f'crowd:{n}', 'Public caller', zone=zone.id)
        actor.x, actor.y = world.free_tile(zone.id, zone.template.meta.spawn, actor)
        zone.actors[actor.id] = actor
    calls = 0
    original = zone.entry_policy

    def counted(actor: Actor | None, tile: Tile) -> bool:
        nonlocal calls
        calls += 1
        return original(actor, tile)

    zone.entry_policy = counted
    assert zone.safe_geometry({})
    # Bound work rather than wall time: thirty public callers must not
    # trigger thirty full-map privacy/escape searches on one door toggle.
    assert calls < 4*zone.template.width*zone.template.height
    private = next(iter(homes.units.values()))
    assert not zone.entry_policy(None, private.tile((2, 2)))
    assert not zone.entry_policy(next(iter(zone.actors.values())), private.tile((2, 2)))


def test_game_8_4_real_ring_nodes_never_require_an_interrupted_harvest_on_a_hazard(city: ContentTree) -> None:
    game = HeadlessServer(deepcopy(city), character_state={})
    salvage = game.core.salvage
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
    # The same fallback cannot put a returning outsider into a tenant's
    # room merely because that is the nearest floor behind the wall.
    blocks = world.zones['terraces-blocks']
    unit = next(iter(game.core.apartments.geometry.units.values()))
    private_floor = unit.tile(unit.room.meta.spawn)
    tile = world.free_tile(blocks.id, private_floor, actor)
    assert not game.core.apartments.geometry.containing(blocks.id, tile)


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
