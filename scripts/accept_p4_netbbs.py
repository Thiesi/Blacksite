"""P4: additive view facts and first-entry history through native stdio.

Creation, movement, training skip, jack-in and menus use ordinary keys.
The private node/world has normal NPCs, rules and clock throughout.
One owned attack drone is provisioned through server commerce solely for
menu disclosure inspection, then deployed with ordinary keys. This is
an inventory fixture, not acquisition or balance acceptance.
"""

import argparse
import asyncio
import json
from copy import deepcopy
from pathlib import Path
import subprocess
from typing import Any

from accept_s10_netbbs import NativeProbe, wait
from tests.presentation.snapshots import snapshot
from blacksite.server.items import make_item


async def accept(root: Path, door_python: Path, show: bool,
                 sizes: tuple[tuple[int, int], ...]) -> None:
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    assert not subprocess.check_output(['git', 'status', '--porcelain'], text=True).strip()
    root.mkdir(parents=True, exist_ok=False)
    probe = NativeProbe(root, door_python, show)
    await probe.start()
    cases: list[dict[str, Any]] = []
    try:
        for width, height in sizes:
            for tier in ('16', '256', 'truecolor'):
                caller = await probe.open(width, height, 'P4'+tier, archetype=3,
                                          sixteen=tier == '16', truecolor=tier == 'truecolor')
                assert caller.session.caps['tier'] == tier
                screen = caller.caller.screen
                await wait(lambda: caller.session.ack_revision == caller.session.view_revision)
                def save(label: str) -> None:
                    probe.save(caller, label)
                    (root/(label+'.json')).write_text(json.dumps(snapshot(screen), ensure_ascii=False,
                        indent=2)+'\n', encoding='utf-8', newline='\n')
                body = probe.game.sim.views[caller.session.id].previous['body']
                assert body['me']['district'] == 'Vatside' and not body['me']['pvp']
                assert all('class' in a and 'jacked' in a for a in body['actors'])
                place = [line for line in caller.session.log_ring if line['kind'] == 'place']
                assert len(place) == 1
                assert all('kind' in line for line in caller.session.log_ring)
                assert not any('restart' in line['text'].lower() for line in caller.session.log_ring)
                save(f'wake-{width}x{height}-{tier}')
                await caller.caller.write(b'\x10')
                await wait(lambda: 'SCROLLBACK' in screen.screen_text() and place[0]['text'][:24] in screen.screen_text())
                save(f'place-history-{width}x{height}-{tier}')
                await caller.caller.write(b'\x1b')
                await wait(lambda: 'Wake Hall' in screen.screen_text().splitlines()[0])
                await probe.walk(caller, (21, 14))
                await caller.caller.write(b'b')
                await wait(lambda: probe.game.players[caller.session.player_id].progress.get('wake_combat') == 'skipped')
                await probe.walk(caller, (34, 15))
                await caller.caller.write(b'j')
                lat = probe.service.core.lattice
                await wait(lambda: caller.session.player_id in lat.presences and 'INTEGRITY' in screen.screen_text())
                await wait(lambda: caller.session.ack_revision == caller.session.view_revision)
                presence = lat.presences[caller.session.player_id]
                body = lat.view(caller.session, presence)
                assert body['theme'] and all('label' in edge for edge in body['edges'])
                assert all('owner' in cell and 'tier' in cell for cell in body['cells'] if cell['core'])
                assert body['me']['district'] == 'Vatside' and not body['me']['pvp']
                save(f'lattice-{width}x{height}-{tier}')
                await caller.caller.write(b'j')
                await wait(lambda: caller.avatar.actor.stance == 'normal')
                await wait(lambda: 'Wake Hall' in screen.screen_text().splitlines()[0])
                for destination in ('vatside-clinics', 'core-plaza', 'sodium-row'):
                    await probe.travel(caller, destination)
                zone = probe.service.world.zones['sodium-row']
                template = probe.game.content.npcs['npc-plainclothes-warden']
                npc = next(a for a in zone.actors.values()
                           if a.behaviour.get('template') == template.id)
                occupied = {a.position for a in zone.actors.values() if a is not caller.avatar.actor}
                adjacent = [(npc.x+dx, npc.y+dy) for dx, dy in
                            ((-1, 0), (0, 1), (1, 0), (0, -1))
                            if (npc.x+dx, npc.y+dy) not in occupied
                            and zone.can_enter(caller.avatar.actor, (npc.x+dx, npc.y+dy))]
                assert adjacent, 'The shipped covered NPC needs a reachable viewing tile.'
                await probe.walk(caller, adjacent[0])
                await probe.target(caller, npc.id)
                await wait(lambda: template.cover_name in screen.screen_text()
                           and caller.session.ack_revision == caller.session.view_revision)
                view = probe.game.sim.views[caller.session.id].previous['body']
                assert view['target']['name'] == template.cover_name
                assert view['target']['class'] == 'civilian' and view['target']['faction'] == 'Civilian'
                assert npc.name not in screen.screen_text()
                assert any(a.name == template.cover_name and a.behaviour.get('template') == 'npc-sodium-regular'
                           for a in zone.actors.values())
                save(f'sodium-cover-{width}x{height}-{tier}')
                # Declared inventory fixture: provision one owned attack drone
                # through the server's normal durable commerce boundary. Keep
                # NPC templates, positions, funds, rules and clocks untouched.
                player = probe.game.players[caller.session.player_id]
                iid = probe.game.sessions.origin+':p4-drone:'+caller.session.id
                await wait(lambda: not probe.commerce.pending)
                items = deepcopy(probe.commerce.items)
                items[iid] = make_item(iid, probe.game.content.items['drn_halvard_sentry'],
                                       player.id, probe.combat.clock.now_utc().isoformat())
                grant: dict[str, bool] = {}
                probe.commerce.settle(player, {'inventory': [*player.inventory, iid]},
                                      items, probe.commerce.caches, probe.commerce.serial,
                                      lambda success: grant.update(done=success))
                await wait(lambda: 'done' in grant)
                assert grant['done']
                drones = probe.service.core.progression.drones
                await caller.caller.write(b'o')
                await wait(lambda: caller.session.id in drones.menus and 'DRONES' in screen.screen_text())
                rows = drones.view(caller.session)['rows']
                index = next(i for i, row in enumerate(rows) if row['id'] == iid)
                for selected in range(index):
                    await caller.caller.write(b'\x1b[B')
                    await wait(lambda: drones.menus[caller.session.id] == selected+1)
                def selected_ready() -> bool:
                    _, body = probe.game.sim.overlays.get(caller.session.id, ('', {}))
                    rows = body.get('rows', [])
                    return (body.get('cursor') == index and len(rows) > index
                            and rows[index]['id'] == iid
                            and caller.session.ack_revision == caller.session.view_revision)
                # Menu actions carry the client's selected row and revision.
                # Server cursor movement alone does not mean it arrived yet.
                await wait(selected_ready)
                await caller.caller.write(b'u')
                await wait(lambda: iid in drones.actors and 'Target '+template.cover_name in screen.screen_text()
                           and caller.session.ack_revision == caller.session.view_revision)
                assert not npc.revealed_to
                assert npc.name not in screen.screen_text()
                save(f'drone-cover-{width}x{height}-{tier}')
                await caller.caller.write(b'\x1b')
                await wait(lambda: caller.session.id not in drones.menus
                           and 'Sodium Row' in screen.screen_text().splitlines()[0])
                # Leave from the public safe plaza through ordinary movement.
                await probe.travel(caller, 'core-plaza')
                await probe.leave(caller, f'finished-{width}x{height}-{tier}')
                cases.append({'size': [width, height], 'tier': tier, 'name': f'P4{tier}界{width}',
                    'place_line': place[0]['text'], 'world_history_has_kinds': True,
                    'crew_restart_outside_world_history': True, 'lattice_fields': True,
                    'shipped_npc_cover': template.cover_name, 'shipped_npc_class': 'civilian',
                    'drone_menu_cover': template.cover_name,
                    'inventory_fixture': 'one owned Halvard Sentry via server commerce; normal deploy/menu keys',
                    'clean_exit': True})
        assert not probe.errors, probe.errors
    finally:
        await probe.close()
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip() == head
    assert not subprocess.check_output(['git', 'status', '--porcelain'], text=True).strip()
    result = {'head': head, 'passed': True, 'cases': cases, 'human_approval': False,
        'transport': 'NetBBS Telnet -> registered native stdio',
        'fixtures': 'private node/world; one owned attack drone via server commerce for menu inspection only; no placement/funds/rules/clock fixtures'}
    (root/'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n',
                                  encoding='utf-8', newline='\n')
    print(json.dumps({'passed': True, 'cases': len(cases)}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--door-python', type=Path, required=True)
    parser.add_argument('--show', action='store_true')
    parser.add_argument('--size', choices=['80x24', '132x50'])
    args = parser.parse_args()
    sizes = ((tuple(map(int, args.size.split('x'))),) if args.size else ((80, 24), (132, 50)))
    asyncio.run(accept(args.root.resolve(), args.door_python, args.show, sizes))
