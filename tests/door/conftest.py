from pathlib import Path

import pytest

from blacksite.door.doorinfo import DoorInfo


@pytest.fixture
def info(scratch_dir: Path) -> DoorInfo:
    return DoorInfo(scratch_dir / "door_info.json", scratch_dir,
                    {"user_id": 1, "handle": "Wide界", "node_name": "test"}, 80, 24, "256", 3600)
