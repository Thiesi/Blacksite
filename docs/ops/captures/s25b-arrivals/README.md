# Live S25b arrival evidence

Clean execution head: `debc51416632de57025271a0f6a2442d8e61d782`.

Received from a registered NetBBS native stdio door over Telnet. The hub
uses shipped content; Service Level uses the labelled 34-zone overlay
and a walked shortcut. Nothing is placed into the terminal by the probe.

Focused acceptance: 66 passed. Strict packet: 99/99.

Neither local full-suite attempt is green: each has 1,677 passed, one
failed and one skipped. The OneDrive run hit a content-directory rename
error; the system-temp run hit a ten-second CLI shutdown wait. Both
failed cases pass isolated rechecks. The manifest retains both attempts;
the current-head hosted Linux/Windows checks remain required.

See [the playable scenario](../../s25b-arrival-captures.md) for fixtures
and interpretation. The original clipped screens are preserved.
The manifest pins every archived capture file by SHA-256.

| Scenario | Size | Tier | Full paragraph visible | Captures |
|---|---|---|---|---|
| wake-hall | 80x24 | 16 | True | [text](16/shipped/arrival-wake-hall-80x24-16.txt) / [ansi](16/shipped/arrival-wake-hall-80x24-16.ans) / [context](16/shipped/arrival-wake-hall-80x24-16.json) |
| wake-hall | 132x50 | 16 | True | [text](16/shipped/arrival-wake-hall-132x50-16.txt) / [ansi](16/shipped/arrival-wake-hall-132x50-16.ans) / [context](16/shipped/arrival-wake-hall-132x50-16.json) |
| under-service | 80x24 | 16 | False | [text](16/generated/arrival-under-service-80x24-16.txt) / [ansi](16/generated/arrival-under-service-80x24-16.ans) / [context](16/generated/arrival-under-service-80x24-16.json) / [scrollback](16/generated/arrival-under-service-80x24-16-scrollback.txt) |
| under-service | 132x50 | 16 | True | [text](16/generated/arrival-under-service-132x50-16.txt) / [ansi](16/generated/arrival-under-service-132x50-16.ans) / [context](16/generated/arrival-under-service-132x50-16.json) |
| wake-hall | 80x24 | 256 | True | [text](256/shipped/arrival-wake-hall-80x24-256.txt) / [ansi](256/shipped/arrival-wake-hall-80x24-256.ans) / [context](256/shipped/arrival-wake-hall-80x24-256.json) |
| wake-hall | 132x50 | 256 | True | [text](256/shipped/arrival-wake-hall-132x50-256.txt) / [ansi](256/shipped/arrival-wake-hall-132x50-256.ans) / [context](256/shipped/arrival-wake-hall-132x50-256.json) |
| under-service | 80x24 | 256 | False | [text](256/generated/arrival-under-service-80x24-256.txt) / [ansi](256/generated/arrival-under-service-80x24-256.ans) / [context](256/generated/arrival-under-service-80x24-256.json) / [scrollback](256/generated/arrival-under-service-80x24-256-scrollback.txt) |
| under-service | 132x50 | 256 | True | [text](256/generated/arrival-under-service-132x50-256.txt) / [ansi](256/generated/arrival-under-service-132x50-256.ans) / [context](256/generated/arrival-under-service-132x50-256.json) |
| wake-hall | 80x24 | truecolor | True | [text](truecolor/shipped/arrival-wake-hall-80x24-truecolor.txt) / [ansi](truecolor/shipped/arrival-wake-hall-80x24-truecolor.ans) / [context](truecolor/shipped/arrival-wake-hall-80x24-truecolor.json) |
| wake-hall | 132x50 | truecolor | True | [text](truecolor/shipped/arrival-wake-hall-132x50-truecolor.txt) / [ansi](truecolor/shipped/arrival-wake-hall-132x50-truecolor.ans) / [context](truecolor/shipped/arrival-wake-hall-132x50-truecolor.json) |
| under-service | 80x24 | truecolor | False | [text](truecolor/generated/arrival-under-service-80x24-truecolor.txt) / [ansi](truecolor/generated/arrival-under-service-80x24-truecolor.ans) / [context](truecolor/generated/arrival-under-service-80x24-truecolor.json) / [scrollback](truecolor/generated/arrival-under-service-80x24-truecolor-scrollback.txt) |
| under-service | 132x50 | truecolor | True | [text](truecolor/generated/arrival-under-service-132x50-truecolor.txt) / [ansi](truecolor/generated/arrival-under-service-132x50-truecolor.ans) / [context](truecolor/generated/arrival-under-service-132x50-truecolor.json) |

All arrivals came first in the observed log window. At 80x24, the
Service Level arrival/XP notices push the first paragraph line above
the visible log; the real Ctrl-P capture recovers it. The 132x50 Wake
Hall capture also shows the existing cell-width wrap splitting a word.
The 80x24 scrollback splits words too, including `lig / ht` and
`invit / e`. `Arrival界80` is the deliberately wide-character fixture
name shown in the status panel, not an added placeholder.
These are P4/P5 observations, not hidden or re-rendered corrections.

No human layout gate or performance gate is granted by these captures.
