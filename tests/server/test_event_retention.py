"""Architecture 15.2/game 12: months of events keep bounded hot state."""

from copy import deepcopy
import json
from typing import Any

import pytest

from blacksite.content.schema import EventTemplate
from blacksite.server.events import Scheduler
from blacksite.server.event_forecasts import remember
from blacksite.server.rules.events import HISTORY_PLANS, HELD_FORECASTS, SCHEDULES
from blacksite.server.clock import TICK_HZ
from tests.character_helpers import place
from tests.harness import HeadlessServer
from tests.server.test_event_engine import base_content, events_game, force


def test_arch_15_2_long_history_preserves_live_plan_serial_and_cooldown_in_bounded_receipt() -> None:
    assert HISTORY_PLANS == 128  # Architecture 15.2.
    templates = {eid: EventTemplate(eid,eid,(where,),*SCHEDULES[eid])
        for eid,where in (('curfew','street'),('choir-surge','sector'))}
    scheduler = Scheduler('history',templates,{})
    live = scheduler.reserve(templates['choir-surge'],100,1,lambda *args: True,forced=True)
    scheduler.cooldowns['ring-fall'] = 10000
    for index in range(1000):
        now = 100+index/100
        plan = scheduler.reserve(templates['curfew'],now,index,lambda *args: True,forced=True)
        plan.allocations = {'sites': {'1': {'tile':[4,8],'zone':'street'}},'offers':[]}
        scheduler.cancel(plan.id,now,'Fixture history')
        scheduler.advance(now,lambda *args: True)
    state = scheduler.record()
    assert len(state['plans']) <= HISTORY_PLANS+1
    assert live.id in scheduler.plans and scheduler.plans[live.id].live
    assert scheduler.serial == 1001 and scheduler.cooldowns['ring-fall'] == 10000
    assert len(json.dumps(state)) < 100000
    restored = Scheduler('history',templates,{},json.loads(json.dumps(state)))
    assert restored.serial == 1001 and restored.plans[live.id].live
    next_plan = restored.reserve(templates['curfew'],111,12,lambda *args: True,forced=True)
    assert next_plan.id.endswith(':1002')


def test_game_12_personal_forecast_reads_are_bounded_and_keep_the_new_read() -> None:
    assert HELD_FORECASTS == 128  # Game 12.
    progress: dict[str, Any] = {'other_journal': {'receipt': True}}
    for index in range(1000):
        remember(progress,str(index),{'revision':1,'text':f'Event {index}'},index)
    assert len(progress['event_forecasts']) == HELD_FORECASTS
    assert set(progress['event_forecasts']) == {str(i) for i in range(1000-HELD_FORECASTS,1000)}
    remember(progress,'old-but-read-again',{'revision':2,'text':'Cancelled'},1001)
    assert 'old-but-read-again' in progress['event_forecasts']
    assert progress['other_journal'] == {'receipt': True}


@pytest.fixture
def archived_game(events_game: tuple[Any, ...]) -> tuple[Any, ...]:
    game,caller,player = events_game
    owner = game.core.events
    zone = owner.world.zones['vatside-wake-hall']
    terminal = next(obj.spec for obj in zone.objects.values() if obj.spec.kind == 'terminal')
    place(game,caller,zone.id,game.core.world.free_tile(zone.id,terminal.tile))
    force(game,'curfew')
    plan = next(iter(owner.scheduler.reserved()))
    owner.views.open(caller.session)
    owner.views.read(caller.session,owner.views.menus[caller.session.id],plan)
    game.commit_commerce()
    revision = player.progress['event_forecasts'][plan.id]['revision']
    owner.admin('event.cancel',{'plan':plan.id},lambda result:None)
    game.step()
    game.commit_commerce()
    assert player.progress['event_forecasts'][plan.id]['final']['state'] == 'cancelled'
    assert player.progress['event_forecasts'][plan.id]['revision'] == revision
    draft = owner.scheduler.fork()
    for index in range(HISTORY_PLANS+2):
        now = owner.now()+index
        later = draft.reserve(owner.content.events['curfew'],now,index,owner.eligible,forced=True)
        draft.cancel(later.id,now,'Fixture history')
        draft.advance(now,owner.eligible)
    game.clock.advance((HISTORY_PLANS+2)*TICK_HZ)
    assert owner.write(draft,[])
    game.commit_commerce()
    assert plan.id not in owner.scheduler.plans
    state = {'events':owner.scheduler.record(),'players':[player.record()],
        'identities':deepcopy(game.core.characters.identities),
        'items':[item.record() for item in owner.commerce.items.values()],
        'commerce':{'item_serial':owner.commerce.serial,'caches':deepcopy(owner.commerce.caches)}}
    restored = HeadlessServer(owner.content,character_state=state,clock=game.clock)
    caller = restored.connect({'user_id':1,'handle':'Archived\u754c','node_name':'test'})
    place(restored,caller,zone.id,restored.core.world.free_tile(zone.id,terminal.tile))
    player = restored.core.characters.players[caller.session.player_id]
    assert plan.id not in restored.core.events.scheduler.plans
    return restored,caller,player,plan.id
