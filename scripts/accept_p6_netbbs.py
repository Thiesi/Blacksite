"""P6a fixture captures through real NetBBS Telnet/native stdio.

This is engine evidence, not a shipped-place walk or a human gate.
Fixtures: test-only content.local palette/themes/zone; explicit initial
placement in that zone. After placement, walking uses ordinary keys.
The production maps, rules and content files are never changed.
"""

import argparse
import asyncio
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess

from accept_p5_netbbs import PresentationProbe
from accept_s10_netbbs import wait

ROOT = Path(__file__).resolve().parents[1]


async def accept(root: Path, python: Path, size: tuple[int, int], theme: str, show: bool) -> None:
    head = subprocess.check_output(['git','rev-parse','HEAD'], text=True).strip()
    assert not subprocess.check_output(['git','status','--porcelain'], text=True).strip()
    if show:
        assert os.isatty(1) and tuple(os.get_terminal_size(1)) == size
    root.mkdir(parents=True, exist_ok=False)
    probe = PresentationProbe(root, python, show,
        door_environment={'DOOR_BLACKSITE_PRESENTATION':'1'}, show_all_tiers=True)
    local = probe.service.install_dir/'content.local'
    shutil.copytree(ROOT/'tests/fixtures/p6', local)
    look_path = local/'looks/p6-fixture.json'
    look = json.loads(look_path.read_text(encoding='utf-8'))
    look['theme'] = 'p6-'+theme
    look_path.write_text(json.dumps(look)+'\n', encoding='utf-8')
    await probe.start()
    cases = []
    try:
        for tier, label in (('16','X'),('256','Y'),('truecolor','Z')):
            connection = await probe.open(*size, label, sixteen=tier=='16', truecolor=tier=='truecolor')
            avatar = connection.avatar
            old = probe.service.world.zones[avatar.zone]
            old.deactivate(connection.session.id, probe.service.clock.now_tick())
            probe.service.world.enter(avatar.actor, 'p6-fixture', (4,5))
            avatar.zone = connection.session.subscribed = 'p6-fixture'
            probe.service.world.zones[avatar.zone].activate(connection.session.id, probe.service.clock.now_tick())
            avatar.perception.viewport = None
            avatar.perception.grid_key = None
            connection.session.needs_full_view = True
            screen = connection.caller.screen
            await wait(lambda: 'Fixture hall' in screen.screen_text().splitlines()[0])
            await wait(lambda: connection.session.ack_revision == connection.session.view_revision)
            assert connection.session.caps['tier'] == tier
            assert '(Plaza)' in screen.screen_text()
            captures = []
            def save(step: str) -> None:
                name = f'{theme}-{step}-{size[0]}x{size[1]}-{tier}'
                probe.save(connection, name)
                captures.append(name)
            save('charted-and-here')
            await probe.walk(connection, (5,5))
            await wait(lambda: '▒ barrels' in screen.screen_text())
            await wait(lambda: connection.session.ack_revision == connection.session.view_revision)
            save('authored-cover')
            await probe.walk(connection, (9,5))
            await wait(lambda: '(Clinic)' in screen.screen_text())
            await wait(lambda: connection.session.ack_revision == connection.session.view_revision)
            save('light-region-and-here')
            # Existing server notice path, without a client text/handle override.
            now = probe.service.clock.now_utc().isoformat()
            connection.session.emit('Fixture warning.', kind='danger', channel='zone', role='log_danger', at=now)
            await wait(lambda: 'Fixture warning' in screen.screen_text())
            connection.session.emit('Fixture notice: you hear the fan.', kind='notice', channel='system', role='log_system', at=now)
            await wait(lambda: 'Fixture notice' in screen.screen_text())
            assert 'Fixture hall' in screen.screen_text().splitlines()[0] and 'Fixture notice' in screen.screen_text().splitlines()[0]
            save('notice')
            cases.append({'size':list(size),'tier':tier,'theme':theme,'captures':captures,
                          'initial_fixture_position':[4,5], 'walk_end':[9,5],
                          'name':probe.game.players[connection.session.player_id].name,
                          'handle':connection.session.door_info['handle']})
            await probe.leave(connection, f'{theme}-return-{tier}')
        assert not probe.errors, probe.errors
    finally:
        await probe.close()
    files = sorted(path for path in root.iterdir() if path.suffix in ('.ans','.txt','.json'))
    manifest = {path.name:sha256(path.read_bytes()).hexdigest() for path in files}
    result = {'head':head,'passed':True,'cases':cases,'manifest':manifest,'show':show,
              'transport':'NetBBS Telnet -> registered native stdio; source-matched isolated wheel',
              'fixtures':'tests/fixtures/p6 via content.local; explicit initial placement; ordinary walking keys',
              'human_approval':False,'shipped_place_acceptance':False,
              'source_matched_wheel':json.loads((root/'native-client.json').read_text())}
    (root/'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'passed':True,'cases':len(cases)}),flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--door-python',type=Path,required=True)
    parser.add_argument('--size',choices=['80x24','132x50'],required=True)
    parser.add_argument('--theme',choices=['dark','light'],required=True)
    parser.add_argument('--show',action='store_true')
    args = parser.parse_args()
    asyncio.run(accept(args.root.resolve(), args.door_python, tuple(map(int,args.size.split('x'))),args.theme,args.show))
