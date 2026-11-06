"""S39: S19 network route and live exit/mission focus through native stdio.

The S19 route uses shipped content. Captures additionally declare one
relocated, paused regular and a survey giver beside the Tin Halo exit.
No player teleport, composed frame, or wait for a talker to release E.
"""

import argparse
import asyncio
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import traceback
from typing import Any

from accept_s10_netbbs import Connection, wait
from accept_s19_netbbs import ContractProbe, first_job
from accept_s38_netbbs import enter_row
from blacksite.content.schema import ContractTemplate, ObjectSpec, Reward, Stage, StageTarget
from blacksite.layout import compute
from blacksite.server.world.zone import ObjectState
from tests.presentation.snapshots import snapshot


async def acknowledged(probe: ContractProbe, caller: Connection, previous: int) -> dict[str, Any]:
    """Wait for delivery, never for a particular interaction choice."""
    await wait(lambda: caller.session.view_revision > previous
               and caller.session.ack_revision == caller.session.view_revision
               and probe.game.sim.views[caller.session.id].previous is not None)
    return probe.game.sim.views[caller.session.id].previous['body']


async def captures(probe: ContractProbe, width: int, height: int, tier: str) -> list[dict[str, Any]]:
    caller = await probe.open(width, height, 'S39'+tier, sixteen=tier == '16', truecolor=tier == 'truecolor')
    assert caller.session.caps['tier'] == tier
    await enter_row(probe, caller)
    zone = probe.service.world.zones['sodium-row']
    exit_ = next(ex for ex in zone.template.meta.exits if ex.target_zone == 'sodium-tin-halo')
    await probe.walk(caller, exit_.tile)
    regular = next(actor for actor in zone.actors.values() if actor.behaviour.get('template') == 'npc-sodium-regular')
    occupied = {a.position for a in zone.actors.values() if a is not regular}
    candidates = [(exit_.tile[0]+dx, exit_.tile[1]+dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)]
    tile = next(tile for tile in candidates if tile not in occupied and zone.can_enter(regular, tile))
    probe.service.world.enter(regular, zone.id, tile)
    regular.behaviour['pause'] = probe.service.clock.now_tick()+60_000
    previous = caller.session.view_revision
    probe.game.sim.reset_view(caller.session, caller.avatar)
    body = await acknowledged(probe, caller, previous)
    assert body['focus']['id'] == exit_.id and body['focus']['verb'] == 'go to', body['focus']
    rows = []
    def save(scenario: str, body: dict[str, Any]) -> None:
        label = f's39-{scenario}-{width}x{height}-{tier}'
        hint = caller.caller.screen.screen_text().splitlines()[compute(width, height).hint.y]
        assert body['focus']['verb'] in hint, hint
        probe.save(caller, label)
        (probe.root/(label+'.json')).write_text(json.dumps(snapshot(caller.caller.screen),
            ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
        rows.append({'capture': label, 'scenario': scenario, 'size': [width, height], 'tier': tier,
                     'focus': body['focus'], 'sha256': {suffix: sha256((probe.root/(label+suffix)).read_bytes()).hexdigest()
                                                       for suffix in ('.ans', '.txt', '.json')}})
    save('exit-beside-regular', body)
    await probe.travel(caller, 'sodium-tin-halo')

    # No shipped giver is beside an exit (see audit_s39_layout.py).
    # Declare a physical giver and a survey mission using normal contracts.
    core = probe.service.core
    zone = probe.service.world.zones['sodium-tin-halo']
    exit_ = next(ex for ex in zone.template.meta.exits if ex.target_zone == 'sodium-row')
    adjacent = exit_.tile[0]+1, exit_.tile[1]
    core.characters.content.dialogue['s39-giver'] = replace(core.characters.content.dialogue['vesper'], id='s39-giver')
    zone.objects['s39-contact'] = ObjectState(ObjectSpec('s39-contact', adjacent, 'vendor',
        {'name': 'Threshold contact', 'dialogue': 's39-giver', 'contract_handler': 'vesper'}))
    owner = core.contracts
    target = StageTarget('object', zone=zone.id, object='s39-contact')
    stage = Stage('survey', 'survey', target, 'interact', 'surveyed', 's39:survey')
    job = ContractTemplate('s39-survey', 'vesper', stages=(stage,), reward=Reward((0, 0)), min_grade=1, story=True)
    owner.content.contracts[job.id] = owner.state.engine.templates[job.id] = job
    draft = owner.state.fork()
    instance = draft.engine.accept(draft.engine.story_offer(job.id, caller.session.player_id),
                                  (owner.participant(caller.session.player_id),), owner.now())
    owner.write(draft)
    await wait(lambda: not probe.commerce.pending and not probe.commerce.waiting)
    await probe.walk(caller, exit_.tile)
    previous = caller.session.view_revision
    probe.game.sim.reset_view(caller.session, caller.avatar)
    body = await acknowledged(probe, caller, previous)
    assert body['focus']['id'] == 's39-contact' and body['focus']['verb'] == 'survey', body['focus']
    save('mission-beside-giver', body)
    await caller.caller.write(b'e')
    await wait(lambda: owner.state.engine.instances[instance.id].state == 'complete')
    assert caller.avatar.zone == zone.id and caller.avatar.travel is None
    assert caller.session.id not in core.dialogue.menus
    await probe.leave(caller, f's39-left-{width}x{height}-{tier}')
    probe.report(f'S39 PASS {width}x{height}/{tier}: exit beside regular; survey beats exit and giver')
    return rows


async def accept(root: Path, python: Path, show: bool, sizes: tuple[tuple[int, int], ...]) -> None:
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    assert not subprocess.check_output(['git', 'status', '--porcelain'], text=True).strip()
    probe = ContractProbe(root, python, show)
    # Show every colour tier on the attached terminal when requested.
    probe.show_all_tiers = True
    await probe.start()
    try:
        routes, screens = [], []
        # Finish every unmodified-content route before installing fixtures.
        for width, height in sizes:
            routes.append(await first_job(probe, width, height, True))
        for width, height in sizes:
            for tier in ('16', '256', 'truecolor'):
                screens.extend(await captures(probe, width, height, tier))
        assert not probe.errors and probe.service.failure is None
        (root/'s39-results.json').write_text(json.dumps({'passed': True, 'head': head,
            'transport': 'NetBBS Telnet -> registered native stdio', 'wait_for_focus': False,
            'network_routes': routes, 'captures': screens,
            'fixtures': ['relocated paused Sodium regular', 'physical dialogue copy of Vesper',
                         'survey mission at declared giver beside Tin Halo exit']}, indent=2)+'\n', encoding='utf-8')
    except BaseException:
        (root/'failure-trace.txt').write_text(traceback.format_exc(), encoding='utf-8')
        raise
    finally:
        await probe.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--door-python', type=Path, required=True)
    parser.add_argument('--show', action='store_true')
    parser.add_argument('--size', choices=('both', '80x24', '132x50'), default='both')
    args = parser.parse_args()
    sizes = ((80, 24), (132, 50)) if args.size == 'both' else (tuple(map(int, args.size.split('x'))),)
    asyncio.run(accept(args.root, args.door_python, args.show, sizes))
