"""Static portability guardrails; real service-manager acceptance is separate."""

import configparser
from pathlib import Path


def test_rc_script_contract_and_deploy_bytes(repo_root: Path) -> None:
    for path in (repo_root / "deploy").rglob("*"):
        if path.is_file():
            data = path.read_bytes()
            data.decode("ascii")
            assert b"\r" not in data
    script = (repo_root / "deploy/rc.d/karst41").read_text()
    assert "/usr/sbin/daemon" not in script and "daemon -" not in script
    assert 'pidfile="$karst41_dir/run/karst41.pid"' in script
    assert "-m karst41.admin" in script and "kill -TERM" in script
    assert "interpreter is not executable" in script


def test_systemd_unit_parses(repo_root: Path) -> None:
    unit = configparser.ConfigParser(interpolation=None, strict=False)
    unit.read(repo_root / "deploy/systemd/karst41.service")
    service = unit["Service"]
    assert service["Type"] == "simple" and service["User"] == "netbbs"
    assert service["Restart"] == "on-failure" and service["TimeoutStopSec"] == "15"
    assert "-m karst41.server" in service["ExecStart"]
    assert "-m karst41.admin" in service["ExecStop"]
    assert service["ExecStop"].startswith("-/"), "a completed admin stop must not fail the unit"
