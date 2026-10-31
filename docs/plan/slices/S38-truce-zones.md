# S38 — Truce zones: Sodium Row keeps the peace

**Status:** planned (approved by the owner 2026-10-31)
**Primary model:** Codex · **Reviewer:** automated review, technical lead, presentation lead (wording and header)
**Depends on:** S11, S20, #126 (P6b; it also edits `sodium-row.json`, so S38 starts after #126 merges) · **Milestone:** world rules
**Issue:** https://github.com/Thiesi/Blacksite/issues/142

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
- **The keeper answers whoever breaks the peace** (`NpcEngine.provoked`).
  Today an attack on a player provokes no NPC, and an attack on an NPC
  alerts only that NPC's own faction's guards. In a truce zone, an
  attack whose target is in the zone breaks the peace when:
  - it is an attack on a player and `would_mark` is true for it; or
  - it is an attack on an NPC that was not already hostile to the
    attacker (no provocation or hunt against them).
  Breaking the peace provokes every guard-behaviour NPC of the keeper
  faction in the zone against the responsible player (a drone's
  controller) for the usual five minutes, besides today's provocation
  of the attacked NPC's group and same-faction guards. Firing back at a
  Marked player, or at an NPC already after you, provokes no keeper.
- **Marking** (`CombatEngine.would_mark`). When the target's body is
  in a truce zone, the hostile-relation exemption does not apply: an
  eligible attack on a player who is not already Marked Marks the
  attacker, wherever the attacker, drone or burn comes from. Crew
  friendly fire and grade protection are unchanged. A target outside a
  truce zone follows today's rules exactly.
- **Presentation** (both presentations until P10):
  - Frame header in a truce zone: `CONTESTED─TRUCE─PvP G5+`.
  - Place card and first-arrival line: "Sable keeps the peace here." /
    "Nobody draws on Sodium Row. Sable makes sure of it."
  - The TARGET panel's warning: on a player target, the existing
    "Firing marks you", driven by `would_mark` (so hostile-faction
    targets show it too); on an NPC target whose attack would provoke
    the keeper's guards, "Truce: <keeper> answers" (Sable: 20
    columns). When it would exceed the panel's 21 columns, drop the
    "Truce: " prefix; a golden covers the longest faction name.
  - The warning follows the target, like the Mark: it shows for a
    target in a truce zone whatever zone the attacker is in. Both fit the 80x24 panel's
    21 columns.
  - The place card shows "CONTESTED · TRUCE".
  - After firing: "You break <zone name>'s truce. You are Marked for 15
    min." (the zone's name, not a hard-coded "the Row").
  - Whenever a truce attack provokes the keeper's guards, the attacker's
    log shows the danger line "<Keeper> is coming for you." ("Sable is
    coming for you." on the Row; the keeper's name comes from the
    zone), so an attack on an NPC, which has no Mark line, is readable
    too. When the attack also Marks, the Mark line comes first, then
    this one.
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
  attacker; firing back at a Marked attacker does not Mark the victim
  and provokes no enforcer, and neither does a bystander shooting the
  Marked attacker.
- Returning fire at an NPC already hunting you on the Row provokes no
  keeper.
- The body rule: a drone or burn from outside at a target on the Row
  Marks and provokes against the controller; an attack from the Row at
  a target outside follows the target zone's rules.
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
