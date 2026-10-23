"""S19: executable approaches, real acquisition references and permissions."""

from copy import deepcopy

import pytest

from tests.content.support import World


def extend(world: World) -> None:
    data = world.read('contracts.json')
    job = data['contracts'][0]
    alternative = deepcopy(job['stages'][1])
    alternative.update(id='network', receipt_key='fx-first-job/network')
    job.update(name='Gate record', approaches=[{'id': 'network', 'label': 'Use the terminal',
        'stages': [alternative]}], permit_scope={'kind': 'maintenance_credential',
        'target': 'fixture-gate-credential', 'expiry_seconds': 1200,
        'binding': {'kind': 'core_control', 'core': 'fx-core-a', 'control': 'c-gate'}})
    job['reward']['programs'] = ['prg_pick']
    world.write('contracts.json', data)


def test_entity_1_10_loads_alternative_program_and_typed_permit(world: World) -> None:
    extend(world)
    assert not world.problems()
    job = world.load().contracts['fx-first-job']
    assert job.approaches[0].stages[0].target.control == 'c-gate'
    assert job.reward.programs == ('prg_pick',)
    assert job.permit_scope.binding.core == 'fx-core-a'


@pytest.mark.parametrize('field,expected', [
    ('program', "program 'prg_missing'"),
    ('binding', "control 'missing' does not exist"),
    ('receipt', 'receipt key'),
    ('completion', 'completion is not a hack server fact'),
    ('quantity', 'quantity must be positive'),
    ('pool', 'target pool is too small'),
    ('window', 'field window cannot be negative'),
    ('checkpoint', 'retry checkpoint'),
])
def test_entity_1_10_rejects_unplayable_active_job_fields(world: World, field: str, expected: str) -> None:
    extend(world)
    data = world.read('contracts.json')
    job = data['contracts'][0]
    stage = job['approaches'][0]['stages'][0]
    if field == 'program':
        job['reward']['programs'] = ['prg_missing']
    elif field == 'binding':
        job['permit_scope']['binding']['control'] = 'missing'
    elif field == 'receipt':
        stage['receipt_key'] = job['stages'][0]['receipt_key']
    elif field == 'completion':
        stage['completion'] = 'defeated'
    elif field == 'quantity':
        stage['quantity'] = 0
    elif field == 'pool':
        job['stages'][0]['quantity'] = 2
    elif field == 'window':
        stage['window_seconds'] = -1
    elif field == 'checkpoint':
        stage['retry_from'] = 'missing-stage'
    world.write('contracts.json', data)
    assert any(expected in message for message in world.messages())
