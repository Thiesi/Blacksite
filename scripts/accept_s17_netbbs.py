"""S17 real NetBBS native stdio with explicitly labelled fixture geography.

The current Wake map hosts temporary Scour/Landing/Old Works test objects.
This verifies engine/UI integration, not S25's future location placement.
Funding, a three-unit hull node and caller B's recipe/inputs are fixtures.
Harvest/craft clocks, caller A's purchase/learning, sale and all keys are real.
"""

import argparse
import asyncio
from dataclasses import replace
import json
from pathlib import Path
import traceback

from accept_s10_netbbs import NativeProbe, wait
from accept_s16_netbbs import key, commit_key, select, use, loan
from blacksite.content.schema import ObjectSpec
from blacksite.server.inventory import Inventory
from blacksite.server.world.zone import ObjectState


def fixtures(probe: NativeProbe, connection) -> None:
    zone = probe.service.world.zones[connection.avatar.zone]
    assert zone.id == "vatside-wake-hall"
    for oid, tile, kind, params in (
        ("fixture-workshop", (10, 8), "workshop", {"makes": "any", "name": "FIXTURE Landing workshop"}),
        ("fixture-counter", (14, 8), "vendor", {"vendor": "fixture-landing-counter"}),
        ("fixture-oldworks", (17, 8), "workshop", {"makes": "rigs_programs", "name": "FIXTURE Old Works workshop"}),
    ):
        assert zone.passable(tile)
        zone.objects[oid] = ObjectState(ObjectSpec(oid, tile, kind, params=params))
    vendor = next(row for row in probe.game.content.vendors.values() if row.salvage_multiplier == 1.2)
    probe.game.content.vendors["fixture-landing-counter"] = replace(vendor,
        id="fixture-landing-counter", name="FIXTURE Landing counter", zone=zone.id, object_id="fixture-counter")
    salvage = probe.service.core.salvage
    salvage.state["zones"][zone.id] = {"ring": 1, "nodes": {
        "fixture-scour-node": {"tile": [6, 8], "grade": "hull", "units": 3}},
        "respawn_at": salvage.uptime+600}
    salvage.sync()
    zone.revision += 1
    probe.report("FIXTURE: Wake geography hosts Scour hull node, Landing counter/workshop and Old Works filter; S25 owns real placement")


async def run_size(probe: NativeProbe, width: int, height: int) -> dict:
    connection = await probe.open(width, height, "S17A", 1, sixteen=True)
    fixtures(probe, connection)
    player = probe.game.players[connection.session.player_id]
    player.chits_hand = 500
    fab = probe.service.core.fabrication
    probe.game.queue("save", player.bbs_user_id, player, immediate=True)
    probe.service._character_writes()
    await probe.walk(connection, (6, 8))
    await key(connection, b'e')
    await wait(lambda: connection.session.player_id in fab.channels)
    await wait(lambda: 'Harvest' in connection.caller.screen.screen_text())
    probe.save(connection, f's17-harvest-channel-{width}')
    await wait(lambda: fab.amounts(player).get('hull', 0) == 3, 12)
    assert Inventory(probe.commerce.items, probe.game.content.items).weight(player) >= 12
    probe.save(connection, f's17-harvest-complete-{width}')

    await probe.walk(connection, (14, 8))
    await key(connection, b'e')
    await wait(lambda: connection.session.id in probe.commerce.menus)
    screen = probe.commerce.menus[connection.session.id]
    await select(connection, lambda: probe.commerce.body(connection.session, screen)['rows'], screen, 'sch_ring_wrench')
    def schematic_item():
        return next((iid for iid in player.inventory if probe.commerce.items[iid].template == 'sch_ring_wrench'), None)
    await commit_key(probe, connection, b'\r', lambda: schematic_item() is not None)
    iid = schematic_item()
    assert 'sch_ring_wrench' not in player.progress.get('known_schematics', ())
    await key(connection, b'\x1b')
    await wait(lambda: connection.session.id not in probe.commerce.menus)
    await use(probe, connection, iid)
    assert 'sch_ring_wrench' in player.progress['known_schematics']

    await probe.walk(connection, (10, 8))
    await key(connection, b'e')
    await wait(lambda: connection.session.id in fab.menus)
    await wait(lambda: 'hull 3/2' in connection.caller.screen.screen_text())
    probe.save(connection, f's17-workshop-menu-{width}')
    old = set(probe.commerce.items)
    await commit_key(probe, connection, b'f', lambda: player.id in fab.channels)
    await wait(lambda: 'Fabricate' in connection.caller.screen.screen_text())
    await wait(lambda: any(iid not in old and item.owner == player.id and item.template == 'wpn_ferry_wrench'
        for iid, item in probe.commerce.items.items()), 10)
    made = next(item for iid, item in probe.commerce.items.items() if iid not in old and item.owner == player.id and item.template == 'wpn_ferry_wrench')
    assert .85 <= made.quality <= 1.15 and fab.amounts(player).get('hull') == 1
    await key(connection, b'i')
    await wait(lambda: connection.session.id in probe.commerce.menus)
    screen = probe.commerce.menus[connection.session.id]
    await select(connection, lambda: probe.commerce.body(connection.session, screen)['rows'], screen, made.id)
    await wait(lambda: f'Damage {26*made.quality:g}' in connection.caller.screen.screen_text())
    body = probe.commerce.body(connection.session, screen)
    assert f'Damage {26*made.quality:g}' in body['detail']
    probe.save(connection, f's17-crafted-detail-{width}')
    await key(connection, b'\x1b')
    await wait(lambda: connection.session.id not in probe.commerce.menus)
    await probe.walk(connection, (14, 8))
    await key(connection, b'e')
    await wait(lambda: connection.session.id in probe.commerce.menus)
    screen = probe.commerce.menus[connection.session.id]
    await key(connection, b't')
    await wait(lambda: screen.sell)
    hull = next(iid for iid in player.inventory if probe.commerce.items[iid].template == 'slv_hull')
    await select(connection, lambda: probe.commerce.body(connection.session, screen)['rows'], screen, hull)
    before = player.chits_hand
    await commit_key(probe, connection, b'\r', lambda: player.chits_hand == before+18)
    await key(connection, b'\x1b')
    await wait(lambda: connection.session.id not in probe.commerce.menus)
    probe.save(connection, f's17-sale-18-{width}')

    second = await probe.open(width, height, "S17B", 1, sixteen=True)
    second_player = probe.game.players[second.session.player_id]
    await use(probe, second, loan(probe, second, 'sch_ring_wrench'))
    loan(probe, second, 'slv_hull')
    loan(probe, second, 'slv_hull')
    await probe.walk(second, (17, 8))
    await key(second, b'e')
    await wait(lambda: second.session.id in fab.menus)
    await key(second, b'f')
    await wait(lambda: 'rigs and programs only' in second.caller.screen.screen_text())
    assert second_player.id not in fab.channels and fab.amounts(second_player)['hull'] == 2
    probe.save(second, f's17-oldworks-refusal-{width}')
    await key(second, b'\x1b')
    await wait(lambda: second.session.id not in fab.menus)
    assert connection.caller.screen.cell(width-1, height-1) == ' '
    assert second.caller.screen.cell(width-1, height-1) == ' '
    probe.report(f'PASS S17 {width}x{height}: 3 hull, actual schematic purchase/learn, 3s craft quality {made.quality:.6f}, 18-chit sale, Old Works refusal; wide names/native16')
    await probe.leave(second, f's17-B-return-{width}')
    await probe.leave(connection, f's17-A-return-{width}')
    return {'size': [width, height], 'quality': made.quality, 'hull_harvested': 3, 'hull_sale': 18,
            'oldworks_refused': True, 'tier': connection.session.caps['tier']}


async def accept(root: Path, python: Path, show: bool) -> None:
    probe = NativeProbe(root, python, show)
    await probe.start()
    try:
        results = [await run_size(probe, *size) for size in ((80, 24), (132, 50))]
        assert not probe.errors and probe.service.failure is None
        (root/'s17-results.json').write_text(json.dumps({'passed': True,
            'transport': 'NetBBS Telnet -> native stdio', 'placement_fixture': True, 'clock_fixture': False,
            'fixtures': ['Wake hosts labelled Scour/Landing/Old Works objects', '500 chits caller A',
                         'three hull node', 'caller B schematic and two hull'], 'runs': results}, indent=2)+'\n', encoding='utf-8')
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
    args = parser.parse_args()
    asyncio.run(accept(args.root, args.door_python, args.show))
