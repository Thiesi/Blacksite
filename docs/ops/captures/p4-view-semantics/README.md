# P4 acceptance evidence

Historical evidence below predates the owner-merged S25b integration.
It does not validate the current head. Fresh evidence will replace this
packet after the cover-name and complete-paragraph checks finish.

Source head: `7b4833f250210548629b9985fe0c1a6c6504e9dc`.
Base: `cae334f92386d2f70e94b3d6816ea2dd0f34026e`.

[Hosted P4 run](https://github.com/Thiesi/Blacksite/actions/runs/40913607689)
passed all six native cases: 80x24 and 132x50, each in 16, 256 and
truecolor, with wide caller names. The 18 text captures here come from
that run's received native-door streams. No screen is composed manually.

GitHub checked out synthetic merge commit
`cd6ce9a60e1004dcaab246149db46a3d46c0ae36`. Its complete Git tree is
verified identical to the source head. The native CI receipts retain
that actual execution SHA; `manifest.json` records both identities.

For each size and colour tier:

| Capture | Scenario |
|---|---|
| `wake-*` | Ordinary new character in Wake Hall, with place history. |
| `place-history-*` | Ctrl-P scrollback displays the first-entry sentence. |
| `lattice-*` | Walk, explicitly skip training, reach the tutorial terminal and jack in. |

The manifest hashes every text capture and its raw ANSI/style JSON
counterparts. Raw files remain in the exact named artifacts, not Git:

Text retains every captured cell, including the reserved final corner.
Folder attributes preserve those bytes and the original small receipts.

- [80x24 artifact](https://github.com/Thiesi/Blacksite/actions/runs/40913607689/artifacts/12914388024)
- [132x50 artifact](https://github.com/Thiesi/Blacksite/actions/runs/40913607689/artifacts/12914697903)

The independent local run also passed all six cases through a real
NetBBS node, with received 16-colour ANSI forwarded to a terminal. Its
small receipts describe the local run, not the hosted capture bytes.
The installed wheel matched source Python tree
`9d8b2ae4d480feaf8c52912b71bae41e8a31b1be208eefd22bdcd55e76b4b501`.
The local node was observed after execution as NetBBS 7.41.0 / door API
5 at dirty checkout `15f1605f80bb2235989f40accec3ab46f1cc3cae`.
Hosted acceptance uses clean pinned NetBBS v7.31.0.

`pytest.json` records the clean source-head full root run: 1,651 passed,
1 skipped. The strict packet passed 99 cases with zero authored CP437
failures. `preservation.json` names the only eight changed baseline
files: two Wake Hall glyph snapshots and their six style companions,
solely for the required place sentence. Mechanics remain byte-identical.

`review-triage.json` records the production-hook reproduction of the
automated review's combat-name finding. A protected plaza blocks fire;
a legal shot invokes retaliation targeting and records its per-caller
reveal before the Hit/Miss label. Another caller keeps the cover. The
permanent regression is
`test_arch_5_5_4_retaliation_reveals_before_hit_or_miss_log` in
`tests/presentation/test_view_semantics.py`. Together with the existing
chat/disclosure tests, the post-review focused run passes 35 cases.
Production code, the native harness and all goldens are unchanged by
this evidence and regression-test follow-up; final-head CI remains
required.

These receipts grant no human layout, content, pacing or performance
approval. Raw worlds, node databases and authentication files are absent.
