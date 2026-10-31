# A6 validation and native fixture evidence

Execution head: `7752508a684623ad91b58cc2ba88fcc121897a1c`.
Pinned runtime Git tree: `d72d9e3bb64388c8a461348590355e4f38e69182`.
The publishing commit changes evidence, the slice Status line and a
P5 scope clarification only; the captured runtime remains identical.

## Validation proof

`validation-windows.json` records three CPU samples per phase and case
on Windows/Python 3.12. Loading/I/O is excluded, as in the existing
S25b TR-8 gate. These are validation timings, separate from door CPU.

| Loaded input | Before median | Final median | Final maximum |
|---|---:|---:|---:|
| Shipped | 0.250 s | 0.234 s | 0.250 s |
| Shipped plus pinned #126 | 11.156 s | 1.563 s | 1.641 s |
| That input plus P6 light fixture | 12.438 s | 1.656 s | 1.719 s |

The baseline is merged A5 `c2f990312d1c6cf88200f56dc4722fe83f9f7321`.
The JSON/map-only input is #126 at
`3e585c71eebf8c8cd19a591016dfe78a788c5b9b`, with each copied file hash
recorded. No source code from that content branch is executed.

Every cache-only diagnostic matches its baseline, in the same order.
On the #126 case, palette conversions fall from 1,359 to one, and
Paint constructions from 1,359 to nine. The final sign policy removes
the twelve intended light-fixture ground-band errors; all final cases
validate clean below the existing three-second limit. The report pins
both changed runtime files by SHA-256. Reproduce the method with
`scripts/presentation_p6_validation.py`; its trusted baseline modules,
cache-only phase and boundaries are documented in `p6-a6-validation.md`.
The CI version repeats the proof separately; this file claims only
the completed Windows run.

## Native captures and frozen output

Run [41185424009](https://github.com/Thiesi/Blacksite/actions/runs/41185424009)
supplies four individually linked artifacts in `manifest.json`.
All twelve native cases passed: 80x24/132x50, all tiers, dark/light,
NetBBS v7.45.0 Telnet to registered stdio with isolated source-matched
wheels and sized attached PTYs. The verifier independently ties each
native Python digest to the Git tree above. All 48 streams replayed
with matching glyphs and rendition; 28 selected text files are kept
byte for byte. Raw ANSI and full style snapshots stay in the artifacts.

The unchanged A5 scenario starts explicitly at `(4,5)`. The existing
gate `(20,5)` is added only to the service-local fixture public region;
it starts unseen and unremembered, as `-3` ground with no rule glyph or
void style. Ordinary keys walk to `(5,5)` for cover and `(9,5)` to
reveal the Clinic terminal. The four checkpoints are charted/HERE,
authored cover, region/HERE and the explicit server notice. This is a
fixture walk, not Part B's shipped-place journey.

`per-cell-proof.json` reports zero existing golden changes. Its named
Clinic `(10,5)` map correction is historical Part A context; A6 changes
no committed fixture or shipped data. Historical packets are unchanged.

To replay, download the four `p6-fixture-*` artifacts into named
directories, save their metadata, and run:

```text
python scripts/presentation_p6_packet.py --artifacts-root <downloads>
  --metadata <artifacts.json> --run 41185424009
  --head 7752508a684623ad91b58cc2ba88fcc121897a1c
  --source-tree d72d9e3bb64388c8a461348590355e4f38e69182
  --output <new-packet-directory>
```

The packet grants no technical, presentation or human acceptance.
H1, P6b fingerprint approval and S25 human layout approval remain
NOT GRANTED. Part B follows A6's merge.
