"""Installed content upgrade, durable zone seeds and the local walk bot."""

import asyncio
from pathlib import Path

from blacksite.bot.__main__ import run
from blacksite.server.app import Server
from blacksite.version import PACKAGE_VERSION


def test_zone_upgrade_seed_restart_and_walk_bot(scratch_dir: Path, capsys: object) -> None:
    async def scenario() -> None:
        first = Server(scratch_dir, tcp=True)
        await first.start()
        try:
            seeds = dict(first.storage.meta("rng_seeds"))
            first.storage.mark_dirty("meta", "content_package_version", "0.0.1")
            first.storage.flush_now()
        finally:
            await first.stop()
        # Recreate an old installed content tree missing the new map.
        (scratch_dir / "content/zones/vatside-wake-hall.map").unlink()
        second = Server(scratch_dir, tcp=True, spawn_zone="vatside-wake-hall")
        await second.start()
        try:
            assert second.storage.meta("content_package_version") == PACKAGE_VERSION
            assert second.storage.meta("rng_seeds") == seeds
            assert {key: zone.seed for key, zone in second.world.zones.items()} == seeds
            async with asyncio.timeout(5):
                await run(scratch_dir, False, 80, 24, steps=4, seed=3)
        finally:
            await second.stop()
    asyncio.run(scenario())
    output = capsys.readouterr().out
    assert "pong " in output and "walk 4 inputs" in output and "bye logout" in output
