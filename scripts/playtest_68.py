"""Play the proposal 68 presentation in this terminal (issue #68 playtest).

    python scripts/playtest_68.py                      # shipped maps
    python scripts/playtest_68.py --geometry candidate # Sodium Row candidate map
    python scripts/playtest_68.py --colour 16          # try another tier

Starts a private foreground service under `.test-tmp/playtest-68-*` with
the trial switches on (charted public geography, ambient lines), then
runs the real door in this console with the proposal renderer selected.
The world persists between runs, so your Wake is still there next time;
`--fresh` starts over.

In play: F7 switches between the shipped and the proposal renderer on the
same game state. F5 shows the place card, F6 cycles when cards appear.
Ctrl-X then Y leaves and stops the service.

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
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "docs/design/proposals/68-presentation/candidates/sodium-row"


def main() -> int:
    size = shutil.get_terminal_size((80, 24))
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--geometry", choices=("shipped", "candidate"), default="shipped")
    parser.add_argument("--colour", choices=("truecolor", "256", "16"), default="256")
    parser.add_argument("--width", type=int, default=max(80, size.columns))
    parser.add_argument("--height", type=int, default=max(24, size.lines))
    parser.add_argument("--handle", default="Playtester")
    parser.add_argument("--fresh", action="store_true", help="delete this playtest world first")
    parser.add_argument("--shipped-renderer", action="store_true", help="start on the shipped renderer (F7 switches)")
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
        door_env = dict(env, NETBBS_DOOR_INFO=str(info), BLACKSITE_INSTALL_DIR=str(install),
                        BLACKSITE_PRESENTATION="0" if args.shipped_renderer else "1")
        command = [sys.executable, "-m", "blacksite.door"] + (["--local"] if os.name == "nt" else [])
        return subprocess.call(command, env=door_env, cwd=ROOT)
    finally:
        server.terminate()
        try:
            server.wait(10)
        except subprocess.TimeoutExpired:
            server.kill()
        log.close()


if __name__ == "__main__":
    sys.exit(main())
