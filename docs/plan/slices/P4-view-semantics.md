# P4 — View semantics

**Status:** planned
**Primary model:** Sonnet · **Reviewer:** automated review, technical lead
**Depends on:** P0, P1 · **Milestone:** presentation track
**Issue:** https://github.com/Thiesi/Blacksite/issues/95

From `docs/plan/03-presentation-integration.md` §4 "Extend" and §7.3,
adopted by the owner on 2026-10-28 (D-T1). The canon is architecture
§5.4 (view fields), §5.5.3 (log kinds) and §5.5.4 (disclosure), merged
in P0 (#81).

## Goal

The server sends the place facts it already knows, so later renderers
can draw them. Nothing is drawn differently in this slice.

## Scope

**View fields,** as named in architecture §5.4:

- `objects.role` by object kind.
- `actors.class`: the presented class `caller`, `civilian`, `warden`,
  `security`, `service`, `hostile` or `drone`.
  - It comes from the template's `presents` field, falling back to the
    current faction-derived role.
  - A disguised NPC shows its cover class until it acts against a
    caller. After that, that caller alone sees its true class, for the
    lifetime of that NPC instance (§5.5.4). Keep the reveal with the
    NPC instance on the server, never in content.
- `actors.jacked` as a flag, replacing the cover-2 shape as the signal.
  The glyph change itself waits for the renderer.
- The drone glyph id (`actor-drone`) in the registry.
- `me.district` and `me.pvp` eligibility.
- The relay owner role, from data already present.
- `legend.glyph_modern`, where the registry has a modern glyph (#89's
  `modern` map).

**Log lines:**

- `kind` on every log line, through **one** emit entry point that
  requires a kind (§5.5.3: `place`, `ambient`, `speech`, `danger`,
  `combat`, `system`, `reward`, `notice`).
- Speech lines also carry `speaker` and `speaker_role` (§5.4, §5.5.3).
  `speaker_role` is the speaker's **presented** class, with the same
  per-caller disguise reveal as `actors.class`. It is never the NPC's
  true faction.
- Every existing emitter passes a kind.
- S25b moved the arrival paragraph into the log; P4 tags it `place`.
- The crew restart notice moves off the world log.

**LatticeView:**

- Owner and tier per core cell. Private cores read "private".
- Sector theme id and link labels.
- Black ICE is marked only from the player's own survey state, never
  from the template.

## Out of scope

- Any rendering change.
- Ambient emission, which is P8.
- Looks, scenes, places and `charted`/`lit`/`public` zone data, which
  are later slices. When those zone fields are added, they join the P1
  fingerprint projection.
- `ZoneView.focus`, which is P3.

## Tests

- Every new field is present in zone, Lattice and menu views, at both
  sizes.
- Disclosure:
  - a plainclothes Warden presents as its cover class, and only the
    caller it acted against sees its true class, until the instance
    ends;
  - that NPC's speech lines carry its cover role in `speaker_role`
    until the same reveal;
  - private cores read "private";
  - black ICE is marked only after a survey;
  - nothing outside sight gains a field.
- No emitter bypasses the single entry point, and every line carries a
  kind (a test that scans emitters, or a runtime assertion in tests).
- The mechanics fingerprint is unchanged.
- Glyph and style goldens are unchanged. S25b already moved the arrival
  paragraph into the log and owns that visible rebaseline.

## Acceptance

Automated review and technical review. The full native matrix stays
green, and native acceptance shows no visible change, including S25b's
existing arrival paragraph in the log.
