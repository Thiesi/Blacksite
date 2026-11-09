"""R1 evidence must preserve a real complete frame and fail closed on data."""

from hashlib import sha256
import json
from pathlib import Path
import sqlite3

import pytest

from karst41.door.doorinfo import DoorInfo
from karst41.door.model import Display
from karst41.door.terminal import ENTER
from scripts.audit_r1_world import audit
from scripts.r1_title import title_prefix


def r1_title(motd: str) -> dict:
    """The title body as R1 shipped it. scripts/r1_title.py pins R1's subtitle,
    so this proof replays R1's screen rather than the current one."""
    return {"screen": "title", "title": "KARST 41", "lines": ["", "The city was built to keep something in.",
        "Nobody remembers what.", "", "a real-time door for NetBBS   .   Karst, Year 41", "", motd,
        "", "? help    Ctrl-X leave"], "page": 1, "pages": 1}


def title_frames(tmp_path: Path, presentation: bool = False) -> tuple[bytes, bytes, bytes]:
    info = DoorInfo(tmp_path/'unused', tmp_path, {'handle': 'Wide界', 'user_id': 1}, 80, 24, '256', 3600)
    model = Display(info, presentation=presentation)
    first = model.render(0)[0]
    model.body = r1_title('Latest welcome')
    model.force_full = model.dirty = True
    second = model.render(1)[0]
    model.body = {'title': 'THE WAKE', 'lines': ['Continue']}
    model.force_full = model.dirty = True
    return first, second, model.render(2)[0]


@pytest.mark.parametrize("presentation", (False, True))
def test_r1_title_is_last_complete_original_prefix(tmp_path: Path, presentation: bool) -> None:
    first, second, wake = title_frames(tmp_path, presentation)
    raw = ENTER+first+second+wake
    captured, terminal = title_prefix(raw, 80, 24)
    assert captured == ENTER+first+second
    assert 'Latest welcome' in terminal.screen_text()
    assert 'THE WAKE' not in terminal.screen_text()


@pytest.mark.parametrize("presentation", (False, True))
def test_r1_partial_title_cannot_be_claimed_as_capture(tmp_path: Path, presentation: bool) -> None:
    first, _, wake = title_frames(tmp_path, presentation)
    incomplete = first.split(b'\x1b[24;1H')[0]
    with pytest.raises(AssertionError, match='No complete'):
        title_prefix(ENTER+incomplete+wake, 80, 24)


@pytest.mark.parametrize('value', (
    json.dumps({'zone': 'blacksite-l1', 'message': 'the Blacksite'}),
    json.dumps({'__module__': 'blacksite.server.character'}),
    json.dumps({'__module__': 'karst41.server.character'}),
    json.dumps({'blacksite_cache': []}),
    b'\x80\x04pickle is never executed',
))
def test_r1_offline_audit_distinguishes_places_from_serialized_names(tmp_path: Path, value: str | bytes) -> None:
    path = tmp_path/'fixture.db'
    with sqlite3.connect(path) as database:
        database.execute('CREATE TABLE record(value)')
        database.execute('INSERT INTO record VALUES (?)', (value,))
    before = sha256(path.read_bytes()).hexdigest()
    report = audit(path)
    assert report['migration_required'] == ('zone' not in str(value))
    assert report['database_sha256'] == before == sha256(path.read_bytes()).hexdigest()
