"""Idempotent round 4 cast/posts, from #185's creative build list.

Run from this demo checkout after the round 4 schema and dialogue merge.
This never changes geometry, canon, or the round 3 population generator.
"""

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CONTENT = ROOT / 'src' / 'karst41' / 'content'


def read(path: str) -> Any:
    return json.loads((CONTENT / path).read_text(encoding='utf-8'))


def write(path: str, data: Any) -> None:
    (CONTENT / path).write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def post(x: int, y: int, *, home: bool = False, seated: bool = False,
         weight: int = 1, hold: tuple[int, int] | None = None, swap: bool = False) -> dict[str, Any]:
    return {'tile': [x, y], 'home': home, 'seated': seated, 'weight': weight,
            'hold_seconds': list(hold or ((60, 180) if seated else (120, 300))), 'swap': swap}


def errand(x: int, y: int, weight: int, *, counter: bool = False) -> dict[str, Any]:
    return post(x, y, weight=weight, hold=(5, 10) if counter else (10, 20))


def configure(spawner: dict[str, Any], posts: list[dict[str, Any]], crowd: str | None = None) -> None:
    spawner.pop('region', None)
    spawner.pop('tile', None)
    spawner.update(posts=posts, moving_cap=1)
    if crowd:
        spawner['crowd'] = crowd


def bark(text: str, weight: int = 1) -> dict[str, Any]:
    return {'text': text, 'weight': weight, 'min_interval_seconds': 90}


def line(lid: str, text: str, *when: str) -> dict[str, Any]:
    return {'id': lid, 'text': text, 'when': list(when), 'required': True}


def add_barks(did: str, texts: list[str]) -> None:
    data = read(f'dialogue/{did}.json')
    data['barks'] += [bark(text) for text in texts if text not in {b['text'] for b in data['barks']}]
    write(f'dialogue/{did}.json', data)


def main() -> None:
    row = read('zones/sodium-row.json')
    row['moving_budget'] = 4
    row['objects'] = [obj for obj in row['objects'] if obj['id'] != 'row-ticket-tout']
    spawners = {sp['id']: sp for sp in row['spawners']}
    configure(spawners['upstairs-halvard'], [post(12, 6, home=True, seated=True),
              errand(14, 6, 50, counter=True), errand(13, 9, 30), errand(15, 6, 20)], 'upstairs')
    configure(spawners['upstairs-sablier'], [post(9, 6, home=True, seated=True),
              errand(14, 6, 50, counter=True), errand(13, 9, 30), errand(15, 6, 20)], 'upstairs')
    bars = {
        'long-shift-crew': [(27, 4), (34, 9), (24, 4), (36, 9), (30, 3)],
        'quarter-tone-listeners': [(40, 6), (39, 9), (50, 3), None, (48, 4)],
        'clause-regulars': [(55, 5), (56, 9), (57, 5), (58, 9), None],
        'spare-parts-runners': [(73, 5), (71, 9), (77, 4), (84, 3), None],
    }
    for sid, (seat, doorway, counter, outside, table) in bars.items():
        posts = [post(*seat, home=True, seated=True, swap=True),
                 post(*doorway, home=True, swap=True), errand(*counter, 50, counter=True)]
        if outside:
            posts.append(errand(*outside, 30))
        if table:
            posts.append(errand(*table, 20))
        configure(spawners[sid], posts)
    configure(spawners['card-court-players'], [post(49, 18, home=True, seated=True),
              post(55, 18, home=True, seated=True)])
    configure(spawners['card-court-solenne'], [post(59, 20, home=True)])
    configure(spawners['halo-doorstep-1'], [post(85, 11, home=True)])
    configure(spawners['halo-doorstep-2'], [post(87, 13, home=True)])
    middle = [post(x, y, home=True) for x, y in ((46, 17), (58, 17), (46, 21), (58, 21))]
    middle += [post(x, y) for x, y in ((44, 9), (48, 9), (52, 9), (30, 16), (64, 15))]
    configure(spawners['sodium-regular'], middle)
    configure(spawners['plainclothes-warden'], deepcopy(middle))
    spawners['plainclothes-warden']['poses_as'] = 'sodium-regular'
    for sid, name, tile in (('ticket-tout', 'Ticket tout', (4, 11)), ('haggler', 'Haggler', (5, 11))):
        sp = {'id': sid, 'npc': f'npc-row-{sid}', 'count': 1, 'respawn_seconds': 60, 'condition': 'always'}
        configure(sp, [post(*tile, home=True)])
        spawners[sid] = sp
    row['spawners'] = list(spawners.values())
    write('zones/sodium-row.json', row)

    # The Halo has its own copies; no street-direction bark leaks indoors.
    halo = read('zones/sodium-tin-halo.json')
    halo['moving_budget'] = 1
    halo_copies = {
        'halo-regular-crew': ('kestrel-crew', (18, 8), 'Double shift, then a bar. Then the next double.'),
        'halo-regular-stray': ('clause-regular', (28, 8), 'Day forty and I still check the lease. Nothing on it. I check.'),
        'halo-regular-runner': ('unmoored-runner', (29, 13), "Everything's salvage eventually. Some of us just got there early."),
    }
    npcs = read('npcs.json')
    templates = {npc['id']: npc for npc in npcs['npcs']}
    for sp in halo['spawners']:
        if sp['id'] not in halo_copies:
            continue
        short, seat, fallback = halo_copies[sp['id']]
        did = 'halo-' + short
        tid = 'npc-' + did
        talker = deepcopy(read(f'dialogue/row-{short}.json'))
        talker['id'], talker['title'] = did, 'Tin Halo regular'
        # Existing voices only, plus the explicitly approved back-way bark.
        talker['lines'] = [entry for entry in talker['lines'] if entry['id'] in ('drawn', 'provoked')]
        talker['lines'].append(line('greeting', fallback))
        talker['barks'] = [bark(fallback)]
        if short == 'unmoored-runner':
            talker['barks'].append(bark("Back room's on Vesper's system. Jack in from the board if you want out the quiet way."))
        write(f'dialogue/{did}.json', talker)
        templates[tid] = {**deepcopy(templates['npc-row-' + short]), 'id': tid, 'dialogue': did}
        sp['npc'] = tid
        configure(sp, [post(*seat, home=True, seated=True), errand(23, 9, 50, counter=True),
                       errand(32, 10, 30), errand(18, 10, 20)], 'halo-regulars')
    write('zones/sodium-tin-halo.json', halo)

    dialogue = {
        'ticket-tout': ("Ticket tout", [
            line('wake', 'Fresh out of the vats and already thinking about leaving? Smart. Convoy seat, under the Kestrel price.', 'is_wake'),
            line('greeting', 'Convoy seats, Scour rides, no questions on the manifest. Ask me tomorrow and the price is worse.')], [
            "Rim run, end of the week. Two seats. One if you're big.",
            'Kestrel sells the tickets. I sell the ones Kestrel forgot it sold.',
            "Ring-fall's coming. Rides go up when the sky comes down."]),
        'haggler': ('Haggler', [line('greeting', 'He wants forty chits for a seat on a truck. Forty. For a truck.')], [
            'Twenty-five and I bring my own water.', 'Last time the seat was a crate. A wet crate.']),
    }
    for sid, (name, lines, barks) in dialogue.items():
        did = 'row-' + sid
        path = CONTENT / 'dialogue' / (did + '.json')
        existing = read(f'dialogue/{did}.json') if path.exists() else {}
        overrides = [entry for entry in existing.get('lines', []) if entry['id'] in ('drawn', 'provoked')]
        write(f'dialogue/{did}.json', {'schema': 1, 'id': did, 'name': name, 'faction': None,
              'title': 'Sodium Row', 'terminal': False, 'machine_mind': False,
              'lines': overrides + lines, 'offers': [], 'barks': [bark(text) for text in barks]})
        templates['npc-' + did] = {**deepcopy(templates['npc-row-halo-doorstep']),
            'id': 'npc-' + did, 'name': name, 'dialogue': did, 'steady': False}
    steady = {'npc-row-card-player', 'npc-row-solenne', 'npc-row-choir-listener',
              'npc-halo-bouncer', 'npc-vendor-sodium-tin-halo-vesper', 'npc-halo-dolf'}
    for npc in templates.values():
        if npc['id'] in steady:
            npc['steady'] = True
    npcs['npcs'] = list(templates.values())
    write('npcs.json', npcs)

    add_barks('row-street-regular', [
        'Six doors, six songs. You learn to hear the one you want.',
        'Loudest street in Karst, and nobody raises their voice.',
        'Puddles never dry on the Row. Nobody remembers it raining.'])
    add_barks('row-enforcer', ["Everybody's welcome. Nobody's exempt.", "We're not here to stop you. We're here after."])
    enforcer = read('dialogue/row-enforcer.json')
    enforcer['barks'][0]['weight'] = 2
    write('dialogue/row-enforcer.json', enforcer)
    add_barks('row-halo-doorstep', ["She knows I'm out here. She always knows.", "I came to ask her one thing. I'm working up to it."])
    dolf = read('dialogue/dolf.json')
    hint = "Back door's on the house system. I don't know anything about it. Ask the board."
    dolf['lines'] = [entry for entry in dolf['lines'] if entry['id'] not in ('back-way-marked', 'back-way-hunted')]
    # Drawn/provoked overrides retain precedence on t4's integration branch.
    at = next((i for i, entry in enumerate(dolf['lines']) if entry['id'] not in ('drawn', 'provoked')), len(dolf['lines']))
    dolf['lines'][at:at] = [line('back-way-marked', hint, 'marked'), line('back-way-hunted', hint, 'hunted')]
    write('dialogue/dolf.json', dolf)
    core = read('cores/lat-tin-halo.json')
    next(room for room in core['rooms'] if room['id'] == 'room-3')['label'] = 'Back room'
    write('cores/lat-tin-halo.json', core)


if __name__ == '__main__':
    main()
