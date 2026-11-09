# R1 engineering evidence

Issue #190. Starting base: `7597dce6f1263a27421c51ec97cff1b0b91b6f68`.
Primary/implementing model: Codex (GPT-6). This is a mechanical rename;
the Blacksite remains an in-world installation and its content IDs stay.

## Current state

Draft implementation. Full Linux/Windows CI, native S04/S05/S10/S11/S24,
the clean-wheel/native title matrix, the real persisted-data audit and
the complete leftover-hit inventory remain mandatory and pending.
Presentation acceptance, technical review and the owner's merge are
pending. H1 and S25 layout approval remain NOT GRANTED.

## Observed focused validation

- Before and after the package move, the existing mechanics-baseline
  check and the real 10,704-case P3 interaction matrix passed: **2 passed**
  each time. No frozen value was rebaselined.
- Environment fallback precedence, once-per-process logging, scratch,
  title rendering, title-independent introduction action and admin CLI:
  **66 passed, 2 skipped** (Windows symlink permissions).
- Historical proof readers, source identity, content pins, origin
  controls, profile and fail-closed scope selection: **33 passed**.
- Title-prefix integrity and offline database-audit fixtures: **7 passed**.
- All three P6 validation datasets passed all three phases, with zero
  final errors. Maximum final CPU was **0.21875 seconds**, below the
  unchanged 3-second gate. This local one-repeat comparison does not
  replace the complete CI performance proof.

Only `tests/door/golden/title_*` and their six colour-style files were
regenerated, as R1 explicitly requires. No general golden-update switch
was used. The unchanged tagline and other screen geometry remain.

## Failures retained

- The initial frozen-test command named a nonexistent matrix test node:
  no tests ran. The corrected selection passed both existing checks.
- The first environment/admin/scratch run had **49 passed, 1 failed,
  2 skipped**. Renaming the prefix changed a fixture's alphabetical
  order; its expected sorted list was corrected without changing the
  cleanup assertion or behavior.
- The first historical-reader run had **30 passed, 3 failed**. Its
  independent Git-fixture checkouts exposed a resolver using the main
  repository instead of the caller's root. The resolver now receives
  that root explicitly; all 33 checks passed.

Original outputs are retained in the adjacent R1 capture/validation
directory. A failed run is never relabelled as successful.

## Historical proof boundary

`source_layout.py` resolves the package directory actually present at a
trusted Git revision. Pinned bytes and capture hashes are not rewritten.
Trusted old Python is compiled with only its package identifiers mapped
to the current namespace; strings and data remain unchanged. The P6
content snapshot diffs subtree objects, so the directory move itself
cannot become a content edit.

The A8 workflow still runs its exact pinned pre-R1 checkout. Its content
diff must therefore retain that checkout's old package path: changing
it to the new path would silently skip content. This is historical
evidence, not an import shim or an exemption from current-head checks.

## Configuration compatibility

New names take precedence over all old aliases, with `DOOR_*` priority
within each generation. Empty new values are set and do not revive old
values. Aliases and old scratch-prefix counting are marked for removal
in S31. Deprecation uses the opt-in INFO logger once per process, never
the game's terminal output. The Python package, socket and pid have no
legacy alias. The old presentation-trial name survives only as a
configuration-compatibility case and in historical proof context; no
retired presentation behavior is reintroduced.
