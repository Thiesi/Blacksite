"""Execute actual E/J handlers over authored tiles, without stepping NPCs.

This driver also runs unchanged against the pre-P3 source in an independent
process. Its outcome digest pins behavior as well as comparing queries with
the consuming handler. Matrix positions are input fixtures, including an
object's own tile when it is not walkable; they are not movement acceptance.
"""

from collections import Counter
from copy import deepcopy
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
from typing import Any
from collections.abc import Callable

from blacksite.content.loader import load_content
from blacksite.server.bus import Event
from blacksite.server.lattice.presence import Presence
from blacksite.server.protocol import Frame
from tests.character_helpers import create
from tests.harness import HeadlessServer


ORDER = ('events', 'market', 'contracts', 'factions', 'crews', 'relays',
         'apartments', 'progression', 'lattice', 'interlock', 'combat',
         'fabrication', 'commerce', 'npcs', 'chat', 'terminal', 'characters')


def matrix_content(root: Path) -> tuple[Any, list[str]]:
    content = load_content(root/'src/blacksite/content')
    fixture = load_content(root/'tests/fixtures/world')
    # Add the fixture world to the complete game, preserving shipped records
    # with shared catalog ids. This exercises the same subsystem composition.
    for name in ('zones', 'sectors', 'cores', 'items', 'programs', 'ice', 'npcs',
                 'factions', 'vendors', 'contracts', 'text', 'tiles'):
        target = getattr(content, name)
        for key, value in getattr(fixture, name).items():
            target.setdefault(key, value)
    hubs = json.loads((root/'src/blacksite/content/bundles/m1-zone-preview.json').read_text())['members']['zones']
    assert len(hubs) == 10
    return content, sorted([*hubs, *fixture.zones])


def outcome(game: HeadlessServer, client: Any, consumed: str) -> dict[str, Any]:
    core, session = game.core, client.session
    sim, lat = core.characters.sim, core.lattice
    avatar = sim.avatars[session.user_id]
    actor = avatar.actor
    menus = {}
    for name, mapping in (
        ('commerce', core.commerce.menus), ('housing', core.apartments.menus),
        ('factions', core.factions.menus), ('contracts', core.contracts.panels.menus),
        ('relays', core.relays.views.menus), ('workshop', core.fabrication.menus),
        ('hardware', lat.interlock.menus), ('encounter', lat.encounters.menus)):
        value = mapping.get(session.id)
        if value is not None:
            menus[name] = asdict(value) if hasattr(value, '__dataclass_fields__') else value
    presence = lat.presences.get(session.player_id)
    return {
        'handler': consumed, 'menus': menus,
        'body': [actor.zone, *actor.position, actor.stance, actor.health, actor.stamina],
        'presence': ([presence.sector, presence.cell, presence.instance, presence.room,
                      presence.loaned_rig, asdict(presence.escape) if presence.escape else None]
                     if presence else None),
        'travel': avatar.travel.exit.id if avatar.travel else None,
        'logs': [line['text'] for line in session.log_ring],
        'pending': bool(core.commerce.pending), 'waiting': len(core.commerce.waiting),
    }


def run_matrix(root: Path, *, verify: bool = True,
               inspect_focus: Callable[[Any, Any, Any], None] | None = None) -> tuple[dict[str, Any], list[Any]]:
    content, zones = matrix_content(root)
    game = HeadlessServer(content, character_state={})
    client = game.connect()
    create(game, client, archetype=0, name='Matrix界', card='none')
    game.commit_characters()
    game.commit_commerce()
    core, session = game.core, client.session
    sim, lat = core.characters.sim, core.lattice
    avatar = sim.avatars[session.user_id]
    body = avatar.actor
    saved_player = deepcopy(core.characters.players[session.player_id])
    saved_actor = deepcopy(body.__dict__)
    saved_objects = {zid: {oid: deepcopy(obj.__dict__) for oid, obj in zone.objects.items()}
                     for zid, zone in core.world.zones.items()}
    saved_leases = deepcopy(core.apartments.state)
    mappings = [core.events.views.menus, core.market.views.menus, core.market.views.prompts,
                core.contracts.panels.menus, core.factions.menus, core.crews.menus,
                core.relays.views.menus, core.apartments.menus, core.apartments.prompts,
                core.progression.menus, core.progression.clinics.menus,
                core.progression.drones.menus, core.combat.menus, core.fabrication.menus,
                core.commerce.menus, core.commerce.prompts, core.npcs.menus,
                core.chat.sitreps, core.characters.screens, core.characters.wakes,
                sim.maps, sim.external_views, lat.presences, lat.transitions,
                lat.encounters.menus, lat.interlock.menus, lat.interlock.log_menus]
    # Observe the actual return values, independently of Core's resolver.
    observed: list[str] = []
    owners = {name: getattr(core, name) for name in ORDER
              if name not in ('interlock', 'terminal', 'characters')}
    owners.update(interlock=lat.interlock, terminal=lat, characters=core.characters)
    for name in ORDER:
        owner = owners[name]
        attr = 'terminal_input' if name == 'terminal' else 'input'
        original = getattr(owner, attr)
        def record(*args: Any, _fn: Any = original, _name: str = name, **kwargs: Any) -> Any:
            result = _fn(*args, **kwargs)
            if result or _name == 'characters':
                observed.append(_name)
            return result
        setattr(owner, attr, record)

    rows = []
    counts: Counter[str] = Counter()
    for zid in zones:
        zone = core.world.zones[zid]
        points = {obj.spec.tile for obj in zone.objects.values()}
        points.update(ex.tile for ex in zone.template.meta.exits)
        points.update(actor.position for actor in zone.actors.values() if actor is not body)
        points = sorted({(x+dx, y+dy) for x, y in points for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                         if 0 <= x+dx < zone.template.width and 0 <= y+dy < zone.template.height})
        for tile in points:
            for jacked in (False, True):
                for action in ('interact', 'jack'):
                    for transport in ('key', 'intent'):
                        for mapping in mappings:
                            mapping.clear()
                        core.commerce.outbox.clear()
                        core.commerce.waiting.clear()
                        core.commerce.pending = None
                        core.characters.outbox.clear()
                        core.apartments.state.clear()
                        core.apartments.state.update(deepcopy(saved_leases))
                        core.characters.players[session.player_id] = deepcopy(saved_player)
                        # Leave from the actual post-input zone before restoring
                        # the actor's fields; World owns zone membership.
                        core.world.leave(body)
                        body.__dict__.update(deepcopy(saved_actor))
                        body.zone, body.x, body.y = zid, *tile
                        core.world.actors[body.id] = body
                        zone.actors[body.id] = body
                        avatar.zone, avatar.travel = zid, None
                        session.subscribed = zid
                        session.pending_prompts.clear()
                        session.log_ring.clear()
                        session.send_queue.clear()
                        session.closed = False
                        for oid, state in saved_objects[zid].items():
                            zone.objects[oid].__dict__.update(deepcopy(state))
                        if jacked:
                            sector = zone.template.meta.sector or 'fx-sector'
                            lat.presences[session.player_id] = Presence(body.id+':presence', body.id, sector,
                                lat.sectors.entrance(sector), ('prg_pick', 'prg_umbrella', None), loaned_rig=True)
                            body.stance = 'jacked'
                        frame = (Frame('key', {'k': 'e' if action == 'interact' else 'j', 't': 0})
                                 if transport == 'key' else Frame('intent', {'name': action, 'args': {}}))
                        observed.clear()
                        prediction = core.resolve_interaction(session, frame) if verify else None
                        if inspect_focus is not None:
                            inspect_focus(core, session, prediction)
                        core._echo(Event('input', {'session': session, 'frame': frame, 'tick': game.clock.now_tick()}))
                        assert len(observed) == 1, (zid, tile, jacked, action, observed)
                        actual = observed[0]
                        if verify:
                            assert prediction is not None and prediction.route.name == actual, (
                                zid, tile, jacked, action, transport,
                                prediction.route.name if prediction else None, actual)
                        result = outcome(game, client, actual)
                        rows.append([zid, tile, jacked, action, transport, result])
                        counts[actual] += 1
    encoded = json.dumps(rows, ensure_ascii=True, sort_keys=True, separators=(',', ':')).encode()
    return {'sha256': sha256(encoded).hexdigest(), 'cases': len(rows), 'zones': zones,
            'handlers': dict(sorted(counts.items()))}, rows
