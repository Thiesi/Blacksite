# M184: Row population measurement

Status: done (PR #186, issue #184; final technical disposition on the PR).
Primary model: Codex. Review: automated Claude, then technical lead.
Base: owner-merged main 5416b5d; A8, A9 and S39 are merged.

The brief is [issue #184](https://github.com/Thiesi/Karst41/issues/184).
This is measurement only. It decides no population and grants no gate.
Do not change shipped content, the engine, the renderer or canon numbers.

Use A8's hosted Linux reference: P1's twelve-second activities, mix,
Display method CPU meter, ten-Hz ticks and five-Hz walking, at 132x50.
Measure 0/20/40/80 stationary extras, 4/8/12 wandering regulars, one/four
callers in a shared world, and all three colour tiers. Ordinary knowledge
is required (72 cells); fully-known corners are additional evidence.
Keep the two Sable posts and the Warden unchanged. Population and legal
visible placement are declared script-only fixtures, never shipping data.

Report every CPU s/h result, per-caller and aggregate door cost, adjacent
stationary/moving marginal costs per caller, and all misses against 108.
Measure shared server ticks separately from caller Display methods. A
separate cheap profile examines NPC evaluation and view production,
including 80 extras. Do not optimize a result here. Do not retry a failed
measurement to get a favorable sample. Record limitations and outcomes.

Heavy work goes to hosted CI. Ring the lead before any heavy local run.
Retain small evidence in `docs/ops/captures/row-population-184/`; keep raw
reports/profiles as exact-head workflow artifacts. Use fixed scratch
folders and delete them, including verification downloads, when finished.

Acceptance: root pytest before opening the PR; fixture/accounting tests;
complete required hosted grid with all misses retained; raw artifact and
source provenance; a readable evidence report; automated-review triage
and an exact-head technical decision record. Measurement failures and
budget misses are findings, not authority to change game behaviour.
H1 and S25 layout approval remain NOT GRANTED. The owner merges.

The first hosted execution at 1ee8bbe records all 72 ordinary cells and
24 known corners, with no retry. Five ordinary cells meet 108. The packet
retains every result, 102 marginal differences and eight separate corner
profiles; stationary extras incur both door and server cost. All activity
cadence/fixture assertions pass. Final-head review and merge requirements
are recorded on #186; this measurement grants no population or human gate.

Technical record 6729363372 accepts the within-runner marginals and asks
for matched A8/current and one/four-caller controls before absolute figures
are used. The predeclared same-runner plan is 6729408184 on #186, with the
exact-snapshot amendment recorded before execution. Retain every arm,
including failures. No optimization is part of this follow-up.

The single control execution at 2cc576f completes all seven arms. Full
old-input manifests and A8/P1 method hashes match. The current A8 ordinary
16-colour eleven-NPC case measures 92.260771 CPU s/h; the dense one-caller
fixture at the same population measures 137.768557. Runtime and data
evolution also increase measured cost. The same-runner four-caller maximum
is higher than one caller for both M8 and M4, so no intrinsic caller
discount is established. All outcomes and limitations are retained in
the packet. The Windows-only expected-path assertion is fixed at b087219;
hosted root passes on both systems. A new-head technical record and owner
merge remain required; this done mark grants no population or human gate.

R1 integration updates current helpers to the `karst41` namespace and
resolves historical content paths at their pinned revision. Archived
measurements, source hashes and captures remain unchanged. Completed
measurement workflows are manual-only; merging main does not repeat the
96-case grid or seven controls. A future explicit control also retains
raw method hashes and checks equivalence apart from R1's declared import,
package-path and scratch-prefix spellings. It grants no new measurement.

The CPU-bound S11 failure at bf1cb84 remains on record. Under the owner's
interim rule (PR comment 6742888669), CI after this merge is the one
permitted rerun for this PR with no runtime changes. A second CPU failure
blocks until S43; no gate, sample or assertion changes are authorised.
