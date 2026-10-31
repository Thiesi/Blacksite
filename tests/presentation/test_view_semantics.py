"""Architecture 5.4/5.5.3/5.5.4: additive facts and per-caller disclosure."""

import ast
from dataclasses import replace

import pytest

from blacksite.content.loader import load_content
from blacksite.server.lattice.presence import Procedure
from blacksite.server.npcs.templates import make_actor
from blacksite.server.views.zone_view import Perception, build
from tests.character_helpers import create, place
from tests.harness import HeadlessServer
from tests.lattice.test_engine import actor, intent, jack, runners
from tests.lattice.test_encounters import enter
from tests.lattice.test_private_cores import apartment_fixture
from tests.door.test_progression_menus import render
from tests.door.conftest import info
from tests.server.test_drone_combat import deploy


@pytest.mark.parametrize('width,height', [(80, 24), (132, 50)])
def test_arch_5_5_4_shipped_sodium_warden_cover_and_per_caller_reveal(repo_root, info, width, height):
    content = load_content(repo_root/'src/blacksite/content')
    template = content.npcs['npc-plainclothes-warden']
    assert template.presents == 'civilian' and template.cover_name == 'Sodium regular'
    # Keep every shipped spawner/template; do not manufacture a Warden.
    game = HeadlessServer(content, character_state={})
    clients = []
    for uid, tile in ((1, (89, 3)), (2, (89, 4))):
        client = game.connect({'user_id': uid, 'handle': f'Cover界{uid}', 'node_name': 'P4'},
                              width=width, height=height)
        create(game, client, archetype=3, name=f'Cover界{uid}', card='none')
        place(game, client, 'sodium-row', game.core.world.free_tile('sodium-row', tile))
        clients.append(client)
    one, two = clients
    zone = game.core.world.zones['sodium-row']
    npc = next(a for a in zone.actors.values() if a.behaviour.get('template') == template.id)
    assert npc.zone == 'sodium-row'
    # Test disclosure, not the content author's street-wide spawn choice.
    # Keep the shipped instance/template and put it in both callers' sight.
    npc.x, npc.y = game.core.world.free_tile('sodium-row', (90, 3))
    assert any(a.name == template.cover_name and a.behaviour.get('template') == 'npc-sodium-regular'
               for a in zone.actors.values())
    sim = game.core.characters.sim
    drones = game.core.progression.drones
    for client in clients:
        caller = actor(game, client)
        player = game.core.characters.players[caller.id]
        drone = deploy(game, client, player, drones)
        drones.menus[client.session.id] = 0
        rows = drones.view(client.session)['rows']
        drones.menus[client.session.id] = next(i for i, row in enumerate(rows)
                                             if row['id'] == drone.behaviour['item'])
        caller.target = npc.id
        view = build(caller, zone, Perception(), content, width, height, '12:00', False, 0)
        assert next(a for a in view['actors'] if a['id'] == npc.id)['class'] == 'civilian'
        assert next(a for a in view['nearby'] if a['id'] == npc.id)['name'] == template.cover_name
        target = game.core.combat.target_view(caller)
        assert target['name'] == template.cover_name and target['class'] == 'civilian'
        assert target['faction'] == 'Civilian' and target['name_role'] == 'npc_neutral'
        sim.speak(client.session, npc, 'Stand here.')
        line = client.session.log_ring[-1]
        assert (line['speaker'], line['speaker_role']) == (template.cover_name, 'civilian')
        menu = drones.view(client.session)
        assert 'Target '+template.cover_name+':' in menu['detail']
        assert template.name not in render(info, content, menu, (width, height))
        assert not npc.revealed_to  # Viewing orders never acts against anyone.
    game.core.combat.warn(npc, actor(game, one), game.clock.now_tick())
    assert npc.revealed_to == {one.session.player_id}
    for client, name, role in ((one, template.name, 'warden'), (two, template.cover_name, 'civilian')):
        sim.speak(client.session, npc, 'Stand here.')
        assert client.session.log_ring[-1]['speaker'] == name
        assert client.session.log_ring[-1]['speaker_role'] == role
        assert game.core.combat.target_view(actor(game, client))['name'] == name
        menu = drones.view(client.session)
        assert 'Target '+name+':' in menu['detail']
        text = render(info, content, menu, (width, height))
        assert name in text
        if client is two:
            assert template.name not in text
    # A respawn is a new instance; content keeps only the authored cover.
    fresh = make_actor(template, 'test:new-shipped-instance', {'home': npc.position})
    assert not fresh.revealed_to


@pytest.mark.parametrize('width,height', [(80, 24), (132, 50)])
def test_arch_5_4_zone_lattice_menu_and_legacy_shapes(runners, width, height):
    game, client, _, _ = runners
    client.session.caps.update(width=width, height=height)
    sim = game.core.characters.sim
    body = actor(game, client)
    zone = game.core.world.zones[body.zone]
    view = build(body, zone, Perception(), sim.world.content, width, height, '12:00', False, 0)
    assert view['me']['district'] == zone.template.meta.district
    assert view['me']['pvp'] is False  # The plaza is safe at every grade.
    assert all('class' in a and type(a['jacked']) is bool for a in view['actors'])
    assert all(o['role'] == sim.world.content.zones[body.zone].meta.objects[
        next(i for i, spec in enumerate(zone.template.meta.objects) if spec.id == o['id'])].kind
        or o['role'] in ('vendor', 'cache') for o in view['objects'])
    intent(game, client, 'map')
    frames = game.frames_for(client)
    menu = [f.data['body'] for f in frames if f.type == 'view' and f.data['kind'] == 'menu'][-1]
    assert menu['me']['district'] == zone.template.meta.district and not menu['me']['pvp']
    intent(game, client, 'menu_close')
    presence = jack(game, client)
    view = game.core.lattice.view(client.session, presence)
    assert view['theme'] == game.core.lattice.sectors.records[presence.sector].district
    assert view['me']['district'] == zone.template.meta.district and not view['me']['pvp']
    assert all('owner' in cell and 'tier' in cell for cell in view['cells'] if cell['core'])
    assert all(edge['label'] for edge in view['edges'])


@pytest.mark.parametrize('width,height', [(80, 24), (132, 50)])
def test_arch_5_5_4_disguise_target_speech_and_instance_lifetime(runners, width, height):
    game, one, two, _ = runners
    content = game.core.loop.content
    template = replace(content.npcs['npc-warden-response'], presents='civilian', cover_name='Plaza resident')
    content.npcs[template.id] = template
    npc = make_actor(template, 'test:plainclothes', {})
    game.core.world.enter(npc, 'core-plaza', (30, 6))
    sim = game.core.characters.sim
    for client in (one, two):
        client.session.caps.update(width=width, height=height)
        caller = actor(game, client)
        caller.target = npc.id
        target = game.core.combat.target_view(caller)
        assert target['class'] == 'civilian' and target['faction'] == 'Civilian'
        assert target['name'] == 'Plaza resident' and target['name_role'] == 'npc_neutral'
        sim.speak(client.session, npc, 'Stand here.')
        line = client.session.log_ring[-1]
        assert (line['kind'], line['speaker'], line['speaker_role']) == ('speech', 'Plaza resident', 'civilian')
    # The real warning path counts as acting even before a shot lands.
    game.core.combat.warn(npc, actor(game, one), game.clock.now_tick())
    assert npc.revealed_to == {one.session.player_id}
    for client, expected in ((one, 'warden'), (two, 'civilian')):
        caller = actor(game, client)
        view = build(caller, game.core.world.zones[caller.zone], Perception(), content,
                     width, height, '12:00', False, 0)
        entry = next(a for a in view['actors'] if a['id'] == npc.id)
        assert entry['class'] == expected
        assert game.core.combat.target_view(caller)['class'] == expected
        sim.speak(client.session, npc, 'Stand here.')
        assert client.session.log_ring[-1]['speaker_role'] == expected
    # A new instance starts covered; the reveal was never put in content.
    game.core.world.leave(npc)
    fresh = make_actor(template, 'test:replacement', {})
    assert not fresh.revealed_to and template.presents == 'civilian'


def test_arch_5_5_4_targeting_reveals_to_target_without_waiting_for_shot(runners):
    game, client, _, _ = runners
    content = game.core.loop.content
    template = replace(content.npcs['npc-warden-response'], presents='civilian', cover_name='Plaza resident')
    content.npcs[template.id] = template
    place(game, client, 'vatside-clinics', (20, 3))
    npc = make_actor(template, 'test:hunter', {})
    game.core.world.enter(npc, 'vatside-clinics', (21, 3))
    actor(game, client).marked = True
    game.core.npcs.evaluate(npc, game.core.world.zones[npc.zone], game.clock.now_tick())
    assert npc.target == client.session.player_id and npc.revealed_to == {client.session.player_id}


def test_arch_5_5_4_retaliation_reveals_before_hit_or_miss_log(runners):
    game, client, observer, _ = runners
    for who, tile in ((client, (20, 3)), (observer, (20, 4))):
        place(game, who, 'vatside-clinics', tile)
    content = game.core.loop.content
    template = replace(content.npcs['npc-warden-response'], presents='civilian', cover_name='Plaza resident')
    content.npcs[template.id] = template
    npc = make_actor(template, 'test:retaliation', {'home': (21, 3)})
    game.core.world.enter(npc, 'vatside-clinics', (21, 3))
    game.commit_commerce()
    caller = actor(game, client)
    combat = game.core.combat
    assert combat.legal(caller, npc) and combat.visible(caller, npc)
    caller.target = npc.id
    assert combat.target_view(caller)['class'] == 'civilian'
    client.session.log_ring.clear()
    observer.session.log_ring.clear()
    # Use the production hostile_hook: exchange targets the attacker and
    # records the reveal before shot formats either Hit or Miss.
    combat.shot(caller, npc, combat.weapon(game.core.characters.players[caller.id])[1])
    assert npc.target == caller.id and npc.revealed_to == {caller.id}
    assert combat.target_view(caller)['class'] == 'warden'
    lines = list(client.session.log_ring)
    assert any(line['text'] in ('Hit: '+npc.name+'.', 'Miss: '+npc.name+'.') for line in lines)
    assert not any(npc.name in line['text'] for line in observer.session.log_ring)
    observer_body = actor(game, observer)
    observer_body.target = npc.id
    assert combat.target_view(observer_body)['class'] == 'civilian'


def test_arch_5_4_modern_legend_and_no_offscreen_disclosure(runners):
    game, client, _, _ = runners
    content = game.core.loop.content
    caller = actor(game, client)
    zone = game.core.world.zones[caller.zone]
    tile = next(iter(content.tiles.values()))
    content.glyphs = replace(content.glyphs, modern={tile.glyph: '·'})
    npc = make_actor(content.npcs['npc-warden-response'], 'test:far', {})
    game.core.world.enter(npc, caller.zone, (70, 30))
    view = build(caller, zone, Perception(), content, 80, 24, '12:00', False, 0)
    assert next(e for e in view['legend'] if e['id'] == tile.id)['glyph_modern'] == '·'
    assert npc.id not in {a['id'] for a in view['actors']}
    assert npc.id not in {a['id'] for a in view['nearby']}
    assert content.glyphs.glyphs['actor-drone'] == 'τ'


@pytest.mark.parametrize('width,height', [(80, 24), (132, 50)])
def test_arch_5_5_4_private_core_owner_is_private(runners, width, height):
    game, resident, other, _ = runners
    _, record = apartment_fixture(game, resident)
    other.session.caps.update(width=width, height=height)
    presence = jack(game, other)
    presence.sector, presence.cell = 'lat-terraces', record['cell']
    view = game.core.lattice.view(other.session, presence)
    cell = next(c for c in view['cells'] if c['id'] == record['cell'])
    assert cell['owner'] == 'private' and cell['tier'] == record['tier']
    assert resident.session.player_id not in cell.values()


def test_arch_5_5_4_black_ice_is_from_own_completed_survey(runners):
    game, one, two, _ = runners
    for client in (one, two):
        place(game, client, 'vatside-wake-hall', game.core.world.free_tile('vatside-wake-hall', (34, 15)))
    a = enter(game, one, 'lat-wake-hall')
    b = enter(game, two, 'lat-wake-hall')
    lat = game.core.lattice
    enc = lat.encounters
    # A shared instance makes per-recipient isolation observable.
    b.instance, b.core, b.room = a.instance, a.core, a.room
    ice = enc.defenders(a)[0]
    ice.template = replace(ice.template, black=True)
    ice.meat_damage = 5
    def black(client, presence):
        result = enc.view(client.session, presence, lat.view(client.session, presence))
        return next(row for row in result[1]['room']['ice'] if row['id'] == ice.id)['black_ice']
    assert not black(one, a) and not black(two, b)
    enc.complete_survey(a, Procedure('survey', '', 0, '', 0))
    assert black(one, a) and not black(two, b)
    a.surveyed_black = {('older-instance', ice.id)}
    assert not black(one, a)


def test_arch_5_5_3_single_emit_and_complete_replay_metadata(runners, repo_root):
    game, client, _, _ = runners
    session = client.session
    with pytest.raises(TypeError):
        session.emit('missing kind', channel='zone', role='text', at='')
    with pytest.raises(ValueError, match='speech requires'):
        session.emit('unknown voice', kind='speech', channel='zone', role='text', at='')
    sim = game.core.characters.sim
    sim.speak(session, actor(game, client), 'A line.')
    assert all('kind' in line for line in session.log_ring)
    assert all('speaker_role' in line and 'speaker' in line
               for line in session.log_ring if line['kind'] == 'speech')
    before = list(session.log_ring)
    session.emit('Service restarted.', kind='notice', channel='system', role='ui_text', at='')
    assert list(session.log_ring) == before
    assert session.send_queue[-1].type == 'toast'
    session.replay_log()
    assert session.send_queue[-1].data['lines'][-1] == before[-1]
    bypasses = []
    for path in (repo_root/'src/blacksite/server').rglob('*.py'):
        if path.name == 'sessions.py':
            continue  # Delivery/replay; all authored lines enter Session.emit.
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == 'Frame' and node.args
                    and isinstance(node.args[0], ast.Constant) and node.args[0].value == 'log'):
                bypasses.append((path, node.lineno))
    assert not bypasses


def test_arch_5_4_pvp_grade_and_safe_pocket(runners):
    game, client, _, _ = runners
    body = actor(game, client)
    player = game.core.characters.players[client.session.player_id]
    place(game, client, 'vatside-clinics', (20, 3))
    assert not game.core.combat.pvp_eligible(body)
    player.grade = 5
    assert game.core.combat.pvp_eligible(body)
    place(game, client, 'core-plaza', (30, 5))
    assert not game.core.combat.pvp_eligible(body)


def test_arch_5_4_relay_role_uses_committed_owner(runners):
    game, client, _, _ = runners
    place(game, client, 'vatside-clinics', (31, 18))
    owner = game.core.relays
    owner.ledger.state['relays'].setdefault('cold-chain', {})['faction'] = 'halvard'
    caller = actor(game, client)
    zone = game.core.world.zones[caller.zone]
    view = build(caller, zone, Perception(), game.core.loop.content, 80, 24, '12:00', False, 0)
    owner.views.decorate(client.session, view)
    obj = next(o for o in view['objects'] if o.get('relay'))
    assert obj['role'] == game.core.loop.content.factions['halvard'].colour
    assert obj['legacy_role'] == 'text'


def test_arch_5_5_3_complete_place_paragraph_is_once_without_toast(runners):
    game, client, _, _ = runners
    sim = game.core.characters.sim
    avatar = sim.avatars[client.session.user_id]
    avatar.seen_zones.discard(avatar.zone)
    game.frames_for(client)
    before = len(client.session.log_ring)
    sim.discover(client.session, avatar)
    assert len(client.session.log_ring) == before+1
    assert client.session.log_ring[-1]['kind'] == 'place'
    frames = game.frames_for(client)
    assert not any(frame.type == 'toast' for frame in frames)
    zone = game.core.world.zones[avatar.zone].template
    asset = game.core.loop.content.text[zone.meta.lore[0]]
    paragraph = ' '.join(asset.body.strip().split('\n\n', 1)[0].splitlines())
    assert client.session.log_ring[-1]['text'] == paragraph
    sim.discover(client.session, avatar)
    assert len(client.session.log_ring) == before+1
