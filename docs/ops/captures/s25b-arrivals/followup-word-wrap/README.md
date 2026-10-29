# Corrected live arrival captures

Clean source/capture head: `5fdce87439f17e69e14a96a2cd32e4dc8339fa88`.

This follow-up implements presentation verdict 6496637951 and technical
endorsement 6496649189. Only the two requested replacement screens are
archived, in 16 colours as permitted by the lead. The real native run
also passes the other two arrival cases. All four observations are in
`result.json`; no additional screen payload is claimed as archived.

NetBBS Telnet -> registered native stdio, installed source-matched wheel,
real character-creation keys and walked exits. The generated overlay and
private shortcut remain explicitly labelled. No screen is composed.

| Scenario | Size | Whole paragraph | Received evidence |
|---|---|---|---|
| wake-hall | 132x50 | visible | [text](shipped/arrival-wake-hall-132x50-16.txt) / [ansi](shipped/arrival-wake-hall-132x50-16.ans) / [context](shipped/arrival-wake-hall-132x50-16.json) |
| under-service | 80x24 | visible | [text](generated/arrival-under-service-80x24-16.txt) / [ansi](generated/arrival-under-service-80x24-16.ans) / [context](generated/arrival-under-service-80x24-16.json) |

Service Level waits for the durable discovery XP receipt before capture.
The paragraph follows the location notice in the immediate arrival
emission. XP may log later, after storage commits; the paragraph and
that notice fit together in the three-row pane. Reward durability is
unchanged. Wake Hall now wraps at a space rather than `corrido / r`.

Validation: 35 focused tests; 307 door/presentation tests with explicit
golden regeneration; clean-head strict packet 99/99 with zero authored
CP437 failures. The two Wake Hall glyph goldens and their six style
goldens change only inside the log rectangle. Mechanics are byte-identical.

See `golden-audit.json`, `strict-packet-summary.json` and `manifest.json`.
The manifest pins every copied payload by SHA-256. The earlier local
full-suite and timing failures stay in the historical evidence; no new
local full-suite, performance or human-layout pass is claimed.
