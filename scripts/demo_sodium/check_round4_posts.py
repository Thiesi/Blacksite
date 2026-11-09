"""Deterministic functional trace of the authored cast; not a CPU/native gate."""

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any

from scripts.demo_sodium.content import load_demo_content as load_content
from tests.character_helpers import create, place
from tests.harness import HeadlessServer


def check(root: Path, samples: int) -> dict[str, Any]:
    game = HeadlessServer(load_content(root / 'src/karst41/content'), character_state={})
    caller = game.connect()
    create(game, caller, card='none')
    game.core.characters.players[caller.session.player_id].progress['wake_combat'] = 'skipped'
    place(game, caller, 'sodium-row', (2, 12))
    world, posts = game.core.world, game.core.npcs.posts
    zones = [world.zones[key] for key in ('sodium-row', 'sodium-tin-halo')]
    zones[1].listeners.add('round4-functional-proof')
    result: dict[str, Any] = {'kind': 'manual-clock functional trace; not native or CPU proof',
        'ticks': samples, 'zones': {z.id: {'budget': z.template.meta.moving_budget,
        'max_reservations': 0, 'max_moved_in_one_tick': 0, 'moves': 0,
        'movers_by_spawner': Counter(), 'swaps_started': 0} for z in zones}}
    previous_homes: dict[str, tuple[int, int]] = {}
    for _ in range(samples):
        before = {a.id: a.position for z in zones for a in z.actors.values()}
        game.step()
        game.commit_commerce()
        for zone in zones:
            data = result['zones'][zone.id]
            reserved = posts.reserved_ids(zone, game.clock.now_tick())
            moved = [a for a in zone.actors.values() if posts.ordinary(a)
                     and a.id in before and a.position != before[a.id]]
            assert len(reserved) <= data['budget'], (zone.id, game.clock.now_tick(), reserved)
            assert len(moved) <= data['budget'], (zone.id, game.clock.now_tick(), moved)
            data['max_reservations'] = max(data['max_reservations'], len(reserved))
            data['max_moved_in_one_tick'] = max(data['max_moved_in_one_tick'], len(moved))
            data['moves'] += len(moved)
            for actor in moved:
                data['movers_by_spawner'][actor.behaviour['spawner']] += 1
            homes = [posts.home(a) for a in zone.actors.values() if a.behaviour.get('posts')]
            assert len(homes) == len(set(homes)), (zone.id, 'duplicate owned home')
            for actor in zone.actors.values():
                if not actor.behaviour.get('posts'):
                    continue
                home = posts.home(actor)
                if actor.id in previous_homes and previous_homes[actor.id] != home:
                    data['swaps_started'] += 1  # Two exchanged actors per swap.
                previous_homes[actor.id] = home
        game.frames_for(caller)  # Bound the fake transport queue during the trace.
    for zone in zones:
        data = result['zones'][zone.id]
        data['population'] = sum(a.kind != 'player' for a in zone.actors.values())
        data['swaps_started'] //= 2
        data['movers_by_spawner'] = dict(sorted(data['movers_by_spawner'].items()))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ticks', type=int, default=6000)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = check(Path(__file__).resolve().parents[2], args.ticks)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
