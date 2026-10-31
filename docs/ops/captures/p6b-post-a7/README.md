# P6b post-A7 engineering evidence, 2026-10-31

Execution: `c8fff45814f168dceab8be48c7ba1338d1c9d63d`.
Source Git tree: `4dc3fb3cf84228c40d31197326e8677c0422e8d2`.
[Hosted run](https://github.com/Thiesi/Blacksite/actions/runs/41209461618).
A7 was owner-merged as `54adc53`; the branch merged main normally.
Authored data remains pinned to `0c4b19d`, unchanged.

All five NetBBS 7.45.0 Telnet/native-stdio configurations passed: both
sizes in 16/256 colours, plus 132x50 truecolor. All 25 genuine ANSI
captures replay to identical glyphs/styles; 22 original texts are kept.
Sized attached PTYs, matched wheels, ordinary creation/keys, no teleports
or local handle override. Raw ANSI/styles and key traces stay in the
eight linked, hashed artifacts in `manifest.json`.

All 27 B2 cases pass 16 KiB deltas and 100 ms render p95. Max looks delta is
2514 / 2021 / 3059 bytes (Plaza/Clinic/Sodium); worst render p95 is
28.749936 ms. CPU is separate:

| Zone | Max CPU s/h | Finding |
|---|---:|---|
| Plaza | 112.1959 | two cases at or above 108 |
| Clinic | 106.0726 | under 120 |
| Sodium | 145.5824 | six misses of 120 |

`performance.json` retains every verdict, nine matched origin controls
and 36 cold/warm phases. Full raw reports are linked/hashed. Clinic's
cold reveal-driven cache replacements remain a nonblocking finding.
Job success grants no CPU acceptance; Sodium needs a technical decision.

`generic-work.json` records deterministic counts, not local timings.
At the original P5 Sodium pose, generic terrain writes rise from 111450
to 159000 with only origin changed: 42.66%, with 40 moves/53 draws in
each arm. Central B2 lanes have little or no clipping difference.
Reproduce with `scripts/presentation_p6b_work.py`. This isolates work,
not the entire historical P5 hourly mixture.

B3 freezes six zone candidates against merged A7; every other golden
is unchanged. Only three charted/public fingerprint entries move.
Root suites: 2169 Linux; 2168 Windows plus one skip.
The earlier pre-A7 packet is preserved in `../p6b-shipped-places/`.

H1, fingerprint approval, P6b sign-off and S25 human layout approval
remain NOT GRANTED. Guard/patrol placement questions remain open.
