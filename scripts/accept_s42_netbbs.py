"""S42: real talk, walk away, flee close and masked shot feedback.

One relocated regular and a 2.5-second initial movement cooldown make
the flee scenario repeatable. A relocated covered actor has a 10-second
movement cooldown for its shot capture. No shot, flee step, player move,
page close, or log message is injected. Shipped layout stays untouched.
"""

import argparse
import asyncio
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import traceback
from typing import Any

from accept_s10_netbbs import NativeProbe, wait
from accept_s38_netbbs import enter_row
from blacksite.layout import compute
from tests.presentation.snapshots import snapshot


async def accept(root: Path, python: Path, size: tuple[int, int], tier: str, show: bool) -> None:
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    assert not subprocess.check_output(['git', 'status', '--porcelain'], text=True).strip()
    probe = NativeProbe(root, python, show, show_all_tiers=True)
    await probe.start()
    try:
        width, height = size
        caller = await probe.open(width, height, 'S42'+tier, sixteen=tier == '16', truecolor=tier == 'truecolor')
        assert caller.session.caps['tier'] == tier
        await enter_row(probe, caller)
        await probe.walk(caller, (5, 5))
        core = probe.service.core
        zone = probe.service.world.zones['sodium-row']
        regular = next(actor for actor in zone.actors.values()
                       if actor.behaviour.get('template') == 'npc-sodium-regular')
        probe.service.world.enter(regular, zone.id, (6, 5))
        regular.behaviour.update(home=(6, 5), pause=probe.service.clock.now_tick()+60000)
        rows: list[dict[str, Any]] = []

        async def delivered() -> None:
            await wait(lambda: caller.session.ack_revision == caller.session.view_revision)

        def save(scenario: str) -> None:
            label = f's42-{scenario}-{width}x{height}-{tier}'
            probe.save(caller, label)
            (root/(label+'.json')).write_text(json.dumps(snapshot(caller.caller.screen),
                ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
            rows.append({'capture': label, 'scenario': scenario, 'size': [width, height], 'tier': tier,
                         'sha256': {suffix: sha256((root/(label+suffix)).read_bytes()).hexdigest()
                                    for suffix in ('.ans', '.txt', '.json')}})

        async def talk() -> None:
            await delivered()
            await caller.caller.write(b'e')
            await wait(lambda: caller.session.id in core.dialogue.menus)
            await wait(lambda: 'Move or Esc/B leaves' in caller.caller.screen.screen_text())
            await delivered()

        await talk()
        hint = caller.caller.screen.screen_text().splitlines()[compute(width, height).hint.y]
        assert 'Move or Esc/B leaves' in hint, hint
        save('talk-hint')
        await caller.caller.write(b'\x1b[D')
        await wait(lambda: caller.avatar.actor.position == (4, 5))
        assert caller.session.id not in core.dialogue.menus
        await delivered()
        save('one-press-walk-away')
        await probe.walk(caller, (5, 5))
        await probe.target(caller, regular.id)
        source = caller.avatar.actor
        before = source.position
        await caller.caller.write(b'f')
        await wait(lambda: (source.id, regular.id) in probe.combat.warnings)
        await wait(lambda: probe.service.clock.now_tick() >= probe.combat.warnings[source.id, regular.id]+20)
        # Only the first ordinary move is delayed. Once due, flee uses its
        # real destination, collision, cooldown and reserved-tile rules.
        regular.cooldowns['move'] = probe.service.clock.now_tick()+25
        health = regular.health
        await caller.caller.write(b'f')
        await wait(lambda: regular.target == source.id and not probe.commerce.pending)
        await talk()
        await wait(lambda: any(line['text'] == 'Sodium regular walks off.' for line in caller.session.log_ring))
        await wait(lambda: 'Sodium regular walks off.' in caller.caller.screen.screen_text())
        assert source.position == before and caller.session.id not in core.dialogue.menus
        assert regular.behaviour['state'] == 'flee'
        await delivered()
        save('shot-flee-walks-off')

        # Audit the actual combat log too: suppressing the old reveal must
        # not leave the true template name in Hit/Miss feedback.
        covered = next(actor for actor in zone.actors.values()
                       if actor.behaviour.get('template') == 'npc-plainclothes-warden')
        probe.service.world.enter(covered, zone.id, (6, 5))
        covered.cooldowns['move'] = probe.service.clock.now_tick()+100
        await probe.target(caller, covered.id)
        await caller.caller.write(b'f')
        await wait(lambda: (source.id, covered.id) in probe.combat.warnings)
        await wait(lambda: probe.service.clock.now_tick() >= probe.combat.warnings[source.id, covered.id]+20)
        mark = len(caller.session.log_ring)
        await caller.caller.write(b'f')
        def shot_lines() -> list[str]:
            return [line['text'] for line in list(caller.session.log_ring)[mark:]
                    if line['text'].startswith(('Hit:', 'Miss:'))]
        await wait(lambda: bool(shot_lines()) and not probe.commerce.pending)
        covered_line = shot_lines()[-1]
        assert covered_line in ('Hit: Sodium regular.', 'Miss: Sodium regular.'), covered_line
        assert source.id not in covered.revealed_to
        # A fresh view ACK follows the ordered log frame. Ctrl-L then
        # redraws that received state through the real client, even when
        # the old regular's identical name was already on screen.
        previous = caller.session.view_revision
        probe.game.sim.reset_view(caller.session, caller.avatar)
        await wait(lambda: caller.session.view_revision > previous
                   and caller.session.ack_revision == caller.session.view_revision)
        output_mark = len(caller.caller.output)
        await caller.caller.write(b'\x0c')
        await wait(lambda: b'\x1b[1;1H' in caller.caller.output[output_mark:]
                   and f'\x1b[{height};1H'.encode() in caller.caller.output[output_mark:])
        await wait(lambda: covered_line in caller.caller.screen.screen_text())
        assert 'Plainclothes Warden' not in caller.caller.screen.screen_text()
        save('covered-shot-label')
        await probe.leave(caller, f's42-left-{width}x{height}-{tier}')
        assert not probe.errors and probe.service.failure is None
        (root/'s42-results.json').write_text(json.dumps({'passed': True, 'head': head,
            'transport': 'NetBBS Telnet -> registered native stdio', 'captures': rows,
            'shot': {'health_before': health, 'health_after': regular.health,
                     'target': regular.target, 'state': regular.behaviour['state']},
            'covered_shot': {'template': covered.behaviour['template'],
                             'line': covered_line, 'revealed_to_caller': source.id in covered.revealed_to},
            'fixtures': ['one regular relocated beside the walked-to caller',
                         'regular ambient pause; ordinary flee ignores it',
                         'first flee movement cooldown 25 ticks',
                         'covered actor relocated for a real F shot; move cooldown 100 ticks'],
            'presentation_acceptance': False, 'h1_layout_approval': False,
            's25_layout_approval': False}, indent=2)+'\n', encoding='utf-8')
        probe.report(f'S42 PASS {width}x{height}/{tier}: talk hint, one press, real shot/flee walk-off, covered shot label')
    except BaseException:
        (root/'failure-trace.txt').write_text(traceback.format_exc(), encoding='utf-8')
        raise
    finally:
        await probe.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--door-python', type=Path, required=True)
    parser.add_argument('--size', choices=('80x24', '132x50'), required=True)
    parser.add_argument('--tier', choices=('16', '256', 'truecolor'), required=True)
    parser.add_argument('--show', action='store_true')
    args = parser.parse_args()
    asyncio.run(accept(args.root, args.door_python, tuple(map(int, args.size.split('x'))), args.tier, args.show))
