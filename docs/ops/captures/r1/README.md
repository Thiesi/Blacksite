# R1 capture and validation packet

The changed screen is the ordinary launch title. Start the service
separately, register the installed-wheel interpreter as a NetBBS native
stdio door with `-m karst41.door`, and select Karst 41 in the picker.
The title must read **KARST 41**, retain the city introduction and the
existing tagline, and then continue through ordinary character entry.
`?`, `I` and the leave keys retain their existing actions.

Repeat at 80x24 and 132x50 in 16, 256 and truecolor, first with
`DOOR_KARST41_PRESENTATION=0`, then with it set to `1` for P5.
The automated driver negotiates those real terminal capabilities through
NetBBS Telnet and its registered native stdio child. It extracts the
last complete title repaint from the original received stream before
the Wake. It substitutes no renderer, message, pause or view.

`scripts/packet_r1.py` verifies all twelve named CI artifacts, their run
and head, the wheel's Python source hash, every capture SHA-256 and the
offline world audit. It replays each untouched ANSI stream and compares
all glyphs and styles to the captured snapshot. The small text files and
manifest are retained here; raw ANSI and large style JSON stay in the
linked CI artifacts. A new title proof is never composed from goldens.

`local-title-summary.json` records a separate twelve-case Windows run
from a clean venv and wheel. It is supplementary engineering evidence;
the final capture packet uses retained hosted artifacts rather than
temporary local storage. `legacy-world-audit.json` records the real
pre-rename acceptance database and its wheel/native provenance.

The validation directory retains the original failed local commands.
The engineering ledger records corrected runs and the first failed CI
head separately. `scope-audit.json` records the protected-byte and canon
audit. `leftovers.json.gz` gives a category and reason for every remaining
old-name search result, including binary capture hits.

No script, test or capture grants presentation acceptance, H1 approval
or S25 layout approval. The presentation lead accepts the title screen;
the owner merges this slice.
