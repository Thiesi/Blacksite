"""Development-only idle/help CPU acceptance; no extra dependencies.

Run from the repository root with an editable install. It starts a
private service and the real door module over native stdio pipes.
NetBBS transport acceptance is a separate check.
"""

import argparse
import asyncio
import ctypes
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from blacksite.server.app import Server
from tests.fake_terminal import FakeTerminal


async def measure(root: Path, seconds: int) -> None:
    root.mkdir(parents=True, exist_ok=True)
    service = Server(root / "world", tcp=True, characters=False)
    await service.start()
    drop = root / "door_info.json"
    drop.write_text(json.dumps({"handle": "Idle界", "user_id": "idle-probe", "terminal_width": 80,
        "terminal_height": 24, "color_depth": "256", "node_name": "local"}), encoding="utf-8")
    env = {**os.environ, "NETBBS_DOOR_INFO": str(drop.resolve()), "BLACKSITE_INSTALL_DIR": str(service.install_dir)}
    executable = sys.executable
    if os.name == "nt":
        # A Windows venv python.exe is a redirector whose CPU time excludes
        # the interpreter it starts. Measure the actual standard-library
        # runtime directly, loading the same package source explicitly.
        executable = sys._base_executable
        env["PYTHONPATH"] = str(Path(__file__).resolve().parent.parent / "src")
    child = await asyncio.create_subprocess_exec(executable, "-m", "blacksite.door", env=env,
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    terminal = FakeTerminal()
    handle = None
    if os.name == "nt":
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        kernel.OpenProcess.restype = wintypes.HANDLE
        handle = kernel.OpenProcess(0x1000, False, child.pid)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        kernel.GetProcessTimes.argtypes = (wintypes.HANDLE, *([ctypes.POINTER(wintypes.FILETIME)] * 4))
        kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    else:
        import resource
        cpu_before = resource.getrusage(resource.RUSAGE_CHILDREN)

    async def collect() -> None:
        while chunk := await child.stdout.read(65536):
            terminal.write(chunk)

    output = asyncio.create_task(collect())
    started = time.monotonic()
    try:
        while time.monotonic() - started < seconds:
            child.stdin.write(b"?")
            await child.stdin.drain()
            await asyncio.sleep(.2)
            child.stdin.write(b"\x1b[6~")
            await child.stdin.drain()
            await asyncio.sleep(.2)
            child.stdin.write(b"\x1b\x0c")
            await child.stdin.drain()
            print(f"idle/help probe: {int(time.monotonic() - started)}/{seconds}s", flush=True)
            await asyncio.sleep(min(59.6, max(0, seconds - (time.monotonic() - started))))
        child.stdin.write(b"\x18y")
        await child.stdin.drain()
        code = await asyncio.wait_for(child.wait(), 5)
        await output
        errors = (await child.stderr.read()).decode("utf-8", errors="replace")
        if os.name == "nt":
            values = [wintypes.FILETIME() for _ in range(4)]
            if not kernel.GetProcessTimes(handle, *(ctypes.byref(value) for value in values)):
                raise ctypes.WinError(ctypes.get_last_error())
            cpu = sum((value.dwHighDateTime << 32) | value.dwLowDateTime for value in values[2:]) / 10_000_000
        else:
            after = resource.getrusage(resource.RUSAGE_CHILDREN)
            cpu = after.ru_utime + after.ru_stime - cpu_before.ru_utime - cpu_before.ru_stime
        result = {"seconds": seconds, "wall_seconds": time.monotonic() - started, "cpu_seconds": cpu,
                  "exit_code": code, "output_bytes": len(terminal.written), "stderr": errors}
        (root / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result), flush=True)
        assert code == 0 and not errors and "Karst keeps your place." in terminal.screen_text()
        assert 0 < cpu < 20 if seconds >= 600 else True
    finally:
        if child.returncode is None:
            child.kill()
            await child.wait()
        output.cancel()
        await asyncio.gather(output, return_exceptions=True)
        if handle:
            kernel.CloseHandle(handle)
        await service.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(".test-tmp/idle-acceptance"))
    parser.add_argument("--seconds", type=int, default=600)
    args = parser.parse_args()
    asyncio.run(measure(args.root, args.seconds))
