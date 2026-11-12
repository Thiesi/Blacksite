"""S44: the Row's truce rules, natively (NetBBS Telnet to registered native stdio).

One renderer per run (legacy default door views, or the opt-in
presentation), each colour tier in turn. Real keys throughout: travel,
targeting, firing, walking, the Halo's door, talk pages and the Ask.

Declared fixtures (technical lead's ruling on #214):
- **The bar is a test fixture.** Main's shipped Row is open ground with no
  bar alcoves. The walls of Upstairs are copied from
  tests/npcs/fixtures/issue187-row-demo.map (the #187 diagnosis map, round
  3 demo geometry) onto the live Row as a geometry layer in this
  acceptance server only. They never enter shipped content or the wheel.
- Grade 5 for the player-vs-player rules, as in S38.
- During the bar capture only, the keeper's guards hold fire (their weapon
  cooldown is pushed out), so the pursuit in and out of the bar can be
  filmed before the player dies, and only the nearest guard pursues: the
  other leaves the world and respawns from its spawner (a guard holding
  fire stands still while it sees you, so two inside can box the doorway).
  Routing, sight and the 20 s give-up are untouched. Fire is released for
  the death.
"""

import argparse
import asyncio
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import traceback
from typing import Any

from accept_s10_netbbs import Connection, NativeProbe, wait
from accept_p4_netbbs import navigate
from karst41 import truce_text
from karst41.content.formats import parse_map
from karst41.content.schema import TileChange, ZoneLayout
from karst41.layout import compute
from karst41.server.world.actors import Actor
from karst41.server.world.zone import GeometryLayer
from tests.presentation.snapshots import snapshot

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT/'tests/npcs/fixtures/issue187-row-demo.map'
BAR = (6, 4, 20, 8)  # Upstairs, walls included: x0, y0, x1, y1.
# Behind the doorway, seen from the street (SEEN); out of that line (INSIDE).
SEEN, INSIDE, DOORWAY = (13, 6), (8, 6), {(13, 8), (14, 8)}
ROW, HALO = 'sodium-row', 'sodium-tin-halo'
SETTLED = 'Sable considers it settled.'
LAYER = 's44-acceptance-bar-fixture'


def inject_bar(probe: NativeProbe) -> list[list[int]]:
    """Copy only Upstairs' walls from the #187 fixture onto the live Row."""
    content = probe.service.world.content
    chars = {tile.char: tile.id for tile in content.tiles.values()}
    grid, problems = parse_map(FIXTURE.read_text(encoding='utf-8'), 'S44 bar fixture', chars)
    assert not problems, problems
    zone = probe.service.world.zones[ROW]
    x0, y0, x1, y1 = BAR
    changes = tuple(TileChange((x, y), grid[y][x]) for y in range(y0, y1+1) for x in range(x0, x1+1)
                    if not content.tiles[grid[y][x]].passable and zone.passable((x, y)))
    assert changes and all(zone.template.tile_at(change.tile) for change in changes)
    zone.layers[LAYER] = GeometryLayer(LAYER, ZoneLayout(LAYER, changes), 0, 10**12)
    zone.compose(probe.service.core.clock.now_tick())
    assert all(not zone.passable(change.tile) for change in changes), 'fixture walls rejected'
    assert all(zone.passable(tile) for tile in DOORWAY | {INSIDE, SEEN})
    return [list(change.tile) for change in changes]


def in_bar(actor: Actor) -> bool:
    return 7 <= actor.x <= 18 and 5 <= actor.y <= 7


async def enter_row(probe: NativeProbe, caller: Connection) -> None:
    await probe.walk(caller, (21, 14))
    await caller.caller.write(b'b')
    await wait(lambda: probe.game.players[caller.session.player_id].progress.get('wake_combat') == 'skipped')
    for destination in ('vatside-clinics', 'core-plaza', ROW):
        await probe.travel(caller, destination)


async def accept(root: Path, door_python: Path, width: int, height: int, modern: bool, show: bool) -> None:
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    assert not subprocess.check_output(['git', 'status', '--porcelain'], text=True).strip()
    root.mkdir(parents=True, exist_ok=False)
    renderer = 'present' if modern else 'legacy'
    probe = NativeProbe(root, door_python, show, door_environment={
        'DOOR_KARST41_PRESENTATION': '1' if modern else '0'}, show_all_tiers=True)
    await probe.start()
    rows: list[dict[str, Any]] = []
    layout = compute(width, height)
    try:
        core = probe.service.core
        walls = inject_bar(probe)
        zone = probe.service.world.zones[ROW]
        for tier in ('16', '256', 'truecolor'):
            kwargs = {'archetype': 3, 'sixteen': tier == '16', 'truecolor': tier == 'truecolor'}
            caller = await probe.open(width, height, 'Row'+tier, **kwargs)
            assert caller.session.caps['tier'] == tier, caller.session.caps
            player = probe.game.players[caller.session.player_id]
            player.grade = 5
            probe.game.queue('save', player.bbs_user_id, player, immediate=True)
            me = caller.avatar.actor

            def screen() -> str:
                return caller.caller.screen.screen_text()

            async def delivered(who: Connection = caller) -> None:
                await wait(lambda: who.session.ack_revision == who.session.view_revision)

            def save(who: Connection, scenario: str, facts: dict[str, Any]) -> None:
                label = f's44-{scenario}-{width}x{height}-{tier}-{renderer}'
                probe.save(who, label)
                (root/(label+'.json')).write_text(json.dumps(snapshot(who.caller.screen),
                    ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
                rows.append({'capture': label, 'scenario': scenario, 'size': [width, height], 'tier': tier,
                             'renderer': renderer, **facts,
                             'sha256': {suffix: sha256((root/(label+suffix)).read_bytes()).hexdigest()
                                        for suffix in ('.ans', '.txt', '.json')}})

            # 1. The price on arrival, then beside the first truce warning.
            await enter_row(probe, caller)
            arrival = truce_text.arrival('Sable')
            await wait(lambda: arrival in screen())
            save(caller, 'price-arrival', {'notice': arrival})
            guards = [a for a in zone.actors.values() if a.behaviour.get('template') == 'npc-sable-enforcer']
            assert guards
            regular = next(a for a in zone.actors.values() if a.behaviour.get('template') == 'npc-sodium-regular')
            await caller.caller.write(b' ')  # The arrival notice has been seen.
            await navigate(probe, caller, regular)
            await probe.target(caller, regular.id)
            at_npc = truce_text.at_npc('Sable')
            await wait(lambda: 'Truce: Sable answers' in screen() and at_npc in screen())
            save(caller, 'price-target', {'notice': at_npc, 'warning': 'Truce: Sable answers'})

            # 2. The breach: HUNTED, and the keeper in pursuit on the open Row.
            for guard in guards:
                guard.cooldowns['weapon'] = 10**12  # Declared: hold fire for the pursuit capture.
            async with asyncio.timeout(40):
                while not any(g.target == me.id for g in guards):
                    await navigate(probe, caller, regular)
                    await probe.target(caller, regular.id)
                    await caller.caller.write(b'f')
                    await asyncio.sleep(.25)
            await wait(lambda: 'Sable is coming for you.' in [ln['text'] for ln in caller.session.log_ring])
            assert core.truce and player.keeper_answer and player.keeper_answer['keeper'] == 'sable'
            await wait(lambda: 'HUNTED' in screen().splitlines()[0])
            await wait(lambda: any(g.behaviour.get('state') == 'hunt' and (g.x-me.x)**2+(g.y-me.y)**2 <= 100
                                   for g in guards), 60)
            await delivered()
            save(caller, 'hunted-pursuit', {'hunted': True, 'guards': [list(g.position) for g in guards]})

            # 3. Into the bar; a guard follows in. Then out; it follows out.
            # Declared: one pursuer for this scene. Holding fire, a guard that
            # sees you stands still, so two guards inside can box the doorway.
            # The other leaves the world; its spawner brings it back.
            pursuer = min(guards, key=lambda g: ((g.x-me.x)**2+(g.y-me.y)**2, g.id))
            for guard in guards:
                if guard is not pursuer:
                    probe.service.world.leave(guard)
            guards = [pursuer]
            # The #187 shape: be seen behind the doorway, then step out of
            # its sight line, so the guard routes in to where it saw you.
            await probe.walk(caller, SEEN)
            await wait(lambda: any(g.target == me.id and tuple(g.behaviour.get('last_position', ())) == SEEN
                                   and core.combat.visible(g, me) for g in guards), 60)
            await probe.walk(caller, INSIDE)
            await wait(lambda: any(in_bar(g) and g.target == me.id for g in guards), 60)
            await delivered()
            follower = next(g for g in guards if in_bar(g))
            save(caller, 'bar-pursuit-in', {'fixture_walls': len(walls), 'guard': list(follower.position),
                                            'player': list(me.position)})
            trail = [follower.position]

            async def record() -> None:
                # Sample the guard's every step (the server ticks at 10 Hz)
                # while the player walks out, not only after the walk.
                while True:
                    if follower.position != trail[-1]:
                        trail.append(follower.position)
                    await asyncio.sleep(.02)
            recorder = asyncio.create_task(record())
            try:
                await probe.walk(caller, (40, 12))
                await wait(lambda: follower.y >= 9 and follower.target == me.id, 60)
            finally:
                recorder.cancel()
            assert DOORWAY & set(trail), trail
            await delivered()
            save(caller, 'bar-pursuit-out', {'guard_trail': [list(t) for t in trail], 'player': list(me.position)})

            # 4. The Halo's door refuses, with the minutes.
            door = next(ex for ex in zone.template.meta.exits if ex.target_zone == HALO)
            await probe.walk(caller, door.tile)
            await delivered()

            def door_focused() -> bool:
                view = probe.game.sim.views[caller.session.id].previous or {}
                return ((view.get('body', {}).get('focus') or {}).get('id') == door.id
                        and not any(abs(o.spec.tile[0]-me.x) <= 1 and abs(o.spec.tile[1]-me.y) <= 1
                                    and o.spec.id in core.commerce.caches for o in zone.objects.values()))
            await wait(door_focused)
            await caller.caller.write(b'e')
            refusal = 'Sable\'s still asking about you. Try me in'
            await wait(lambda: any(refusal in ln['text'] for ln in caller.session.log_ring))
            assert me.zone == ROW
            await wait(lambda: refusal in screen())
            line = next(ln['text'] for ln in caller.session.log_ring if refusal in ln['text'])
            save(caller, 'halo-refused', {'line': line})

            # 5. Death settles the debt. Fire is released, and the player goes
            # back within sight of the guards' posts (a guard that lost sight
            # 20 s ago has given up, as canon says). Not beside the Halo's
            # door or a post: the death's loot cache would take a later E.
            guards = [a for a in zone.actors.values() if a.behaviour.get('template') == 'npc-sable-enforcer']
            for guard in guards:
                guard.cooldowns['weapon'] = 0  # Fire released (respawned guards never held it).
            await probe.walk(caller, (52, 14))
            await wait(lambda: me.stance in ('down', 'dead'), 120)
            await wait(lambda: me.stance == 'normal' and SETTLED in [ln['text'] for ln in caller.session.log_ring], 90)
            assert player.keeper_answer is None
            await wait(lambda: SETTLED in screen())
            log = [ln['text'] for ln in caller.session.log_ring]
            vat = max(i for i, text in enumerate(log) if text.startswith('You wake in the vat.'))
            assert log[vat+1] == SETTLED, log[vat:vat+2]
            await delivered()
            save(caller, 'settled', {'line': SETTLED, 'zone': me.zone})
            await probe.leave(caller, f's44-left-a-{width}x{height}-{tier}-{renderer}')

            # 6. A fresh character opens an enforcer's page and asks.
            asker = await probe.open(width, height, 'Ask'+tier, **kwargs)
            await enter_row(probe, asker)
            await asker.caller.write(b' ')
            guard = min((g for g in zone.actors.values() if g.behaviour.get('template') == 'npc-sable-enforcer'),
                        key=lambda g: g.id)
            spot = next(t for t in ((guard.x-1, guard.y), (guard.x+1, guard.y), (guard.x, guard.y-1),
                                    (guard.x, guard.y+1))
                        if zone.passable(t) and not any(a.position == t for a in zone.actors.values()))
            await probe.walk(asker, spot)
            await delivered(asker)
            await asker.caller.write(b'e')
            await wait(lambda: asker.session.id in core.dialogue.menus)
            await wait(lambda: 'Ask about the peace' in asker.caller.screen.screen_text())
            await delivered(asker)
            save(asker, 'enforcer-talk', {'label': 'Ask about the peace'})
            await asker.caller.write(b'a')
            answer = 'Nobody draws. Somebody does, we come for them'
            await wait(lambda: answer in asker.caller.screen.screen_text())
            await delivered(asker)
            save(asker, 'enforcer-ask', {'question': "What's the arrangement here?",
                                         'answer': core.dialogue.menus[asker.session.id].line})
            await asker.caller.write(b'\x1b')
            await wait(lambda: asker.session.id not in core.dialogue.menus)
            await probe.leave(asker, f's44-left-b-{width}x{height}-{tier}-{renderer}')
        assert not probe.errors and probe.service.failure is None
        (root/'s44-results.json').write_text(json.dumps({
            'passed': True, 'head': head, 'transport': 'NetBBS Telnet -> registered native stdio',
            'renderer': renderer, 'size': [width, height], 'captures': rows,
            'fixtures': ["bar: Upstairs' walls copied from tests/npcs/fixtures/issue187-row-demo.map onto the live "
                         'Row as a geometry layer in this acceptance server only; main\'s Row has no alcoves',
                         'grade 5 for the player-vs-player rules (S38 precedent)',
                         'keeper guards hold fire during the bar pursuit capture only; released for the death',
                         'one pursuer in the bar scene: the other guard leaves the world and respawns from its spawner'],
            'fixture_walls': walls,
            'presentation_acceptance': False, 'h1_layout_approval': False,
            's25_layout_approval': False}, indent=2)+'\n', encoding='utf-8', newline='\n')
        probe.report(f'S44 PASS {width}x{height}/{renderer}: price, hunted, bar pursuit, Halo, settled, ask')
    except BaseException:
        (root/'failure-trace.txt').write_text(traceback.format_exc(), encoding='utf-8')
        raise
    finally:
        await probe.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--door-python', type=Path, required=True)
    parser.add_argument('--size', choices=('80x24', '132x50'), required=True)
    parser.add_argument('--presentation', choices=('legacy', 'modern'), required=True)
    parser.add_argument('--show', action='store_true')
    args = parser.parse_args()
    width, height = map(int, args.size.split('x'))
    asyncio.run(accept(args.root.resolve(), args.door_python, width, height,
                       args.presentation == 'modern', args.show))
