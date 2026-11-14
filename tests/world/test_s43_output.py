"""S43 must match the committed, pre-optimization twenty-scene output."""

import gzip
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

import pytest

from scripts.measure_s43_invalidations import execute


BASELINE = Path(__file__).resolve().parents[2]/'docs/ops/captures/s43/invalidations-before.json.gz'
RAW = BASELINE.read_bytes()
assert sha256(RAW).hexdigest() == 'd3e5286031f82ea17d8c132ae13a7f21fb89a1566fc1e3df8c0a2136ae32fd12'
CASES = json.loads(gzip.decompress(RAW))['cases']
# S43's claim is that the off-loop work does not change what the server does.
# Two kinds of change after S43 may re-pin a case's frame and body hashes,
# each with a reason:
# - a content change (new actors or text in view; technical lead, #237);
# - a setup-path change where the bodies match the capture once `base`/`rev`
#   are normalised, and the traces, inputs and moves are unchanged
#   (technical lead, S48c1a; checked by scripts/compare_s43_normalised.py).
# Neither may re-pin the actor trace, the inputs or the successful moves. The
# original capture stays untouched as evidence.
REPINS = json.loads((BASELINE.parent/'content-repins.json').read_text(encoding='utf-8'))
REPINNABLE = ('frame_sha256', 'body_sha256')


def test_content_repins_carry_only_frame_and_body_with_a_reason() -> None:
    known = {f"{c['zone']}-{c['mode']}" for c in CASES}
    for case, entry in REPINS.items():
        assert case in known, case
        assert entry.get('reason') and isinstance(entry.get('pr'), int), case
        assert set(entry) - {'reason', 'pr'} <= set(REPINNABLE), (case, sorted(entry))
        assert set(entry) & set(REPINNABLE), case


@pytest.mark.parametrize('before', CASES, ids=[f"{c['zone']}-{c['mode']}" for c in CASES])
def test_pre_s43_encoded_frames_bodies_and_actor_traces(before: dict[str, Any]) -> None:
    after = execute(before['zone'], before['mode'], before['ticks'], observed=False)
    repin = REPINS.get(f"{before['zone']}-{before['mode']}", {})
    for key in ('frame_sha256', 'body_sha256', 'actor_trace_sha256', 'inputs', 'successful_moves'):
        expected = repin[key] if key in REPINNABLE and key in repin else before[key]
        assert after[key] == expected, (before['zone'], before['mode'], key)
