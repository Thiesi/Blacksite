"""B1: the shipped P6b walk through registered NetBBS native stdio.

Normal character creation, arrows, E and J only. No pose, progression,
inventory, actor, memory or handle override. Run --show on a real PTY.
"""

import argparse
import asyncio
from hashlib import sha256
from importlib.metadata import version
import json
import os
from pathlib import Path
import subprocess
from typing import Any

from accept_p5_netbbs import PresentationProbe
from accept_s10_netbbs import wait


async def accept(root: Path, door_python: Path, size: tuple[int, int], tier: str, show: bool) -> None:
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    assert not subprocess.check_output(['git', 'status', '--porcelain'], text=True).strip()
    console: dict[str, Any] = {'isatty': os.isatty(1), 'size': None}
    if show:
        assert console['isatty'], '--show requires an attached terminal'
        terminal = os.get_terminal_size(1)
        console['size'] = [terminal.columns, terminal.lines]
        assert tuple(console['size']) == size, 'Resize the attached terminal to --size'
    assert version('netbbs') == '7.45.0'
    root.mkdir(parents=True, exist_ok=False)
    probe = PresentationProbe(root, door_python, show,
        door_environment={'DOOR_BLACKSITE_PRESENTATION': '1'}, show_all_tiers=True)
    await probe.start()
    captures: list[str] = []
    checkpoints: list[dict[str, Any]] = []
    keys: list[str] = []
    try:
        caller = await probe.open(*size, 'B'+{'16':'S', '256':'T', 'truecolor':'U'}[tier],
                                  sixteen=tier == '16', truecolor=tier == 'truecolor')
        assert caller.session.caps['tier'] == tier
        player = probe.game.players[caller.session.player_id]
        assert '界' in player.name
        handle = caller.session.door_info['handle']
        original_write = caller.caller.write

        async def write(data: bytes) -> None:
            keys.append(data.hex())
            await original_write(data)

        caller.caller.write = write

        async def settled() -> None:
            await wait(lambda: caller.session.ack_revision == caller.session.view_revision)

        async def save(step: str) -> None:
            await settled()
            label = f'{step}-{size[0]}x{size[1]}-{tier}'
            probe.save(caller, label)
            captures.append(label)
            av = caller.avatar
            checkpoints.append({'capture': label, 'zone': av.zone, 'position': av.actor.position,
                                'viewport': dict(av.perception.viewport), 'key_count': len(keys),
                                'handle': caller.session.door_info['handle']})
            probe.report(f'CAPTURE {label}: {av.zone} {av.actor.position}')

        # The Wake's offered B skip is an ordinary action, without fighting
        # or changing the character's grade, equipment or training actor.
        await probe.walk(caller, (21, 14))
        await caller.caller.write(b'b')
        await wait(lambda: player.progress.get('wake_combat') == 'skipped')
        await probe.travel(caller, 'vatside-clinics')
        await probe.walk(caller, (12, 13))
        zone = probe.service.world.zones['vatside-clinics']
        if not zone.passable((12, 12)):
            await caller.caller.write(b'e')
            await wait(lambda: zone.passable((12, 12)))
        await probe.walk(caller, (17, 7))
        await settled()
        body_position = caller.avatar.actor.position
        await caller.caller.write(b'j')
        await wait(lambda: caller.avatar.actor.stance == 'jacked')
        await wait(lambda: 'INTEGRITY' in caller.caller.screen.screen_text())
        await caller.caller.write(b'j')
        await wait(lambda: caller.avatar.actor.stance == 'normal')
        await wait(lambda: 'Clinic Row' in caller.caller.screen.screen_text().splitlines()[0])
        assert caller.avatar.actor.position == body_position
        await probe.walk(caller, (12, 14))
        await settled()
        perception = caller.avatar.perception
        assert (17, 8) in perception.remembered['vatside-clinics']
        vp = perception.viewport
        cx, cy = 17-vp['x'], 8-vp['y']
        assert 0 <= cy < len(perception.tiles) and 0 <= cx < len(perception.tiles[cy])
        assert perception.tiles[cy][cx] == -2, 'clinic terminal must be remembered, outside current sight'
        await save('clinic-known-interior')
        await probe.walk(caller, (50, 14))
        await save('pharmacy-frontage')
        await probe.travel(caller, 'core-plaza')
        await probe.walk(caller, (57, 6))
        await save('plaza-second-terminal')
        plaza = probe.service.world.zones['core-plaza']
        assert next(ex for ex in plaza.template.meta.exits if ex.target_zone == 'sodium-row').id == 'to-sodium-row'
        await probe.travel(caller, 'sodium-row')
        await save('sodium-row-entry')
        await probe.walk(caller, (93, 26))
        assert caller.avatar.zone == 'sodium-row' and caller.avatar.actor.position != (94, 26)
        await save('tin-halo-frontage')
        assert caller.session.door_info['handle'] == handle
        case = {'size': list(size), 'tier': tier, 'captures': captures, 'checkpoints': checkpoints,
                'character_name': player.name, 'handle': handle, 'wide_character_name': True,
                'wide_bbs_handle': False, 'ordinary_inputs': True, 'training': 'normal B skip',
                'clinic_terminal': [17, 8], 'jack_in_out': True, 'remembered_clinic_terminal': True,
                'tin_halo_entered': False, 'key_hex_after_character_creation': keys}
        await probe.leave(caller, f'return-{size[0]}x{size[1]}-{tier}')
        assert not probe.errors, probe.errors
        probe.report(f'PASS P6b {size[0]}x{size[1]} {tier}: clinic jack/out, known interior, pharmacy, Plaza, Sodium, Tin Halo frontage')
    finally:
        await probe.close()
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip() == head
    assert not subprocess.check_output(['git', 'status', '--porcelain'], text=True).strip()
    manifest = {p.name: {'bytes': p.stat().st_size, 'sha256': sha256(p.read_bytes()).hexdigest()}
                for label in captures for ext in ('.ans', '.txt', '.json') for p in [root/(label+ext)]}
    (root/'result.json').write_text(json.dumps({'head': head, 'passed': True, 'cases': [case],
        'transport': 'NetBBS 7.45.0 Telnet -> registered native stdio; DOOR_BLACKSITE_PRESENTATION=1',
        'source_matched_wheel': json.loads((root/'native-client.json').read_text()),
        'show': show, 'console': console, 'teleports': False, 'local_handle_override': False,
        'fixtures': 'private node/world/accounts only; ordinary creation and player keys',
        'human_approval': False, 'fingerprint_approval': False, 's25_layout_approval': False,
        'manifest': manifest}, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps({'passed': True, 'captures': len(captures)}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--door-python', type=Path, required=True)
    parser.add_argument('--size', choices=('80x24', '132x50'), required=True)
    parser.add_argument('--tier', choices=('16', '256', 'truecolor'), required=True)
    parser.add_argument('--show', action='store_true')
    args = parser.parse_args()
    asyncio.run(accept(args.root.resolve(), args.door_python, tuple(map(int, args.size.split('x'))), args.tier, args.show))
