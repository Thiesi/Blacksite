"""R1: new operator names win, with bounded S31 compatibility logging."""

import json
import logging
import os
from pathlib import Path
import subprocess
import sys

import pytest

from karst41.door.doorinfo import read
from karst41.environment import _legacy_notice, setting


NAMES = ('KARST41_INSTALL_DIR', 'KARST41_SESSION_LIMIT',
         'DOOR_KARST41_INSTALL_DIR', 'DOOR_KARST41_SESSION_LIMIT',
         'DOOR_KARST41_PRESENTATION', 'KARST41_PRESENTATION_TRIAL',
         'KARST41_SCRATCH_LIMIT')


@pytest.mark.parametrize('name', NAMES)
@pytest.mark.parametrize('generation', ('new', 'old', 'both', 'neither'))
def test_r1_each_environment_name(name: str, generation: str) -> None:
    # Remove in S31: the old spelling is deliberately exercised here.
    old = name.replace('KARST41', 'BLACKSITE')
    environment = {}
    if generation in ('new', 'both'):
        environment[name] = 'new'
    if generation in ('old', 'both'):
        environment[old] = 'old'
    expected = {'new': 'new', 'old': 'old', 'both': 'new', 'neither': 'default'}[generation]
    assert setting(environment, (name,), 'default') == expected


def test_r1_empty_new_value_is_set_and_does_not_revive_old_value() -> None:
    # Remove in S31.
    assert setting({'KARST41_INSTALL_DIR': '', 'BLACKSITE_INSTALL_DIR': 'old'},
                   ('KARST41_INSTALL_DIR',)) == ''


def test_r1_all_new_aliases_beat_every_legacy_alias(tmp_path: Path) -> None:
    path = tmp_path/'door.json'
    path.write_text(json.dumps({'handle': 'Wide界', 'user_id': 1,
        'terminal_width': 80, 'terminal_height': 24, 'session_limit_seconds': 120}))
    # Remove in S31: a legacy DOOR_* profile cannot beat a new standalone name.
    environment = {'NETBBS_DOOR_INFO': str(path),
        'KARST41_INSTALL_DIR': str(tmp_path/'new'), 'DOOR_BLACKSITE_INSTALL_DIR': str(tmp_path/'old'),
        'KARST41_SESSION_LIMIT': '60', 'DOOR_BLACKSITE_SESSION_LIMIT': '90'}
    info = read(environment)
    assert info.install == tmp_path/'new' and info.session_limit == 60
    environment.update(DOOR_KARST41_INSTALL_DIR=str(tmp_path/'door'), DOOR_KARST41_SESSION_LIMIT='30')
    info = read(environment)
    assert info.install == tmp_path/'door' and info.session_limit == 30


def test_r1_legacy_notice_is_once_per_process_and_not_game_output(
        caplog: pytest.LogCaptureFixture, capsys: pytest.CaptureFixture[str]) -> None:
    _legacy_notice.cache_clear()
    try:
        with caplog.at_level(logging.INFO, logger='karst41.environment'):
            for _ in range(2):
                for name in NAMES:
                    # Remove in S31.
                    setting({name.replace('KARST41', 'BLACKSITE'): 'private-value'}, (name,))
        records = [r for r in caplog.records if r.name == 'karst41.environment']
        assert len(records) == 1 and 'Deprecated' in records[0].message
        assert 'private-value' not in records[0].message
        assert capsys.readouterr() == ('', '')
    finally:
        _legacy_notice.cache_clear()


def test_r1_unused_legacy_alias_does_not_log(caplog: pytest.LogCaptureFixture) -> None:
    _legacy_notice.cache_clear()
    with caplog.at_level(logging.INFO, logger='karst41.environment'):
        # Remove in S31.
        assert setting({'KARST41_INSTALL_DIR': 'new', 'BLACKSITE_INSTALL_DIR': 'old'},
                       ('KARST41_INSTALL_DIR',)) == 'new'
    assert not caplog.records


def test_r1_operator_sees_one_warning_and_native_door_stays_quiet(
        tmp_path: Path, repo_root: Path) -> None:
    # Remove in S31: exercise actual process logging defaults for old names.
    environment = {**os.environ, 'PYTHONPATH': str(repo_root/'src')}
    for name in NAMES:
        environment.pop(name, None)
        environment.pop(name.replace('KARST41', 'BLACKSITE'), None)
    result = subprocess.run([sys.executable, '-c',
        'from karst41.environment import setting; '
        'setting({"BLACKSITE_INSTALL_DIR":"private"}, ("KARST41_INSTALL_DIR",)); '
        'setting({"BLACKSITE_SESSION_LIMIT":"60"}, ("KARST41_SESSION_LIMIT",))'],
        env=environment, cwd=repo_root, capture_output=True, text=True, check=True)
    assert result.stderr.count('Deprecated') == 1 and not result.stdout
    assert 'private' not in result.stderr
    path = tmp_path/'door.json'
    path.write_text(json.dumps({'handle': 'Wide界', 'user_id': 1,
        'terminal_width': 10, 'terminal_height': 4}))
    environment.update(NETBBS_DOOR_INFO=str(path), DOOR_BLACKSITE_INSTALL_DIR=str(tmp_path))
    for name in ('DOOR_KARST41_INSTALL_DIR', 'KARST41_INSTALL_DIR'):
        environment.pop(name, None)
    result = subprocess.run([sys.executable, '-m', 'karst41.door'], env=environment,
        cwd=repo_root, capture_output=True, check=True)
    assert not result.stderr and b'Deprecated' not in result.stdout
