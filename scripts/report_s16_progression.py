"""Deterministic earning schedules, not a measurement of human pacing.

Only implemented S16 sources are scheduled. Contracts, crafting, relays
and contributions need their owning slices before a complete playtest.
"""

from collections import Counter
from datetime import datetime, timedelta, timezone
import json
from typing import Any

from blacksite.server.players import Player
from blacksite.server.progression import Grant, award


def report(profile: str, minutes: int = 360) -> dict[str, Any]:
    start = datetime(2026,1,1,12,tzinfo=timezone.utc)
    player = Player('report','node','report-identity','Report','Report','operator',start.isoformat())
    identity: dict[str, Any] = {'first_decanted_at':start.isoformat(),'legal_at':None}
    totals: Counter[str] = Counter()
    accepted: Counter[str] = Counter()
    rejected: Counter[str] = Counter()
    milestones: dict[str, Any] = {}
    for minute in range(minutes):
        grants: list[Grant] = []
        # Twenty defeats/hour for street; eight/hour for mixed/runner.
        interval = 3 if profile == 'street' else 8
        if minute % interval == 0:
            grants.append(Grant('combat',f'spawn:{minute}',True,scope='street-spawner',opponent_grade=3))
        if profile != 'street':
            # The authored ten-zone hub and forty distinct cells, not loops.
            if minute < 10:
                grants.append(Grant('zone_discovery',f'zone:{minute}',True,scope=f'zone:{minute}',authored=True))
            if minute < 80 and minute % 2 == 0:
                grants.append(Grant('cell_discovery',f'cell:{minute}',True,scope=f'cell:{minute}',authored=True))
            if minute % 10 == 0:
                core = f'hub-core:{minute//10%6}'
                grants.append(Grant('run',f'lift:{minute}',True,scope=core,core=core,tier=1 if profile == 'runner' else 2))
        for grant in grants:
            result = award(player,identity,grant,start+timedelta(minutes=minute))
            if result:
                totals[grant.kind] += result.xp
                accepted[grant.kind] += 1
                if result.old_grade < 5 <= result.grade:
                    milestones['grade5_minute'] = minute
            else:
                rejected[grant.kind] += 1
        if minute+1 in (240,360):
            milestones[f'at_{minute+1}_minutes'] = {'xp':player.xp,'grade':player.grade}
    return {'profile':profile,'minutes':minutes,'xp':player.xp,'grade':player.grade,
        'xp_by_source':dict(totals),'accepted':dict(accepted),'rejected':dict(rejected),
        'milestones':milestones}


if __name__ == '__main__':
    print(json.dumps({'kind':'assumed deterministic activity; not human pacing',
        'not_yet_measured':['contracts','crafting','relays','contributions','travel and combat difficulty'],
        'runs':[report(name) for name in ('street','runner','mixed')]},indent=2))
