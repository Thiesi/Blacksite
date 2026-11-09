"""S39 fixtures, also executed against main's unchanged production core.

Only the shipped-street case uses an unchanged layout. Other cases declare
their inserted exits/objects or moved NPCs; none edits shipped content.
"""

from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from typing import Any

from karst41.content.loader import ContentTree, load_content
from karst41.content.schema import Behaviour, HousingAnchor, ObjectSpec, Stage, StageTarget
from karst41.server.bus import Event
from karst41.server.commerce import CommerceMenu
from karst41.server.protocol import Frame
from karst41.server.world.zone import ObjectState
from tests.character_helpers import create, place
from tests.contracts.test_engine import template
from tests.harness import FakeClient, HeadlessServer
from tests.presentation.interaction_matrix import outcome


CASES = ('shipped-street', 'talker-off-exit', 'hidden-exit', 'lift', 'tram',
         'legacy-talker', 'vendor-adjacent', 'vendor-off-exit', 'vendor-underfoot',
         'prop-underfoot', 'open-dialogue', 'open-shop', 'contract-giver',
         'mission-action', 'board', 'doorstep', 'talker-before-terminal')
PROMOTED = {'shipped-street', 'hidden-exit', 'lift', 'tram', 'legacy-talker',
            'vendor-adjacent', 'contract-giver'}


def mission(core: Any, session: Any, zone: str, object_id: str) -> str:
    """Declared survey fixture beside a giver; normal mission resolution."""
    owner = core.contracts
    target = StageTarget('object', zone=zone, object=object_id)
    stage = Stage('survey', 'survey', target, 'interact', 'surveyed', 's39:survey')
    job = template('s39-survey', story=True, stages=(stage,))
    owner.content.contracts[job.id] = owner.state.engine.templates[job.id] = job
    instance = owner.state.engine.accept(owner.state.engine.story_offer(job.id, session.player_id),
                                        (owner.participant(session.player_id),), owner.now())
    return instance.id


def setup(content: ContentTree, case: str) -> tuple[HeadlessServer, FakeClient]:
    content = deepcopy(content)
    if case in ('contract-giver', 'mission-action'):
        # Vesper's dialogue is staged in a disabled bundle. Declare a copy
        # for these fixtures, retaining its real contract offers.
        content.dialogue['s39-giver'] = replace(content.dialogue['vesper'], id='s39-giver')
    if case == 'doorstep':
        # The shipped housing pool is not commissioned. Use S18's first
        # declared anchor, in memory, without changing the shipped layout.
        zone = content.zones['vatside-wake-hall']
        anchor = HousingAnchor('apt_terrace_cell', 'apartment', (2, 13),
                               'lat-terraces', 'lat-terraces-c1', (4, 11), (2, 0))
        door = ObjectSpec('s39-home', (4, 12), 'apartment_door', {'name': 'Threshold home'}, housing=anchor)
        content.zones[zone.id] = replace(zone, meta=replace(zone.meta, objects=(*zone.meta.objects, door)))
    game = HeadlessServer(content, character_state={})
    caller = game.connect()
    create(game, caller, archetype=0, name='Threshold界', card='none')
    game.commit_characters()
    game.commit_commerce()
    core, session = game.core, caller.session
    sim = core.characters.sim
    zone = core.world.zones['sodium-tin-halo']
    exit_ = zone.template.meta.exits[0]
    tile = exit_.tile
    adjacent = tile[0]+1, tile[1]
    if case in ('shipped-street', 'talker-off-exit', 'legacy-talker'):
        zone = core.world.zones['sodium-row']
        exit_ = next(ex for ex in zone.template.meta.exits if ex.target_zone == 'sodium-tin-halo')
        tile = exit_.tile
        adjacent = tile[0]+1, tile[1]
    place(game, caller, zone.id, tile)
    game.commit_commerce()
    if case in ('hidden-exit', 'lift', 'tram'):
        exit_ = replace(exit_, hidden=case == 'hidden-exit',
                        kind=case if case in ('lift', 'tram') else exit_.kind)
        zone.template = replace(zone.template, meta=replace(zone.template.meta, exits=(exit_,)))
    if case in ('shipped-street', 'talker-off-exit', 'legacy-talker'):
        regular = next(actor for actor in zone.actors.values()
                       if actor.behaviour.get('template') == 'npc-sodium-regular')
        core.world.enter(regular, zone.id, adjacent)
        if case == 'legacy-talker':
            npc = core.characters.content.npcs['npc-sodium-regular']
            core.characters.content.npcs[npc.id] = replace(npc, dialogue=None,
                behaviours=(*npc.behaviours, Behaviour('talker')))
    elif case in ('hidden-exit', 'lift', 'tram', 'open-dialogue', 'contract-giver',
                  'mission-action', 'talker-before-terminal'):
        params = {'name': 'Threshold contact', 'dialogue': 'row-street-regular'}
        if case in ('contract-giver', 'mission-action'):
            params.update(dialogue='s39-giver', contract_handler='vesper')
        zone.objects['s39-contact'] = ObjectState(ObjectSpec('s39-contact', adjacent, 'vendor', params))
    elif case.startswith('vendor-') or case == 'open-shop':
        target = tile if case == 'vendor-underfoot' else adjacent
        zone.objects['s39-vendor'] = ObjectState(ObjectSpec('s39-vendor', target, 'vendor',
            {'name': 'Threshold counter', 'vendor': 'vesper'}))
    elif case == 'prop-underfoot':
        zone.objects['s39-bank'] = ObjectState(ObjectSpec('s39-bank', tile, 'bank', {'name': 'Threshold bank'}))
    elif case == 'board':
        zone.objects['s39-board'] = ObjectState(ObjectSpec('s39-board', adjacent, 'terminal',
            {'name': 'Threshold board', 'contract_handler': 'vesper'}))
    elif case == 'doorstep':
        unit = next(iter(core.apartments.geometry.units.values()))
        place(game, caller, unit.zone, unit.anchor.doorstep)
        game.commit_commerce()
    if case in ('talker-off-exit', 'vendor-off-exit'):
        # Both exit and contact are adjacent to this tile.
        core.world.enter(sim.avatars[session.user_id].actor, zone.id, (tile[0], tile[1]+1))
    if case == 'mission-action':
        mission(core, session, zone.id, 's39-contact')
    if case == 'open-dialogue':
        contact = core.dialogue.contact(session, 's39-contact')
        core.dialogue.open(session, contact, game.clock.now_tick())
        game.commit_commerce()
        assert session.id in core.dialogue.menus
    if case == 'open-shop':
        core.commerce.menus[session.id] = CommerceMenu('vendor', 's39-vendor', opened=game.clock.now_tick())
    if case == 'talker-before-terminal':
        zone.objects['s39-terminal'] = ObjectState(ObjectSpec('s39-terminal', adjacent, 'terminal',
            {'name': 'Threshold terminal', 'sector': 'lat-sodium'}))
    return game, caller


def execute(game: HeadlessServer, caller: FakeClient, frame: Frame) -> dict[str, Any]:
    """Record the consuming production handler and its committed outcome."""
    core, session = game.core, caller.session
    observed: list[str] = []
    routes = core.input_routes()
    def instrument(route: Any) -> Any:
        def handler(*args: Any, **kwargs: Any) -> Any:
            result = route.handler(*args, **kwargs)
            if result or route.final:
                observed.append(route.name)
            return result
        return replace(route, handler=handler)
    core.input_routes = lambda: [instrument(route) for route in routes]
    predicted = core.resolve_interaction(session, frame)
    focus = core.interaction_views(session)
    core._echo(Event('input', {'session': session, 'frame': frame, 'tick': game.clock.now_tick()}))
    game.commit_commerce()
    assert len(observed) == 1, observed
    screen = core.dialogue.menus.get(session.id)
    return {'predicted': predicted.route.name, 'focus': focus,
            'outcome': {**outcome(game, caller, observed[0]),
                        'dialogue': (screen.contact.talker if screen else None),
                        'missions': [(job.template, job.index, job.state)
                                     for job in core.contracts.state.engine.instances.values()]}}


def run(root: Path) -> dict[str, Any]:
    content = load_content(root/'src/karst41/content')
    return {case: {key: execute(*setup(content, case), Frame('key', {'k': key}))
                   for key in ('e', 'j')} for case in CASES}
