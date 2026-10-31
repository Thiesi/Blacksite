# P6 A6 validation proof

The A6 assignment and constraints are on #115, comment 6540763713.
The implementation starts from merged A5, commit
`c2f990312d1c6cf88200f56dc4722fe83f9f7321`. No shipped data, committed
fixture, golden or mechanics baseline changes. The slice edit is its
Status line only.

## Paired validation measurement

```text
git fetch --no-tags origin 3e585c71eebf8c8cd19a591016dfe78a788c5b9b
python scripts/presentation_p6_validation.py --output <new-report.json>
```

The script reads local Git objects. It copies only JSON/map input from
the pinned #126 head into a temporary copy of shipped content. It also
copies each zone sidecar's unchanged map pair. The content branch is
never checked out or modified; no Python from that branch is executed.
The report lists the input hashes and the two changed runtime hashes.

Three cases use the same loaded tree for every phase: shipped content,
shipped plus the pinned #126 data, and that data plus the P6 light
fixture. Full `validate(tree)` is timed with `process_time`, excluding
loading and I/O, matching the existing S25b TR-8 three-second gate in
`tests/content/test_hub_maps.py`. Three samples are recorded per phase:

- **before:** the original A5 place validator and Paint from the fixed,
  reviewed baseline commit;
- **cache_only:** the new place validator with the original Paint;
- **after:** the new validator and Paint.

The baseline modules are executed from that trusted Git commit inside
the isolated developer tool. The ordinary cross-file validator is the
same in all phases. Instrumentation counts palette conversions and
Paint construction within placement validation; source loading,
serialization and module construction are outside the timer.

Every cache-only diagnostic, including its order, must equal the
baseline. The light fixture provides nonempty baseline diagnostics.
The final sign-policy change may only remove the specified
structure/things ground-floor diagnostics; it may introduce no others.
Final validation must be clean and every sample below the existing
budget. Ordered diagnostic hashes and all CPU samples are reported.
The P6 workflow repeats this proof with the pinned input.

## Sign policy and regression checks

UI 2.2 checks sign-only `thing_sign_*` letters against their wall face.
They do not determine the darkest thing against ground in `bands_on`.
The generic P5 floor and ordinary thing roles are unchanged.

The regression uses a bright sign colour equal to a light ground:
zero ground distance, but readable on the wall. It must validate.
The same sign made equal to its wall must still fail at 256/truecolor;
black lettering on ANSI's forced-black face must fail too. An ordinary
thing at the light ground colour still fails its ground-floor check.
A separate regression mutates and restores the palette between
validations to prove that the cache does not survive a call.

```text
python -m pytest -q tests/presentation/test_places.py
python -m pytest -q tests/content/test_hub_maps.py
python scripts/p6_cell_diff.py --output <new-per-cell-proof.json>
```

Native fixture acceptance remains the existing all-tier dark/light
matrix at 80x24 and 132x50 through NetBBS v7.45.0 Telnet to registered
stdio, including A5's test-service-only public gate face at `(20,5)`.
The source-matched wheel and capture verifier pin the runtime tree.
Those fixtures are engineering evidence, not Part B's shipped walk.

Technical review and presentation sign-off are separate from the
owner's H1, P6b fingerprint approval and S25 human layout approval.
Those human gates remain NOT GRANTED. Part B follows A6's merge.
