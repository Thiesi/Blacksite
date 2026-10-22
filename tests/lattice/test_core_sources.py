"""Game 6.7/13.1: source receipts, retry and uptime survive a restart."""

from blacksite.content.schema import DataSpec
from blacksite.server.lattice.cores import Sources, trace_thresholds
import pytest


def test_design_6_7_failed_claim_retries_without_spending_the_unit():
    ledger = Sources("node", {})
    spec = DataSpec("cash", "chits", 1800, amount=80)
    current = ledger.refresh("lat-civic-ledger:cash", spec, 0)
    proposal = ledger.propose("lat-civic-ledger:cash", spec, current.generation, 0)
    with pytest.raises(ValueError, match="settling"):
        ledger.propose(proposal.key, spec, current.generation, 0)
    ledger.finish(proposal, False)
    assert ledger.refresh(proposal.key, spec, 10).available
    retry = ledger.propose(proposal.key, spec, current.generation, 10)
    assert retry.unit_id == proposal.unit_id
    ledger.finish(retry, True)
    assert not ledger.refresh(proposal.key, spec, 11).available


def test_design_6_7_durable_claim_before_lost_reply_cannot_repeat_after_restart():
    ledger = Sources("node", {})
    spec = DataSpec("cash", "chits", 1800, amount=80)
    current = ledger.refresh("core:cash", spec, 0)
    claim = ledger.propose("core:cash", spec, current.generation, 0)
    # This is the exact state committed alongside the reward. Restart
    # before a response does not depend on the old commit callback.
    durable = ledger.record(0, claim)
    restored = Sources("node", durable)
    with pytest.raises(ValueError, match="changed"):
        restored.propose("core:cash", spec, 0, 18000)
    next_claim = restored.propose("core:cash", spec, 1, 18000)
    assert next_claim.unit_id != claim.unit_id
    assert next_claim.unit_id.startswith("node:")


def test_design_13_1_offline_time_does_not_respawn_contributions():
    ledger = Sources("node", {})
    spec = DataSpec("telemetry", "contribution", 3600, amount=1)
    key = "season1:lat-core:floor:telemetry"
    ledger.refresh(key, spec, 0)
    claim = ledger.propose(key, spec, 0, 0)
    ledger.finish(claim, True)
    saved = ledger.record(100)
    # Restart's tick origin is unrelated to the previous process. No UTC
    # duration is supplied to the uptime counter, even after weeks away.
    restored = Sources("node", saved, start_tick=900)
    assert restored.uptime(900) == 10
    assert not restored.refresh(key, spec, 900).available
    assert not restored.refresh(key, spec, 900 + 35899).available
    assert restored.refresh(key, spec, 900 + 35900).available


def test_design_6_7_failed_rig_roll_is_not_rerolled_by_inspection_or_new_seed():
    spec = DataSpec("dead-rig", "item", 1800, amount=1,
                    asset="item_rig_portable_ow_brick", chance=1/3)
    ledger = Sources("node", {})
    key = next(k for i in range(100) if not ledger.refresh(k := f"season1:sector{i}:drift:dead-rig", spec, 0).available)
    first = ledger.sources[key]
    for tick in range(1, 100):
        assert ledger.refresh(key, spec, tick) == first
    restored = Sources("node", ledger.record(100))
    assert restored.refresh(key, spec, 0) == first


def test_design_6_7_street_lock_is_identity_and_core_scoped():
    ledger = Sources("node", {})
    ledger.lock("bbs-user-1", "core-a", 1000)
    restored = Sources("node", ledger.record(0))
    assert restored.locked("bbs-user-1", "core-a", 1299)
    assert not restored.locked("bbs-user-2", "core-a", 1299)
    assert not restored.locked("bbs-user-1", "core-b", 1299)
    assert not restored.locked("bbs-user-1", "core-a", 1300)


def test_design_6_7_trace_consequences_do_not_repeat_after_alibi():
    seen = set()
    assert trace_thresholds(49, 55, seen) == (50,)
    assert trace_thresholds(45, 55, seen) == ()
    assert trace_thresholds(55, 100, seen) == (100,)
    assert trace_thresholds(80, 100, seen) == ()
