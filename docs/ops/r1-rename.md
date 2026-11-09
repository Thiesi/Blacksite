# R1 engineering evidence

Issue #190. Starting base: `7597dce6f1263a27421c51ec97cff1b0b91b6f68`.
Primary/implementing model: Codex (GPT-6). This is a mechanical rename;
the Blacksite remains an in-world installation and its content IDs stay.

## Current state

Draft implementation. Current-head full Linux/Windows CI, native
S04/S05/S10/S11/S24 and the clean-wheel/native title matrix remain
mandatory. The offline persisted-data audit and leftover inventory are
retained beside this note.
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

The eight door title files and, under technical ruling
[6738034888](https://github.com/Thiesi/Karst41/pull/193#issuecomment-6738034888),
the six P5 title files are the only changed goldens. No general golden
update switch was used. `scripts/check_r1_titles.py` compares each P5
file to its original Git object and requires only the title replacement
and its one-cell-shorter fill. Palette, rectangles and every other cell
must match. Its actual output is on the PR. Native evidence covers both
default and P5 at both sizes in all three tiers (twelve cases).

The latest focused checks passed **106 tests**, including the original
mechanics fingerprint and P3 matrix; a separate subprocess/environment
and title-prefix set passed **42 tests**. Both renderers reject incomplete
native title captures.

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
- At `8cb9f6d`, Linux CI had **7 failed, 2546 passed** and Windows had
  **7 failed, 2545 passed, 1 skipped**. Six failures were the P5 title
  goldens subsequently authorized above. The seventh exposed an
  over-renamed canonical level prefix in a test; it is restored below.
  No mechanics/P3 baseline failed or was changed.
- S04 at that head exited before its first title. Its retained node
  registration points at the system Python rather than the clean venv:
  `Path.resolve()` followed the Unix interpreter symlink. The probe now
  uses `Path.absolute()`, as the later native probes already do. No
  timeout or assertion was relaxed. The original failed job is
  [129102964745](https://github.com/Thiesi/Karst41/actions/runs/42600349891/job/129102964745).

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
in S31. Deprecation uses one warning record per process. Operator CLI
use shows it on stderr; the door installs a null handler to keep default
logging out of game output. The Python package, socket and pid have no
legacy alias. The old presentation-trial name survives only as a
configuration-compatibility case and in historical proof context; no
retired presentation behavior is reintroduced.

## Canon and historical scope audit

The complete changed-line audit for `blacksite-` and `Blacksite` found
one incorrect place use: `tests/lattice/test_content.py` must exclude
the unchanged `blacksite-` sector prefix. That test filter is restored.
S26, `blacksite-l1`, `art-blacksite-l1`, Outworks, the maintenance drone
and the content/lore bytes remain unchanged. Existing Python canonical
literal bindings are preserved; no function/class named for the old
brand was present to confuse a place name with a package rename.

The banner link again names the existing image. Nine older evidence
notes (P2, P3, P5, P6a, P6 engine follow-up, P1 verification, both S25b
notes and S40 measurements) are restored byte for byte to the base.
Their commands and URLs describe their original revisions. Living
operator guides, upstream contracts and workflow labels use the new
game name. No art, map, lore or historical capture is rewritten.

The 1,258-file protected-byte audit allows exactly fourteen title
goldens plus this slice's status metadata, and found no other changes.
The compressed [leftover inventory](captures/r1/leftovers.json.gz)
lists every exact `git grep -n -i blacksite` result by path and line,
with a category, reason, matching-line hash and bounded excerpt. Its
four groups are place (canon), historical evidence, S31 fallback and
redirecting URL. It includes binary capture hits. New runtime imports
and launch paths have no old-package alias.

## Persisted-data proof

The [pre-rename world audit](captures/r1/legacy-world-audit.json) uses a
wheel built at `7597dce`, installed into a separate clean venv, and the
unmodified S42 acceptance driver from that revision. The actual NetBBS
native run passed at 80x24/16. After the service closed, a read-only
SQLite scan checked schema, all text/BLOB values and JSON keys/type
tags: **13 tables, 38 rows, 120 text values, 40 JSON values, no BLOBs,
no findings**. It never executes a pickle. No migration is required.
Wheel and native-result provenance are retained in that audit record.
This is synthetic acceptance data, not an existing operator deployment.

The first R1 clean-wheel native run at `8cb9f6d` also passed at
80x24/16, with no old package import available. Its fresh-world audit
had 13 tables, 32 rows, 108 text values, 34 JSON values and no findings.
That is first-head evidence; the twelve-case CI matrix supplies the
source-matched final-head captures and fresh-world audits.
