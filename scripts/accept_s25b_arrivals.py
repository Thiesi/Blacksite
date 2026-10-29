"""S25b arrival captures from live NetBBS Telnet/native stdio play.

The hub uses the shipped ten-zone world. The Undercity uses the generated
34-zone private overlay and a labelled walked shortcut from Wake Hall.
No player placement, discovery call or composed terminal frame is used.
"""

import argparse
import asyncio
import json
from pathlib import Path
import subprocess
from typing import Any

from accept_s10_netbbs import Connection, NativeProbe, wait
from build_city_content import build, read, write
from blacksite.content.loader import load_content
from blacksite.content.validate import validate
from blacksite.door.layout import compute
from tests.presentation.snapshots import snapshot


def generated_fixture(root: Path) -> dict[str, Any]:
    local = root/'world/content.local'
    build(local)
    tree = load_content(local)
    wake = read(local/'zones/vatside-wake-hall.json')
    under = read(local/'zones/under-service.json')
    spawn = tuple(under['spawn'])
    zone = tree.zones['under-service']
    used = {obj.tile for obj in zone.meta.objects} | {ex.tile for ex in zone.meta.exits}
    back = next(tile for tile in ((spawn[0]-1, spawn[1]), (spawn[0]+1, spawn[1]),
                                 (spawn[0], spawn[1]-1), (spawn[0], spawn[1]+1))
                if tile not in used and zone.tile_at(tile) in tree.tiles
                and tree.tiles[zone.tile_at(tile)].passable
                and not tree.tiles[zone.tile_at(tile)].hazard)
    shortcut = (32, 16)  # Outside the Wake outfitter's 33..35 spawn region.
    assert tree.tiles[tree.zones[wake['id']].tile_at(shortcut)].passable
    wake['exits'].append(dict(id='fixture-under-service', tile=list(shortcut),
        target_zone=under['id'], target_tile=list(spawn), kind='street'))
    under['exits'].append(dict(id='fixture-return-wake', tile=list(back),
        target_zone=wake['id'], target_tile=wake['spawn'], kind='street'))
    for meta, marker in ((wake, shortcut), (under, back)):
        write(local/'zones'/(meta['id']+'.json'), meta)
        path = local/'zones'/(meta['id']+'.map')
        rows = [list(row) for row in path.read_text(encoding='utf-8').splitlines()]
        rows[marker[1]][marker[0]] = '>'
        path.write_text('\n'.join(''.join(row) for row in rows)+'\n', encoding='utf-8', newline='\n')
    problems = validate(load_content(local))
    assert not problems, problems
    return {'generated_zones': len(tree.zones), 'shortcut': list(shortcut),
        'return': list(back), 'fixtures': [
            'generated 34-zone private content.local overlay',
            f'two marked street exits on existing passable tiles between Wake Hall and {under["name"]}'],
        'not_claimed': ['full-city walking', 'human pacing', 'layout approval']}


async def capture(probe: NativeProbe, caller: Connection, tier: str,
                  scenario: str, before_ids: set[str]) -> dict[str, Any]:
    zone = probe.service.world.zones[caller.avatar.zone].template
    await wait(lambda: zone.meta.name in caller.caller.screen.screen_text().splitlines()[0]
               and caller.session.ack_revision == caller.session.view_revision)
    # Let the live door flush the log alongside the acknowledged view. This
    # is transport readiness, not a simulation-time or performance fixture.
    await asyncio.sleep(.1)
    asset = probe.game.content.text[zone.meta.lore[0]]
    expected = ' '.join(asset.body.strip().split('\n\n', 1)[0].splitlines())
    logs = [line for line in caller.session.log_ring if line['id'] not in before_ids]
    arrival = next(line for line in logs if line['channel'] == 'zone' and line['text'] == expected)
    screen = caller.caller.screen
    layout = compute(screen.width, screen.height)
    log_rows = [''.join(screen.grid[y][layout.log.x:layout.log.x+layout.log.width])
                for y in range(layout.log.y, layout.log.y+layout.log.height)]
    def compact(text: str) -> str:
        return ''.join(text.split())
    label = f'arrival-{scenario}-{screen.width}x{screen.height}-{tier}'
    observed = {'scenario': scenario, 'zone': zone.id, 'size': [screen.width, screen.height],
        'tier': tier, 'negotiated_tier': caller.session.caps['tier'],
        'arrival_text': expected, 'arrival_role': arrival['role'],
        'arrival_retained_in_ring': True,
        'whole_paragraph_visible': compact(expected) in compact(''.join(log_rows)),
        'arrival_first_log_since_walk_or_connection': logs[0]['id'] == arrival['id'],
        'arrival_last_log_since_walk_or_connection': logs[-1]['id'] == arrival['id'],
        'observed_log_rows': log_rows, 'new_log_lines': logs,
        'ansi': label+'.ans', 'text': label+'.txt', 'context': label+'.json'}
    assert observed['negotiated_tier'] == tier, observed
    # All three files describe one received live state. Nothing is injected
    # into the terminal; the ANSI transcript includes the real node picker.
    probe.save(caller, label)
    write(probe.root/(label+'.json'), {'capture': observed, 'snapshot': snapshot(screen)})
    if not observed['whole_paragraph_visible']:
        # Keep the initially clipped screen as evidence. Then use the real
        # local scrollback hotkey to prove the retained paragraph is usable.
        await caller.caller.write(b'\x10')
        await wait(lambda: 'SCROLLBACK' in caller.caller.screen.screen_text())
        visible = False
        for _ in range(4):
            rows = [''.join(screen.grid[y][layout.viewport.x:layout.viewport.x+layout.viewport.width])
                    for y in range(layout.viewport.y, layout.viewport.y+layout.viewport.height)]
            visible = compact(expected) in compact(''.join(rows))
            if visible:
                break
            await caller.caller.write(b'\x1b[6~')
            await asyncio.sleep(.1)
        scroll_label = label+'-scrollback'
        probe.save(caller, scroll_label)
        observed['scrollback'] = {'ansi': scroll_label+'.ans', 'text': scroll_label+'.txt',
            'context': scroll_label+'.json', 'whole_paragraph_visible': visible}
        write(probe.root/(scroll_label+'.json'), {'scenario': scenario, 'scene': 'live Ctrl-P scrollback',
            'size': [screen.width, screen.height], 'tier': tier, 'whole_paragraph_visible': visible,
            'snapshot': snapshot(screen)})
        assert visible, observed
        await caller.caller.write(b'\x1b')
        await wait(lambda: 'SCROLLBACK' not in caller.caller.screen.screen_text())
    return observed


async def accept(root: Path, door_python: Path, tier: str, show: bool) -> None:
    root.mkdir(parents=True, exist_ok=False)
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    dirty = bool(subprocess.check_output(['git', 'status', '--porcelain'], text=True).strip())
    captures: list[dict[str, Any]] = []
    worlds: list[dict[str, Any]] = []
    for generated in (False, True):
        path = root/('generated' if generated else 'shipped')
        fixture = generated_fixture(path) if generated else {'fixtures': [], 'generated_zones': 0}
        probe = NativeProbe(path, door_python, show)
        await probe.start()
        try:
            for width, height in ((80, 24), (132, 50)):
                caller = await probe.open(width, height, 'Arrival', 0,
                    tier == '16', truecolor=tier == 'truecolor')
                if generated:
                    await probe.walk(caller, (21, 14))
                    await caller.caller.write(b'b')
                    player = probe.game.players[caller.session.player_id]
                    await wait(lambda: player.progress.get('wake_combat') == 'skipped')
                    before = {line['id'] for line in caller.session.log_ring}
                    await probe.travel(caller, 'under-service')
                    await wait(lambda: (caller.session.player_id, 'zone', caller.avatar.zone)
                        not in probe.service.core.progression.pending_discoveries)
                    await wait(lambda: any(line['text'] == 'You gain 25 XP.'
                        for line in caller.session.log_ring if line['id'] not in before))
                    row = await capture(probe, caller, tier, 'under-service', before)
                    assert row['whole_paragraph_visible'], row
                    await probe.travel(caller, 'vatside-wake-hall')
                else:
                    row = await capture(probe, caller, tier, 'wake-hall', set())
                row['directory'] = path.name
                captures.append(row)
                await probe.leave(caller, f'finished-{width}x{height}-{tier}')
            assert not probe.errors, probe.errors
            client = read(path/'native-client.json')
            worlds.append({'directory': path.name, 'served_zones': len(probe.game.content.zones),
                'served_content_sha256': probe.game.content.hash,
                'native_python_tree_sha256': client['python_tree_sha256'],
                'startup_seconds': probe.server_start_seconds, **fixture})
        finally:
            await probe.close()
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip() == head
    assert bool(subprocess.check_output(['git', 'status', '--porcelain'], text=True).strip()) == dirty
    write(root/'result.json', {'passed': True, 'head': head, 'dirty': dirty,
        'transport': 'NetBBS Telnet -> registered native stdio',
        'human_approval': False, 'performance_gate': 'not asserted here; separate full native matrix required',
        'method': 'real character-creation keys and walked exits; received ANSI replay, never a composed frame',
        'worlds': worlds, 'captures': captures})
    print(json.dumps({'passed': True, 'tier': tier, 'captures': len(captures)}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--door-python', type=Path, required=True)
    parser.add_argument('--tier', choices=('16', '256', 'truecolor'), required=True)
    parser.add_argument('--show', action='store_true')
    args = parser.parse_args()
    asyncio.run(accept(args.root.resolve(), args.door_python, args.tier, args.show))
