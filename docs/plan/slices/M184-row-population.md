# M184: Row population measurement

Status: in progress (PR #186, issue #184; matched controls requested).
Primary model: Codex. Review: automated Claude, then technical lead.
Base: owner-merged main 5416b5d; A8, A9 and S39 are merged.

The brief is [issue #184](https://github.com/Thiesi/Blacksite/issues/184).
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
