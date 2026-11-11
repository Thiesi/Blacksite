"""P12: talk lines, talk actions, whole log entries and a wrapped detail.

Native NetBBS Telnet to registered native stdio, in one renderer per
run (legacy default door views or the opt-in presentation).

Declared fixtures (P12 #204; technical lead and presentation lead agreed
on #204's capture plan): on main the s27-cast talkers are still
"authoring", so no shipped talker with a long line or offers can be met.
Two contact objects in the Tin Halo carry copies of the shipped
`halvard` and `vesper` dialogue, unchanged except their ids
(`p12-halvard`, `p12-vesper`), following S39's precedent. Halvard's
record line needs journal evidence `s19-hal-s1-1-recovery` and a prior
meeting, both granted. The vendor capture uses the real Wake Hall
outfitter. Talk pages are opened with E, closed with Esc; no frame,
log line or page is injected.
"""

import argparse
import asyncio
from collections import deque
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import traceback
from typing import Any

from accept_s10_netbbs import wait
from accept_s19_netbbs import ContractProbe
from karst41.content.schema import ObjectSpec
from karst41.door.fit import wrap_text
from karst41.layout import compute
from karst41.server.world.zone import ObjectState
from tests.presentation.snapshots import snapshot

EVIDENCE = 's19-hal-s1-1-recovery'
OUTFITTER, SIDEARM = 'wake-outfitter', 'wpn_kestrel_sidearm'


async def accept(root: Path, door_python: Path, width: int, height: int, modern: bool, show: bool) -> None:
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    assert not subprocess.check_output(['git', 'status', '--porcelain'], text=True).strip()
    root.mkdir(parents=True, exist_ok=False)
    renderer = 'present' if modern else 'legacy'
    probe = ContractProbe(root, door_python, show, door_environment={
        'DOOR_KARST41_PRESENTATION': '1' if modern else '0'}, show_all_tiers=True)
    await probe.start()
    rows: list[dict[str, Any]] = []
    layout = compute(width, height)
    try:
        core = probe.service.core
        dialogue = core.characters.content.dialogue
        for did in ('halvard', 'vesper'):
            dialogue['p12-'+did] = replace(dialogue[did], id='p12-'+did)
        record = next(ln for ln in dialogue['p12-halvard'].lines if ln.id == 'record-hal-s1-1-recovery')
        assert len(wrap_text(record.text, layout.menu.talk.width)) >= (3 if width == 80 else 2)

        for tier in ('16', '256', 'truecolor'):
            full = tier == 'truecolor'  # captures 2-4 once per size and renderer
            caller = await probe.open(width, height, 'P12'+tier, sixteen=tier == '16', truecolor=full)
            assert caller.session.caps['tier'] == tier, caller.session.caps

            async def delivered() -> None:
                await wait(lambda: caller.session.ack_revision == caller.session.view_revision)

            def screen() -> list[str]:
                return caller.caller.screen.screen_text().split('\n')

            def save(scenario: str, facts: dict[str, Any]) -> None:
                label = f'p12-{scenario}-{width}x{height}-{tier}-{renderer}'
                probe.save(caller, label)
                (root/(label+'.json')).write_text(json.dumps(snapshot(caller.caller.screen),
                    ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
                rows.append({'capture': label, 'scenario': scenario, 'size': [width, height], 'tier': tier,
                             'renderer': renderer, **facts,
                             'sha256': {suffix: sha256((root/(label+suffix)).read_bytes()).hexdigest()
                                        for suffix in ('.ans', '.txt', '.json')}})

            def talk_rows() -> list[str]:
                area = layout.menu.talk
                return [row[area.x:area.right].rstrip() for row in screen()[area.y:area.bottom]]

            # Skip the Wake's training fight first (as enter_row does), so
            # no drone fires while the caller shops.
            await probe.walk(caller, (21, 14))
            await caller.caller.write(b'b')
            await wait(lambda: probe.game.players[caller.session.player_id].progress.get('wake_combat') == 'skipped')
            if full:
                await probe.near(caller, OUTFITTER)
                await delivered()
                await caller.caller.write(b'e')
                await wait(lambda: caller.session.id in core.commerce.menus)
                menu = core.commerce.menus[caller.session.id]
                stock = [entry.item for entry in core.commerce.stock(core.commerce.content.vendors[OUTFITTER])]
                for index in range(stock.index(SIDEARM)):
                    await caller.caller.write(b'\x1b[B')
                    await wait(lambda: menu.cursor == index+1)
                description = core.commerce.content.items[SIDEARM].description
                await wait(lambda: 'The starter pistol.' in caller.caller.screen.screen_text())
                await delivered()
                detail = layout.menu.detail
                shown = [row[detail.x:detail.right].rstrip() for row in screen()[detail.y:detail.bottom]]
                wrapped = wrap_text(description, detail.width)
                assert len(wrapped) >= 2  # the description wraps at this width
                whole = all(row in shown for row in wrapped)
                if width == 132:
                    # Presentation lead: the 86-char description wraps whole.
                    assert whole, shown
                else:
                    # 4-row detail rect: rule 3's fallback ends row 4 with `...`.
                    assert not whole and shown[detail.height-1].endswith('...'), shown
                save('vendor-detail-wraps', {'item': SIDEARM, 'description': description, 'detail_rows': shown,
                                             'description_whole': whole, 'rule_3_fallback': not whole})
                await caller.caller.write(b'\x1b')
                await wait(lambda: caller.session.id not in core.commerce.menus)

            for destination in ('vatside-clinics', 'core-plaza', 'sodium-row'):
                await probe.travel(caller, destination)
            await probe.travel(caller, 'sodium-tin-halo')
            zone = probe.service.world.zones['sodium-tin-halo']
            actor = caller.avatar.actor
            exits = {ex.tile for ex in zone.template.meta.exits}
            taken = {a.position for a in zone.actors.values()} | {o.spec.tile for o in zone.objects.values()}

            def near_exit(tile: tuple[int, int]) -> bool:
                return any(abs(tile[0]-x) <= 2 and abs(tile[1]-y) <= 2 for x, y in exits)

            # Reachable floor away from the doors, with a free tile east
            # of it for the contact object.
            pending, seen = deque([actor.position]), {actor.position}
            while pending:
                x, y = pending.popleft()
                for tile in ((x+1, y), (x, y+1), (x-1, y), (x, y-1)):
                    if tile not in seen and tile not in taken and zone.can_enter(actor, tile):
                        seen.add(tile)
                        pending.append(tile)
            stand, spot = next((tile, (tile[0]+1, tile[1])) for tile in sorted(seen)
                               if not near_exit(tile) and tile != actor.position
                               and zone.passable((tile[0]+1, tile[1]))
                               and (tile[0]+1, tile[1]) not in taken)
            await probe.walk(caller, stand)

            player = probe.game.players[caller.session.player_id]
            owner = core.contracts
            draft = owner.state.fork()
            draft.journal.setdefault(player.id, {})[EVIDENCE] = {'id': EVIDENCE, 'fixture': 'P12 capture 1'}
            owner.write(draft)
            player.progress['met_talkers'] = sorted({*player.progress.get('met_talkers', ()), 'p12-halvard'})
            await wait(lambda: not probe.commerce.pending and not probe.commerce.waiting)

            async def talk(did: str, scenario: str, line_id: str | None) -> str:
                zone.objects['p12-contact'] = ObjectState(ObjectSpec('p12-contact', spot, 'vendor',
                    {'name': dialogue[did].name, 'dialogue': did}))
                previous = caller.session.view_revision
                probe.game.sim.reset_view(caller.session, caller.avatar)
                await wait(lambda: caller.session.view_revision > previous)
                await delivered()
                await caller.caller.write(b'e')
                await wait(lambda: caller.session.id in core.dialogue.menus)
                text = core.dialogue.menus[caller.session.id].line
                if line_id:
                    assert text == next(ln.text for ln in dialogue[did].lines if ln.id == line_id), text
                assert text in {ln.text for ln in dialogue[did].lines}  # a real shipped line
                await wait(lambda: 'Esc/B  Leave' in talk_rows())
                await delivered()
                shown = talk_rows()
                body = [row for row in shown if row and not row.startswith(('c ', 'v ', 'Esc/B'))]
                assert ' '.join(body).split() == text.split(), (body, text)
                assert shown.count('Esc/B  Leave') == 1 and not any('Back' in row for row in shown)
                save(scenario, {'talker': did, 'line': text, 'line_rows': len(body), 'talk_rows': shown})
                await caller.caller.write(b'\x1b')
                await wait(lambda: caller.session.id not in core.dialogue.menus)
                del zone.objects['p12-contact']
                return text

            halvard = await talk('p12-halvard', 'talk-halvard', 'record-hal-s1-1-recovery')
            if full:
                vesper = await talk('p12-vesper', 'talk-vesper', None)
                speaker = dialogue['p12-vesper'].name
                await wait(lambda: any(ln['text'].endswith(vesper) for ln in caller.session.log_ring))
                await wait(lambda: speaker in '\n'.join(screen()[layout.log.y:layout.log.bottom]))
                await delivered()
                log_rows = [row.rstrip() for row in screen()[layout.log.y:layout.log.bottom]]
                save('log-after-talk', {'older': halvard, 'newer': vesper, 'log_rows': log_rows})
            await probe.leave(caller, f'p12-left-{width}x{height}-{tier}-{renderer}')
        assert not probe.errors and probe.service.failure is None
        (root/'p12-results.json').write_text(json.dumps({
            'passed': True, 'head': head, 'transport': 'NetBBS Telnet -> registered native stdio',
            'renderer': renderer, 'size': [width, height], 'captures': rows,
            'fixtures': ['p12-halvard: shipped halvard dialogue, id changed only; contact object in the Tin Halo',
                         'p12-vesper: shipped vesper dialogue, id changed only; contact object in the Tin Halo',
                         f'journal evidence {EVIDENCE} granted; p12-halvard marked as met',
                         'the s27-cast originals stay "authoring" on main and are not placed'],
            'presentation_acceptance': False, 'h1_layout_approval': False,
            's25_layout_approval': False}, indent=2)+'\n', encoding='utf-8', newline='\n')
        probe.report(f'P12 PASS {width}x{height}/{renderer}: talk pages, log, vendor detail')
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
