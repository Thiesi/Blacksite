# S38 — Truce zones: Sodium Row keeps the peace

**Status:** planned (approved by the owner 2026-10-31)
**Primary model:** Codex · **Reviewer:** automated review, technical lead, presentation lead (wording and header)
**Depends on:** S11, S20, P6b (#126, which also edits `sodium-row.json`) · **Milestone:** world rules
**Issue:** filed on merge

Canon: game design 5.5 and 7.3, terminal UI 2.1 and entities, all
marked "planned, S38". The gazetteer's Sodium Row entry already describes
the truce. Where this file and canon differ, canon wins.

## Goal

Sodium Row is the one street where rivals drink side by side. Today
the relations matrix makes Sable enforcers fire on Halvard, Kestrel,
Warden and Unmoored members on sight. After this slice, nobody on the
Row is attacked for their faction; whoever starts a fight there is
Marked and answered by the enforcers.

Decided by the owner on 2026-10-31, from the creative consultant's
proposal, with the presentation lead's wording.

## Scope

- **Data.** `ZoneMeta.truce` (bool, default false). The validator
  rejects it on any class other than contested. `sodium-row.json` sets it.
- **NPC hostility** (`NpcEngine.hostile`). In a truce zone the relations
  matrix and `hostile_all` never make an NPC hostile. Provocation still
  does (the spawner group and same-faction local guards, five minutes),
  and Wardens still engage Marked players and players with Warden heat.
  Outside truce zones nothing changes.
- **Marking** (`CombatEngine.would_mark`). When the attacker's or the
  target's body is in a truce zone, the hostile-relation exemption does
  not apply: an eligible attack on a player who is not already Marked
  Marks the attacker. Crew friendly fire, grade protection, open-zone
  and drone or remote rules are unchanged; the drone path checks the
  controller and target bodies as today.
- **Presentation** (both presentations until P10):
  - Frame header in a truce zone: `CONTESTED─TRUCE─PvP G5+`.
  - Place card and first-arrival line: "Sable keeps the peace here." /
    "Nobody draws on Sodium Row. Sable makes sure of it."
  - The TARGET panel's warning, for every eligible target in a truce
    zone: "Truce: firing marks you".
  - After firing: "You break the Row's truce. You are Marked for 15 min."
  - No fire confirmation and no HERE entry.

## Out of scope

- Applying the flag anywhere else. Warmwater's Lamp Street describes the
  same rule; that is Warmwater's Stage 2 decision.
- Standing penalties (none, by decision), the Tin Halo pocket rules,
  open zones, and Lattice controls (pranks there are not attacks).
- Enforcer posts: the creative consultant's follow-up after #126.

## Tests

- A Kestrel, Halvard, Warden or Unmoored player is never targeted by an
  enforcer on Sodium Row; the existing §7.2 test still passes outside it.
- Plainclothes Wardens and enforcers do not engage each other there.
- Attacking a player or NPC on the Row provokes the enforcers as today.
- An eligible attack on a hostile-faction player on the Row Marks the
  attacker; firing back at a Marked attacker does not Mark the victim.
- Grade protection below 5, crew friendly fire and open zones are
  unchanged; a remote or drone attack into or out of the Row follows
  the body rule.
- The validator rejects `truce` on safe, pocket and open zones.
- Header, warning and log goldens at 80x24 and 132x50.

## Definition of done

Roadmap §7, plus: the mechanics fingerprint moves only for the truce
rule and the flag, reported per zone; the owner's approval of this slice
covers that move. The presentation lead signs off the wording and the
header.
