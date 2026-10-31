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

- **Data.** `ZoneMeta.truce`: the keeper faction id, or null (the
  default). The validator rejects it on any class other than contested
  and requires a known faction. `sodium-row.json` sets `"sable"`.
- **NPC hostility** (`NpcEngine.hostile`). In a truce zone the relations
  matrix and `hostile_all` never make an NPC hostile. Provocation still
  does (the spawner group and same-faction local guards, five minutes),
  and Wardens still engage Marked players and players with Warden heat.
  Outside truce zones nothing changes.
- **The keeper answers every attack** (`NpcEngine.provoked`). Today an
  attack on a player provokes no NPC, and an attack on an NPC alerts
  only that NPC's own faction's guards. In a truce zone, any eligible
  attack, on a player or on an NPC of any faction, also provokes every
  guard-behaviour NPC of the keeper faction in the zone against the
  attacker (and a drone's controller) for the usual five minutes, so
  the enforcers answer whoever breaks the peace.
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
  - The TARGET panel's warning: on a player target, the existing
    "Firing marks you", driven by `would_mark` (so hostile-faction
    targets show it too); on an NPC target whose attack would provoke
    the keeper's guards, "Truce: <keeper> answers" (Sable: 20
    columns). Both fit the 80x24 panel's
    21 columns.
  - The place card shows "CONTESTED · TRUCE".
  - After firing: "You break <zone name>'s truce. You are Marked for 15
    min." (the zone's name, not a hard-coded "the Row").
  - Whenever a truce attack provokes the keeper's guards, the attacker's
    log reads "<Keeper>'s enforcers turn on you." ("Sable's enforcers
    turn on you." on the Row), so an attack on an NPC, which has no
    Mark line, is readable too.
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
- On the Row, an eligible attack on a player, on a Sable NPC and on a
  non-Sable NPC (a regular, a plainclothes Warden) each provokes the
  enforcers. Outside a truce zone, an attack on a player still provokes
  no NPC, and an NPC attack alerts only its own faction's guards.
- An eligible attack on a hostile-faction player on the Row Marks the
  attacker; firing back at a Marked attacker does not Mark the victim.
- Grade protection below 5, crew friendly fire and open zones are
  unchanged; a remote or drone attack into or out of the Row follows
  the body rule.
- The validator rejects `truce` on safe, pocket and open zones, and an
  unknown keeper faction.
- Header, warning and log goldens at 80x24 and 132x50.

## Definition of done

Roadmap §7, plus: the mechanics fingerprint moves only for the truce
rule and the flag, reported per zone; the owner's approval of this slice
covers that move. The presentation lead signs off the wording and the
header.
