"""P8: the Row speaks, then goes quiet in combat (native NetBBS evidence).

One renderer per run (legacy default door views, or the opt-in
presentation), each colour tier in turn, over NetBBS Telnet to the
registered native stdio door. Real keys throughout: travel to the Row, a
real target and a real F shot.

Declared fixtures:
- One Sodium regular is relocated beside the caller and holds still, so
  it is inside the six-tile bark radius when filmed.
- That regular's bark is made due, and the Row's ambience is made due once
  the caller's budget has reopened. That saves waiting the 90 s interval
  and the 60-90 s cadence. The budget, the suppression and the line
  choice are untouched.
- The keeper's guards hold fire (as in S44), so the shot doesn't end the
  run in a death. During the quiet window the regular's bark and the Row's
  ambience are forced due every half second, to show suppression, not
  silence, is what keeps the log clear.
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
from accept_s44_netbbs import enter_row
from karst41.server import ambience as amb
from karst41.server.clock import TICK_HZ
from tests.presentation.snapshots import snapshot

ROW = 'sodium-row'
SPOT, BESIDE = (25, 6), (27, 6)


async def accept(root: Path, door_python: Path, width: int, height: int, modern: bool, show: bool) -> None:
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    assert not subprocess.check_output(['git', 'status', '--porcelain'], text=True).strip()
    root.mkdir(parents=True, exist_ok=False)
    renderer = 'present' if modern else 'legacy'
    probe = NativeProbe(root, door_python, show, door_environment={
        'DOOR_KARST41_PRESENTATION': '1' if modern else '0'}, show_all_tiers=True)
    await probe.start()
    rows: list[dict[str, Any]] = []
    try:
        core = probe.service.core
        clock = probe.service.clock
        voice_of = core.dialogue.ambience
        zone = probe.service.world.zones[ROW]
        look = probe.service.world.content.looks[ROW]
        tram = probe.service.world.content.dialogue['row-street-regular'].barks[0].text
        for tier in ('16', '256', 'truecolor'):
            caller = await probe.open(width, height, 'Ear'+tier, sixteen=tier == '16', truecolor=tier == 'truecolor')
            assert caller.session.caps['tier'] == tier, caller.session.caps
            heard: list[tuple[int, str, str]] = []
            send = caller.session.send

            def listen(frame: Any, send: Any = send, heard: list = heard) -> bool:
                # Observation only: note every bark or ambient line delivered.
                if frame.type == 'log' and not frame.data.get('replay'):
                    heard.extend((clock.now_tick(), line['kind'], line['text']) for line in frame.data['lines'])
                return send(frame)
            caller.session.send = listen

            def screen() -> str:
                return caller.caller.screen.screen_text()

            def shows(text: str) -> bool:
                # A log line can wrap at 80x24; its opening words sit on one row.
                return text[:28] in screen()

            async def delivered(who: Connection = caller) -> None:
                await wait(lambda: who.session.ack_revision == who.session.view_revision)

            def save(scenario: str, facts: dict[str, Any]) -> None:
                label = f'p8-{scenario}-{width}x{height}-{tier}-{renderer}'
                probe.save(caller, label)
                (root/(label+'.json')).write_text(json.dumps(snapshot(caller.caller.screen),
                    ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
                rows.append({'capture': label, 'scenario': scenario, 'size': [width, height], 'tier': tier,
                             'renderer': renderer, **facts,
                             'sha256': {suffix: sha256((root/(label+suffix)).read_bytes()).hexdigest()
                                        for suffix in ('.ans', '.txt', '.json')}})

            async def budget_open() -> None:
                await wait(lambda: (state := voice_of.callers.get(caller.session.id)) is not None and (
                    state.last_line is None or clock.now_tick() - state.last_line >= amb.LINE_BUDGET_SECONDS * TICK_HZ),
                    amb.LINE_BUDGET_SECONDS + 5)

            await enter_row(probe, caller)
            await probe.walk(caller, SPOT)
            me = caller.avatar.actor
            regular = min((a for a in zone.actors.values() if a.behaviour.get('template') == 'npc-sodium-regular'),
                          key=lambda a: ((a.x-me.x)**2+(a.y-me.y)**2, a.id))
            probe.service.world.enter(regular, ROW, probe.service.world.free_tile(ROW, BESIDE, regular))
            regular.behaviour.update(home=regular.position, pause=1 << 40)
            await wait(lambda: ROW in voice_of.zones)
            voice = voice_of.zones[ROW]

            # 1. A regular's bark arrives.
            await budget_open()
            voice.barks.next_due[regular.id] = 0
            await wait(lambda: any(kind == 'speech' and tram in text for _, kind, text in heard))
            await wait(lambda: shows(tram))
            await delivered()
            bark = next(text for _, kind, text in heard if kind == 'speech' and tram in text)
            save('bark', {'line': bark, 'regular': list(regular.position), 'player': list(me.position)})

            # 2. A Row ambience line arrives.
            await budget_open()
            mark = len(heard)  # The trip here passed zones with their own ambience.
            voice.ambient_due = clock.now_tick()
            await wait(lambda: any(kind == 'ambient' for _, kind, _ in heard[mark:]))
            line = next(text for _, kind, text in heard[mark:] if kind == 'ambient')
            assert line in look.ambient
            await wait(lambda: shows(line))
            await delivered()
            save('ambience', {'line': line})

            # 3. Combat: a real shot. Barks and ambience stop.
            async def hold_fire() -> None:
                while True:
                    for guard in zone.actors.values():
                        if guard.behaviour.get('template') == 'npc-sable-enforcer':
                            guard.cooldowns['weapon'] = 10**12
                    await asyncio.sleep(.05)
            holding = asyncio.create_task(hold_fire())
            try:
                await budget_open()
                await probe.target(caller, regular.id)
                mark = len(caller.session.log_ring)
                async with asyncio.timeout(20):
                    while not any(ln.get('kind') in ('combat', 'danger') for ln in list(caller.session.log_ring)[mark:]):
                        await caller.caller.write(b'f')
                        await asyncio.sleep(.3)
                shot = clock.now_tick()
                combat = next(ln['text'] for ln in list(caller.session.log_ring)[mark:]
                              if ln.get('kind') in ('combat', 'danger'))
                quiet_until = shot + (amb.DANGER_HOLD_SECONDS - 2) * TICK_HZ
                while clock.now_tick() < quiet_until:
                    voice.barks.next_due[regular.id] = 0
                    voice.ambient_due = clock.now_tick()
                    await asyncio.sleep(.5)
                late = [(t, kind, text) for t, kind, text in heard if t > shot and kind in ('ambient', 'speech')
                        and (kind == 'ambient' or tram in text)]
                assert not late, late
                await wait(lambda: shows(combat))
                await delivered()
                save('combat-quiet', {'combat_line': combat, 'quiet_seconds': (clock.now_tick()-shot)/TICK_HZ,
                                      'forced_due_every_seconds': .5, 'delivered_in_window': late})
            finally:
                holding.cancel()
            await probe.leave(caller, f'p8-left-{width}x{height}-{tier}-{renderer}')
        assert not probe.errors and probe.service.failure is None
        (root/'p8-results.json').write_text(json.dumps({
            'passed': True, 'head': head, 'transport': 'NetBBS Telnet -> registered native stdio',
            'renderer': renderer, 'size': [width, height], 'captures': rows,
            'numbers': {'line_budget_seconds': amb.LINE_BUDGET_SECONDS, 'ambient_seconds': amb.AMBIENT_SECONDS,
                        'ambient_jitter_seconds': amb.AMBIENT_JITTER_SECONDS,
                        'danger_hold_seconds': amb.DANGER_HOLD_SECONDS},
            'fixtures': ['one Sodium regular relocated beside the caller and holding still',
                         'its bark made due, and the Row ambience made due once the budget reopened',
                         'keeper guards hold fire (S44 precedent); during the quiet window bark and ambience '
                         'are forced due every 0.5 s'],
            'presentation_acceptance': False, 'h1_layout_approval': False,
            's25_layout_approval': False}, indent=2)+'\n', encoding='utf-8', newline='\n')
        probe.report(f'P8 PASS {width}x{height}/{renderer}: bark, ambience, quiet in combat')
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
    parser.add_argument('--presentation', choices=('legacy', 'modern'), required=True)
    parser.add_argument('--show', action='store_true')
    args = parser.parse_args()
    width, height = map(int, args.size.split('x'))
    asyncio.run(accept(args.root, args.door_python, width, height, args.presentation == 'modern', args.show))
