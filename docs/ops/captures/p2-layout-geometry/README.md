# P2 verification evidence

Clean runtime/acceptance head: `0203051ea3f1b36cf1faf3ec5f985002325d9b4d`.

Full root pytest: **1650 passed, 1 skipped**.
Strict packet: **99/99**, zero authored CP437 failures. No rebaseline.
The entire glyph/style golden tree and the mechanics blob match the
base exactly; `golden-identity.json` records their Git object IDs.

An initial root run exposed seven City Map page-index collisions.
That implementation defect was corrected before the clean final gate;
no test, timeout, glyph baseline or mechanics baseline was weakened.

## Real native game

NetBBS Telnet -> registered native stdio with a source-matched wheel.
Normal wide-name character creation, inventory page keys, help page 2,
scrollback and clean exit run at both sizes in 16 colours. No placement,
funding, rule or clock fixtures. These are received screens, not composed
frames. The wider full native matrix remains a separate hosted gate.

| Size | Scene | Received evidence |
|---|---|---|
| 80x24 | wake | [txt](native-wide/wake-80x24.txt) / [ans](native-wide/wake-80x24.ans) / [json](native-wide/wake-80x24.json) |
| 80x24 | inventory | [txt](native-wide/inventory-80x24.txt) / [ans](native-wide/inventory-80x24.ans) / [json](native-wide/inventory-80x24.json) |
| 80x24 | help | [txt](native-wide/help-80x24.txt) / [ans](native-wide/help-80x24.ans) / [json](native-wide/help-80x24.json) |
| 80x24 | scrollback | [txt](native-wide/scrollback-80x24.txt) / [ans](native-wide/scrollback-80x24.ans) / [json](native-wide/scrollback-80x24.json) |
| 132x50 | wake | [txt](native-wide/wake-132x50.txt) / [ans](native-wide/wake-132x50.ans) / [json](native-wide/wake-132x50.json) |
| 132x50 | inventory | [txt](native-wide/inventory-132x50.txt) / [ans](native-wide/inventory-132x50.ans) / [json](native-wide/inventory-132x50.json) |
| 132x50 | help | [txt](native-wide/help-132x50.txt) / [ans](native-wide/help-132x50.ans) / [json](native-wide/help-132x50.json) |
| 132x50 | scrollback | [txt](native-wide/scrollback-132x50.txt) / [ans](native-wide/scrollback-132x50.ans) / [json](native-wide/scrollback-132x50.json) |

## Transport fixture

The existing S04 service fixture disables characters. Its Telnet, SSH
and WebSocket cases pass at both sizes, including picker/help/escape,
clean return to the node and the real service-loss countdown. Its raw
transcripts and provenance are under `native-transports/`.

Only selected screen payloads and test/provenance receipts are copied.
The manifest pins every payload by SHA-256. No private node/world
database, secret, performance pass or human-layout approval is included.
