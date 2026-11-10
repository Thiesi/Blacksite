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
# Content changes after S43 may re-pin a case's body hash only; the original
# capture stays untouched as evidence, and every other key must still match it.
REPINS = json.loads((BASELINE.parent/'content-repins.json').read_text(encoding='utf-8'))


@pytest.mark.parametrize('before', CASES, ids=[f"{c['zone']}-{c['mode']}" for c in CASES])
def test_pre_s43_encoded_frames_bodies_and_actor_traces(before: dict[str, Any]) -> None:
    after = execute(before['zone'], before['mode'], before['ticks'], observed=False)
    repin = REPINS.get(f"{before['zone']}-{before['mode']}", {})
    for key in ('frame_sha256', 'body_sha256', 'actor_trace_sha256', 'inputs', 'successful_moves'):
        expected = repin['body_sha256'] if key == 'body_sha256' and 'body_sha256' in repin else before[key]
        assert after[key] == expected, (before['zone'], before['mode'], key)
