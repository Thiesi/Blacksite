"""P8: the ambient emitter's per-tick cost on Sodium Row (headless).

One and three callers stand on the shipped Row (spawners on) for ten
simulated minutes. The emitter's own time is measured around
`Ambience.tick`; the loop's around `HeadlessServer.step`. Prints a summary
and writes JSON. Timing is observation only; the simulation reads ticks.
"""

import argparse
import json
from pathlib import Path
import statistics
import time

from karst41.content.loader import load_content
from karst41.server.clock import TICK_HZ
from tests.character_helpers import create, place
from tests.harness import HeadlessServer

ROOT = Path(__file__).resolve().parents[1]
SPOTS = ((25, 6), (30, 6), (40, 8))


def measure(callers: int, seconds: int) -> dict:
    game = HeadlessServer(load_content(ROOT/'src/karst41/content'), character_state={})
    clients = []
    for uid, tile in enumerate(SPOTS[:callers], 1):
        client = game.connect({'user_id': uid, 'handle': f'Cost{uid}', 'node_name': 'P8'})
        create(game, client, card='none')
        place(game, client, 'sodium-row', tile)
        clients.append(client)
    emitter = game.core.dialogue.ambience
    original, every, active = emitter.tick, [], []

    def timed(tick, *args):
        start = time.perf_counter()
        original(tick, *args)
        spent = time.perf_counter() - start
        every.append(spent)
        if tick % TICK_HZ == 0:
            active.append(spent)
    emitter.tick = timed
    loop, lines = [], [0] * callers
    for _ in range(seconds):
        for _ in range(TICK_HZ):
            start = time.perf_counter()
            game.step(1)
            loop.append(time.perf_counter() - start)
        for i, client in enumerate(clients):
            lines[i] += sum(1 for f in game.frames_for(client) if f.type == 'log'
                            for line in f.data['lines'] if line['kind'] in ('ambient', 'speech'))
    active.sort()
    us = 1e6
    return {'callers': callers, 'seconds': seconds,
            'emitter_mean_us_per_tick': round(statistics.mean(every) * us, 1),
            'emitter_1hz_tick_mean_us': round(statistics.mean(active) * us, 1),
            'emitter_1hz_tick_p99_us': round(active[int(len(active) * .99)] * us, 1),
            'emitter_1hz_tick_max_us': round(active[-1] * us, 1),
            'loop_tick_mean_ms': round(statistics.mean(loop) * 1e3, 3),
            'emitter_share_of_loop_percent': round(sum(every) / sum(loop) * 100, 3),
            'lines_per_caller': lines}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--seconds', type=int, default=600)
    args = parser.parse_args()
    results = [measure(n, args.seconds) for n in (1, 3)]
    for row in results:
        print(json.dumps(row))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(results, indent=2) + '\n', encoding='utf-8')
