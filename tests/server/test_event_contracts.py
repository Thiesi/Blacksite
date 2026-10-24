"""Game 12: source-bound jobs preserve a completed worker's return trip."""

from blacksite.content.schema import ContractTemplate, Reward, Stage, StageTarget
from blacksite.server.contracts.engine import Engine, Fact, Participant


def test_game_12_completed_event_job_keeps_standard_turnin_window() -> None:
    target = StageTarget('npc', zone='fixture-road', npc='fixture-convoy')
    template = ContractTemplate('fixture-escort', 'vesper', type='escort',
        stages=(Stage('arrive', 'escort', target, 'wait', 'arrived', 'fixture-arrival'),),
        reward=Reward((200, 200), xp=100), crew_scaling=False, event_only=True)
    engine = Engine('origin', {template.id: template})
    base = engine.offer(template, 'plan:offer', 100)
    from dataclasses import replace
    offer = replace(base, event_plan='plan')
    accepted = engine.accept(offer, (Participant('worker', 'bbs-worker'),), 0)
    incomplete = engine.accept(offer, (Participant('late', 'bbs-late'),), 0)
    assert accepted.expires_at == 100 and accepted.runtime['event_plan'] == 'plan'
    engine.observe(Fact('worker', 'escort', 'arrived', target, 'actual-convoy',
        'plan:arrival:worker', instance=accepted.id), 99)
    assert accepted.state == 'complete' and accepted.expires_at == 3699
    engine.expire(101)
    assert accepted.state == 'complete' and incomplete.state == 'failed'
    payout, = engine.claim(accepted.id, 'worker', 120)
    assert payout.payment.chits == 200 and payout.payment.xp == 100
    assert not engine.claim(accepted.id, 'worker', 121)
