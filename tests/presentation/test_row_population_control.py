"""The old-content control must not inherit files from today's checkout."""

from hashlib import sha256
import io
from pathlib import Path
import tarfile

import pytest

from scripts import measure_row_control as control


def test_exact_snapshot_is_whole_old_data_not_a_checkout_overlay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    checkout = tmp_path/'checkout'
    late = checkout/'src/blacksite/content/late.json'
    late.parent.mkdir(parents=True)
    late.write_bytes(b'{"late":true}')
    old = b'{"population":8}\n'
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w') as archive:
        for name, data in [('zones/old.json', old), ('__init__.py', b'raise AssertionError')]:
            member = tarfile.TarInfo('src/blacksite/content/'+name)
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))
    monkeypatch.setattr(control.subprocess, 'check_output', lambda *args, **kwargs: buffer.getvalue())
    destination = tmp_path/'snapshot'
    hashes = control.exact_snapshot(checkout, destination, 'a'*40)
    assert (destination/'zones/old.json').read_bytes() == old
    assert hashes == {str(Path('zones')/'old.json'): sha256(old).hexdigest()}
    assert not (destination/'late.json').exists()
    assert not (destination/'__init__.py').exists()
