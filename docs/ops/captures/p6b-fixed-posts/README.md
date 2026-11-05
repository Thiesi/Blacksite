# P6b fixed-post evidence, 2026-10-31

Execution: `f52716e8011ad5d883a4b448af305cdc1f911142`.
Runtime/content tree: `74a116c05cc108491edf4dff42783a8fb1ccc916`.
Author's fixed-post data: `f69541473704f1164cd5b5e8dbd315c2fa811504`.
[Hosted run](https://github.com/Thiesi/Blacksite/actions/runs/41217130067).
The later execution commit only updates B3's content validation pin.

All five NetBBS 7.45.0 Telnet/native-stdio walks pass: 80x24 and 132x50
in 16/256, plus 132x50 truecolor. All 25 ANSI captures independently
replay to identical glyphs/styles; 22 original texts are committed.
Attached PTYs, matched wheels, ordinary creation and movement/E/J/B;
no teleport or local handle override. Raw streams/styles and key traces
remain in the eight hashed artifacts linked by `manifest.json`.

All 27 B2 cases pass 16 KiB deltas and 100 ms render p95. Maximum looks
deltas: Plaza 2412, Clinic 2121, Sodium 3163 bytes; worst render p95
across both arms is 35.261188 ms. CPU remains a separate recorded verdict:

| Zone | Max CPU s/h | Misses of 120 | Cases >=108 |
|---|---:|---:|---:|
| Plaza | 126.7356 | 2 | 6 |
| Clinic | 130.0968 | 3 | 6 |
| Sodium | 102.0943 | 0 | 0 |

Every verdict, nine matched origin controls and 36 cold/warm phases
remain in `performance.json`. These timings do not establish content
causation or host-noise attribution. CPU misses are nonblocking for P6b
per the lead; A8 is queued. No numeric pass or threshold waiver is claimed.

`generic-work.json` counts work, not CPU: at the original P5 Sodium pose,
old/A7 generic writes are 117270/168000 (+43.26%), both 40 moves/56 draws.
Reproduce all 12 cases with `scripts/presentation_p6b_work.py --route both`.
This isolates origin/clipping work, not historical P5's entire mixture.

B3 retains six exact candidates against merged A7 and no further
fingerprint move. Linux CI: 2175 passed; Windows: 2174 passed, one skip.
Both older packets remain historical, with their original source pins.
The added fresh packet needs an evidence-size exception in technical review.

Presentation sign-off is recorded separately at f695414. H1, fingerprint
approval and S25 human layout approval remain NOT GRANTED.
