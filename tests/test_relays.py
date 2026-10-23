"""Game 7.4: active participation, pauses and single-source payments."""

from blacksite.server.clock import TICK_HZ
from blacksite.server.relays import Claims, Ledger, Participant


def person(pid='holder', faction='halvard', identity=None):
    return Participant(pid, identity or pid, faction)


def test_game_7_4_current_claim_hack_completes_after_three_minutes():
    claims = Claims()
    claim = claims.start('cold-chain', person())
    claims.support(claim.id, person('runner', None))
    assert not claims.hack('stale-claim', 'runner')
    assert not claims.hack(claim.id, 'bystander')
    claims.step(0, {'holder'}, {'holder'}, set())
    assert claims.step(180*TICK_HZ, {'holder'}, {'holder'}, set()) == ()
    assert claims.hack(claim.id, 'runner')
    assert claims.step(181*TICK_HZ, {'holder'}, {'holder'}, set()) == (claim,)
    assert [p.player for p in claim.participants()] == ['holder', 'runner']


def test_game_7_4_solo_eight_minutes_never_counts_bystanders_or_unfinished_support():
    claims = Claims()
    claim = claims.start('cold-chain', person())
    claims.support(claim.id, person('did-not-hack', 'choir'))
    claims.step(0, {'holder', 'bystander'}, {'holder', 'bystander'}, set())
    assert not claims.step(479*TICK_HZ, {'holder'}, {'holder'}, set())
    assert claims.step(480*TICK_HZ, {'holder'}, {'holder'}, set()) == (claim,)
    assert claim.participants() == (person(),)


def test_game_7_4_opposing_claims_and_curfew_freeze_then_resume_exact_clock():
    claims = Claims()
    first = claims.start('cold-chain', person())
    claims.step(0, {'holder'}, {'holder'}, set())
    claims.step(100*TICK_HZ, {'holder'}, {'holder'}, set())
    other = claims.start('cold-chain', person('opponent', 'choir'))
    claims.step(200*TICK_HZ, {'holder','opponent'}, {'holder','opponent'}, set())
    assert first.elapsed == 100*TICK_HZ and other.elapsed == 0
    claims.withdraw('opponent')
    claims.step(300*TICK_HZ, {'holder'}, {'holder'}, {'cold-chain'})
    assert first.elapsed == 100*TICK_HZ
    claims.step(400*TICK_HZ, {'holder'}, {'holder'}, set())
    assert first.elapsed == 200*TICK_HZ


def test_game_7_4_absence_grace_does_not_advance_and_death_aborts():
    claims = Claims()
    first = claims.start('cold-chain', person())
    claims.step(0, {'holder'}, {'holder'}, set())
    claims.step(TICK_HZ, {'holder'}, set(), set())
    claims.step(6*TICK_HZ, {'holder'}, set(), set())
    assert first.id in claims.active and first.elapsed == 0
    claims.step(6*TICK_HZ+1, {'holder'}, set(), set())
    assert first.id not in claims.active
    second = claims.start('cold-chain', person())
    claims.step(7*TICK_HZ, set(), set(), set())
    assert second.id not in claims.active


def test_game_7_4_influence_carries_fraction_across_flip_restart_and_cutoff():
    ledger = Ledger()
    rates = {'ordinary':10, 'scour':30, 'shaft':20}
    for relay in rates:
        ledger.set_owner(relay, 'halvard', 'holder', 0, rates)
    assert ledger.settle(rates, 30) == 0
    ledger = Ledger(ledger.record())
    ledger.set_owner('ordinary', 'choir', 'other', 60, rates)
    assert ledger.totals('halvard')['influence'] == 1
    assert ledger.owner('ordinary', 59) == 'halvard'
    assert ledger.owner('ordinary', 60) == 'choir'
    ledger.state['cutoff'] = 120
    ledger.settle(rates, 7200)
    assert ledger.totals('halvard')['influence'] == 1
    assert ledger.totals('choir')['influence'] == 0
    ledger.settle(rates, 8000)
    assert ledger.totals('halvard')['influence'] == 1


def test_game_7_4_capture_receipt_identity_cannot_farm_through_other_character():
    ledger, claims = Ledger(), Claims()
    claim = claims.start('ordinary', person(identity='bbs-1'))
    capture = ledger.capture(claim, 0, {'ordinary':10})
    assert capture.rewarded == (claim.holder,) and capture.former is None
    ledger.set_owner('ordinary', 'choir', None, 1, {'ordinary':10})
    claims.withdraw('holder')
    claim = claims.start('ordinary', person('replacement', identity='bbs-1'))
    assert not ledger.capture(claim, 86399, {'ordinary':10}).rewarded
    ledger.set_owner('ordinary', 'choir', None, 86400, {'ordinary':10})
    assert ledger.capture(claim, 86400, {'ordinary':10}).rewarded == (claim.holder,)


def test_game_7_4_daily_share_once_identity_across_factions_and_restart():
    ledger = Ledger()
    ledger.totals('halvard')['treasury'] = 25000
    assert ledger.daily_share('bbs-1','halvard','2026-01-01') == 200
    ledger = Ledger(ledger.record())
    ledger.totals('choir')['treasury'] = 10000
    assert ledger.daily_share('bbs-1','choir','2026-01-01') == 0
    assert ledger.daily_share('bbs-1','choir','2026-01-02') == 100
    assert ledger.totals('choir')['treasury'] == 9900


def test_game_7_4_reset_stops_old_score_preserves_earned_treasury_and_history():
    ledger, rates = Ledger(), {'ordinary':10}
    ledger.set_owner('ordinary', 'halvard', 'holder', 0, rates)
    ledger.reset_season(2, 7200, rates)
    assert ledger.owner('ordinary') is None
    assert ledger.owner('ordinary', 7000) == 'halvard'
    assert ledger.totals('halvard') == {'influence':0,'treasury':20,'fraction':0}
    ledger.settle(rates, 14400)
    assert ledger.totals('halvard')['treasury'] == 20
