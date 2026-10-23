"""Game 9.4: a retryable race, independent of a live event schedule."""
from dataclasses import replace
from pathlib import Path

from blacksite.content.loader import load_content
from blacksite.content.schema import Stage, StageTarget
from blacksite.server.contracts.engine import Engine, Fact, Participant
from tests.contracts.test_engine import template
from tests.contracts.test_adapter import live, shipped


def test_game_9_4_window_starts_on_launch_commit_and_survives_restart_then_retries_checkpoint():
    target = StageTarget('zone_object',zone='fixture',object='launch')
    stages = (
        Stage('brief','survey',target,'inspect','recorded','window:brief'),
        Stage('launch','survey',target,'inspect','recorded','window:launch'),
        Stage('recover','fetch',replace(target,object='cache',item='salvage'),'carry','carried',
              'window:recover',window_seconds=180,retry_from='launch'),
        Stage('return','fetch',target,'carry','delivered','window:return',requires_item='salvage'))
    job = template('window',story=True,stages=stages)
    engine = Engine('window',{job.id:job})
    instance = engine.accept(engine.story_offer(job.id,'a'),(Participant('a','bbs-a'),),0)
    def fact(sid,verb,completion,where,subject):
        progress=instance.stages[instance.index]
        return Fact('a',verb,completion,where,subject,subject,instance=instance.id,
                    stage=sid,attempt=progress.attempt)
    engine.observe(fact('brief','survey','recorded',target,'brief'),1)
    engine.expire(5000)  # Preparation has no timer.
    assert instance.state == 'active' and instance.index == 1
    engine.observe(fact('launch','survey','recorded',target,'launch'),5000)
    assert instance.stages[2].started_at == 5000
    stale = fact('recover','fetch','carried',stages[2].target,'cache-unit')
    assert not engine.observe(stale,5180)  # Exact deadline is closed.
    engine = Engine('window',engine.templates,engine.record())
    instance = engine.instances[instance.id]
    assert engine.expire(5180) == (instance.id,)
    assert instance.state == 'failed'
    engine.retry(instance.id,'a',6000)
    assert instance.index == 1 and instance.stages[0].complete
    assert not instance.stages[2].counts and instance.stages[2].started_at is None
    assert instance.stages[1].attempt == instance.stages[2].attempt == 1
    assert not engine.observe(stale,6000)
    engine.observe(fact('launch','survey','recorded',target,'launch-2'),6001)
    engine.observe(fact('recover','fetch','carried',stages[2].target,'cache-unit-2'),6180)
    assert instance.index == 3
    engine.expire(90000)  # Returning the recovered item has no timer.
    assert instance.state == 'active'
    engine.observe(fact('return','fetch','delivered',target,'delivered-unit'),90000)
    assert instance.state == 'complete'


def test_game_9_4_authored_race_discloses_window_and_relaunch_point():
    content=load_content(Path(__file__).parents[2]/'src/blacksite/content')
    job=content.contracts['fer-s1-1-race']
    assert job.stages[0].target.zone == 'scour-landing'
    assert job.stages[1].window_seconds == 180
    assert job.stages[1].retry_from == job.stages[0].id
    assert job.stages[2].window_seconds == 0
    assert '180' in job.consequence and '180' in job.stages[0].label


def test_ui_11_current_field_window_remains_visible_in_compact_hud(live):
    game,owner,callers,players=live
    base=template('hud-window',story=True)
    job=replace(base,stages=(replace(base.stages[0],window_seconds=180),))
    owner.content.contracts[job.id]=owner.state.engine.templates[job.id]=job
    draft=owner.state.fork()
    instance=draft.engine.accept(draft.engine.story_offer(job.id,players[0].id),
                                 (owner.participant(players[0].id),),owner.now())
    owner.write(draft)
    game.commit_commerce()
    body={'viewport':[],'me':{}}
    owner.decorate(callers[0].session,body)
    assert '180s left' in body['objective']['cost'] and body['hint'].startswith('180s left')
    game.clock.advance(300)
    owner.decorate(callers[0].session,body)
    assert body['hint'].startswith('150s left')
