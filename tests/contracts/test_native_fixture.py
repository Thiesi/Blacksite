"""Game 7.5/9.4: explicit native fixture bindings validate independently."""
from pathlib import Path

from blacksite.content.loader import load_content
from blacksite.content.validate import validate
from blacksite.server.contracts.ledger import Ledger
from scripts.contracts_fixture import build_fixture


def test_game_7_5_9_4_native_fixture_activates_only_its_resolved_services_and_story_copies(repo_root: Path,tmp_path: Path) -> None:
    shipped=repo_root/'src/blacksite/content'
    local=tmp_path/'content.local'
    descriptor=build_fixture(shipped,local)
    fixture=load_content(shipped,local)
    assert not validate(fixture)
    state=Ledger('native-fixture',fixture)
    assert set(state.services.nodes) == {'cold-chain','sump','depot','relay-zero'}
    original=load_content(shipped)
    for tid in ('sab-s1-1-retrieval','unm-s1-2-vat-nine','kes-s1-2-diversion'):
        assert fixture.active('contracts',tid) and not original.active('contracts',tid)
        assert fixture.contracts[tid].reward == original.contracts[tid].reward
        assert fixture.contracts[tid].branch_group == original.contracts[tid].branch_group
    assert original.active('services','sump')
    assert original.services['sump'].zone == 'sink-floor'
    assert fixture.services['sump'].zone == descriptor['zone']
    assert fixture.cores[descriptor['core']].hardware[0].tile == (9,10)
    assert fixture.zones[descriptor['zone']].meta.layouts
