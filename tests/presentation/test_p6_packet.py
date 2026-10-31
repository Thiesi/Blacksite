"""A4: artifact assertions cannot replace the independently pinned source."""

import json
from pathlib import Path
import subprocess

import pytest

from scripts.presentation_p6_packet import ROOT, build_packet, source_hash


def git_sources() -> tuple[str,str]:
    head = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    tree = subprocess.check_output(['git','rev-parse',f'{head}:src/blacksite'],cwd=ROOT,text=True).strip()
    return head,tree


def test_p6_packet_rejects_wrong_pinned_git_tree() -> None:
    head,_ = git_sources()
    with pytest.raises(ValueError,match='expected source tree'):
        source_hash(head,'0'*40)


def test_p6_packet_rejects_artifacts_own_forged_source_hash(tmp_path: Path) -> None:
    head,tree = git_sources()
    name = 'p6-fixture-dark-80x24'
    artifact = tmp_path/name/'p6-proof'
    artifact.mkdir(parents=True)
    (artifact/'result.json').write_text(json.dumps({'head':head,'passed':True,'show':True,
        'source_matched_wheel':{'python_tree_sha256':'0'*64}}),encoding='utf-8')
    output = tmp_path/'packet'
    with pytest.raises(ValueError,match='native Python source hash differs from pinned source tree'):
        build_packet(tmp_path,[{'name':name,'id':1}],1,head,output,source_tree=tree)
    assert not output.exists()
