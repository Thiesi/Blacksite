"""Play the proposal 68 presentation in this terminal (issue #68 playtest).

    python scripts/playtest_68.py                      # shipped maps
    python scripts/playtest_68.py --geometry candidate # Sodium Row candidate map
    python scripts/playtest_68.py --colour 16          # try another tier
    python scripts/playtest_68.py --view street        # paradigm A: eye level
    python scripts/playtest_68.py --view scene         # paradigm B: places
    python scripts/playtest_68.py --view auto          # paradigm C: chosen by context
    python scripts/playtest_68.py --view auto --inspect  # and show why (F10)
    python scripts/playtest_68.py --geometry candidate --view scene --colour truecolor --glyphs modern
                                                       # V0: the Tin Halo lit, in sextants

Starts a private foreground service under `.test-tmp/playtest-68-*` with
the trial switches on (charted public geography, ambient lines), then
runs the real door in this console with the proposal renderer selected.
The world persists between runs, so your Wake is still there next time;
`--fresh` starts over.

In play: F7 cycles the views on the same game state: shipped map,
proposal map, street view, scenes, auto. F5 shows the place card, F6 cycles
when cards appear. Danger always hands the screen to the tactical map.
In scenes and auto, comma and full stop choose a way and Space goes there;
the arrows always step. F10 shows the auto view's decision and reasons,
and every change of decision is written to `auto-trace.jsonl` beside the
world, one JSON line each, for reading after a session.
Ctrl-X then Y leaves and stops the service.

On Windows the script switches the console to UTF-8 (code page 65001)
with ANSI processing for the session and restores your settings when the
door exits; no `chcp` is needed.

The candidate geometry is a content.local overlay of Sodium Row and the
Tin Halo's return door; shipped content is never modified.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "docs/design/proposals/68-presentation/candidates/sodium-row"
UTF8 = 65001
ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004


@contextmanager
def utf8_console() -> Iterator[None]:
    """On Windows, give the door a UTF-8 console that understands ANSI,
    and put the caller's code pages and console mode back afterwards."""
    if os.name != "nt":
        yield
        return
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetStdHandle.restype = wintypes.HANDLE
    output_cp, input_cp = kernel.GetConsoleOutputCP(), kernel.GetConsoleCP()
    handle = kernel.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
    mode = wintypes.DWORD()
    has_mode = bool(kernel.GetConsoleMode(handle, ctypes.byref(mode)))
    kernel.SetConsoleOutputCP(UTF8)
    kernel.SetConsoleCP(UTF8)
    if has_mode:
        kernel.SetConsoleMode(handle, mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING)
    try:
        yield
    finally:
        if has_mode:
            kernel.SetConsoleMode(handle, mode.value)
        if output_cp:
            kernel.SetConsoleOutputCP(output_cp)
        if input_cp:
            kernel.SetConsoleCP(input_cp)


def main() -> int:
    size = shutil.get_terminal_size((80, 24))
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--geometry", choices=("shipped", "candidate"), default="shipped")
    parser.add_argument("--colour", choices=("truecolor", "256", "16"), default="256")
    parser.add_argument("--width", type=int, default=max(80, size.columns))
    parser.add_argument("--height", type=int, default=max(24, size.lines))
    parser.add_argument("--handle", default="Playtester")
    parser.add_argument("--fresh", action="store_true", help="delete this playtest world first")
    parser.add_argument("--view", choices=("shipped", "map", "street", "scene", "auto"), default="map",
                        help="the view to start in (F7 cycles)")
    parser.add_argument("--inspect", action="store_true", help="start with the auto inspector shown (F10)")
    parser.add_argument("--glyphs", choices=("cp437", "modern"), default="cp437",
                        help="modern: eye-level pictures in sextants (V0; needs a font that has them)")
    args = parser.parse_args()

    root = ROOT / ".test-tmp" / f"playtest-68-{args.geometry}"
    if args.fresh and root.exists():
        shutil.rmtree(root)
    install = root / "world"
    install.mkdir(parents=True, exist_ok=True)
    local = install / "content.local"
    if local.exists():
        shutil.rmtree(local)
    if args.geometry == "candidate":
        shutil.copytree(CANDIDATE, local)

    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(ROOT / "src"), env.get("PYTHONPATH")]))
    env["BLACKSITE_PRESENTATION_TRIAL"] = "1"
    port = install / "run" / "port"
    if port.exists():
        port.unlink()
    log = (root / "server.out").open("w", encoding="utf-8")
    server = subprocess.Popen([sys.executable, "-m", "blacksite.server", "--install-dir", str(install), "--tcp"],
                              env=env, stdout=log, stderr=subprocess.STDOUT, cwd=ROOT,
                              creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    try:
        deadline = time.monotonic() + 90
        while not (port.exists() and (install / "secrets" / "door.secret").exists()):
            if server.poll() is not None or time.monotonic() > deadline:
                print(f"The service did not start; see {root / 'server.out'}")
                return 1
            time.sleep(0.2)
        info = root / "door_info.json"
        info.write_text(json.dumps({"handle": args.handle, "user_id": 1, "terminal_width": args.width,
                                    "terminal_height": args.height, "color_depth": args.colour,
                                    "node_name": "playtest", "transport": "local"}), encoding="utf-8")
        trace = root / "auto-trace.jsonl"
        door_env = dict(env, NETBBS_DOOR_INFO=str(info), BLACKSITE_INSTALL_DIR=str(install),
                        BLACKSITE_PRESENTATION="0" if args.view == "shipped" else args.view,
                        BLACKSITE_AUTO_TRACE=str(trace), BLACKSITE_AUTO_INSPECT="1" if args.inspect else "0",
                        BLACKSITE_GLYPH_TIER=args.glyphs)
        command = [sys.executable, "-m", "blacksite.door"] + (["--local"] if os.name == "nt" else [])
        with utf8_console():
            code = subprocess.call(command, env=door_env, cwd=ROOT)
        if trace.exists():
            print(f"Auto decisions: {trace}")
        return code
    finally:
        server.terminate()
        try:
            server.wait(10)
        except subprocess.TimeoutExpired:
            server.kill()
        log.close()


if __name__ == "__main__":
    sys.exit(main())
