"""The explicit demo layer must not overwrite unowned local files."""

import json

import pytest

from scripts.demo_sodium.content import install_overlay, load_demo_content
from karst41.content.validate import validate


def test_demo_overlay_validates_and_refreshes_its_own_files(tmp_path):
    install_overlay(tmp_path)
    marker = tmp_path / 'characters-preserved.marker'
    marker.write_text('keep')
    install_overlay(tmp_path)
    assert marker.read_text() == 'keep'
    assert (tmp_path / 'content.local/zones/sodium-row.map').is_file()
    assert not validate(load_demo_content())


def test_demo_refuses_to_replace_an_unowned_local_record(tmp_path):
    record = tmp_path / 'content.local/zones/sodium-row.map'
    record.parent.mkdir(parents=True)
    record.write_text('my map')
    with pytest.raises(ValueError, match='unowned'):
        install_overlay(tmp_path)
    assert record.read_text() == 'my map'


def test_demo_manifest_cannot_escape_the_install_directory(tmp_path):
    marker = tmp_path / 'keep'
    marker.write_text('keep')
    (tmp_path / '.round4-content.json').write_text(json.dumps(['../keep']))
    with pytest.raises(ValueError, match='escapes'):
        install_overlay(tmp_path)
    assert marker.read_text() == 'keep'
