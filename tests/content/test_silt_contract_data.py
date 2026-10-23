"""Entity 1.10: authored Silt jobs cannot borrow another graph's cells."""

import json
from pathlib import Path

import pytest

from blacksite.content.formats import read_record
from blacksite.content.loader import load_content
from blacksite.content.schema import ContractTemplate
from blacksite.content.validate import validate


@pytest.mark.parametrize('broken,expected', [
    ('', ''),
    ('cell', 'never coordinates'),
    ('band', 'authored Silt band'),
    ('data', 'exact mission data'),
    ('cash', 'permanent unlocks'),
])
def test_entity_1_10_silt_target_uses_its_own_mission_record(repo_root: Path, broken: str, expected: str) -> None:
    record = {'id':'fixture-silt', 'faction':'vesper', 'story':True, 'crew_scaling':False,
        'mission_data':[{'id':'fixture-copy','kind':'contract_key','amount':1,'respawn_seconds':0,'scope':'mission'}],
        'stages':[{'id':'copy', 'verb':'hack', 'input':'lift', 'completion':'lifted', 'receipt_key':'fixture:silt-copy',
            'target':{'kind':'silt_data','sector':'lat-old-works','band':'shallows','data':'fixture-copy'}}]}
    target = record['stages'][0]['target']
    if broken == 'cell':
        target['cell'] = 'b0-01'
    elif broken == 'band':
        target['band'] = 'missing-band'
    elif broken == 'data':
        target['data'] = 'not-owned-by-this-job'
    elif broken == 'cash':
        record['mission_data'][0]['kind'] = 'chits'
    job, problems = read_record(json.dumps(record), 'fixture-contract.json', ContractTemplate)
    assert not problems and job is not None
    tree = load_content(repo_root/'src/blacksite/content')
    tree.contracts[job.id] = job
    messages = [p.message for p in validate(tree)]
    if broken:
        assert any(expected in message for message in messages)
    else:
        assert not messages
