"""The old-content control must not inherit files from today's checkout."""

from hashlib import sha256
import io
from pathlib import Path
import tarfile

import pytest

from scripts import measure_row_control as control


@pytest.mark.parametrize('package', ['blacksite', 'karst41'])
def test_exact_snapshot_is_whole_revision_data_not_a_checkout_overlay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, package: str,
) -> None:
    checkout = tmp_path/'checkout'
    late = checkout/'src/karst41/content/late.json'
    late.parent.mkdir(parents=True)
    late.write_bytes(b'{"late":true}')
    old = b'{"population":8}\n'
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w') as archive:
        for name, data in [('zones/old.json', old), ('__init__.py', b'raise AssertionError')]:
            member = tarfile.TarInfo(f'src/{package}/content/'+name)
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))
    monkeypatch.setattr(control, 'at_revision', lambda ref, path, *, root: f'src/{package}/content')
    commands = []
    def archive_bytes(command: list[str], **kwargs: object) -> bytes:
        commands.append(command)
        return buffer.getvalue()
    monkeypatch.setattr(control.subprocess, 'check_output', archive_bytes)
    destination = tmp_path/'snapshot'
    hashes = control.exact_snapshot(checkout, destination, 'a'*40)
    assert commands == [['git', 'archive', '--format=tar', 'a'*40, f'src/{package}/content/']]
    assert (destination/'zones/old.json').read_bytes() == old
    assert hashes == {str(Path('zones')/'old.json'): sha256(old).hexdigest()}
    assert not (destination/'late.json').exists()
    assert not (destination/'__init__.py').exists()


def test_method_identity_preserves_non_rename_changes() -> None:
    before = (b'from blacksite.door.model import Display\n'
              b"SOURCES = ('src/blacksite/door/cells.py',)\n"
              b"TemporaryDirectory(prefix='blacksite-a8-')\nseconds = 12\n")
    after = before.replace(b'blacksite', b'karst41')
    assert sha256(before).digest() != sha256(after).digest()
    assert control.method_sha256(before) == control.method_sha256(after)
    assert control.method_sha256(after.replace(b'12', b'10')) != control.method_sha256(before)
    # Other data and in-world names are not erased by the method adapter.
    assert control.method_sha256(b"title = 'Blacksite'\n") != control.method_sha256(b"title = 'Karst 41'\n")
