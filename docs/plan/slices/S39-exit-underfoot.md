# S39 — Exit underfoot: a door on your tile outranks an adjacent talker

**Status:** planned (approved by the owner 2026-11-04)
**Primary model:** Codex · **Reviewer:** automated review, technical lead, presentation lead (presentation acceptance)
**Depends on:** P3, #126 (P6b; its travel probe carries the interim wait this slice removes) · **Milestone:** interaction
**Issue:** https://github.com/Thiesi/Blacksite/issues/155

Canon: game design 5.5 (Interact precedence) and architecture 5.5.2
(focus contract), both marked "planned, S39". Where this file and canon
differ, canon wins.

## Goal

What you stand on beats what stands beside you. A caller standing on
an exit or door tile who presses E goes through it, even when a talker
has wandered alongside. Today a Sodium regular beside the Tin Halo door
takes both the focus prompt and E. Nobody designed that order:
`Core.input_routes` just happens to list `npcs` before `simulation`,
where exits live.

Decided by the owner on 2026-11-04, from the presentation lead's rule.
Found by #126's contracts probe (diagnosis:
https://github.com/Thiesi/Blacksite/pull/126#issuecomment-6622283046).

## Scope

- **The precedence.** When the caller's own tile holds an exit or a
  door, that exit or door wins E and the focus prompt over an adjacent
  talker's dialogue.
  - **Exit:** any `meta.exits` tile of the caller's zone, including
    hidden exits. Hidden exits keep D-T4: they are named only while the
    caller stands on the tile.
  - **Door:** the apartment door a dedicated public doorstep already
    selects (game design 5.5, housing).
- **Everywhere else talkers keep winning,** including on the tile next
  to the door. To talk at a threshold, the caller steps off the door
  tile.
- **No special cases.** An anchored talker gets no exception. An
  authored talker placed on an exit tile is a layout problem for its
  zone, not something focus works around.
- **One mechanism.** The rule lives in the composed resolver that both
  the advertised focus (`ZoneView.focus`) and E dispatch use
  (`Core.resolve_interaction`). There is no second resolver, no
  probe-only path and no client-side guess.
- **Scope limits.** Only exits and doors underfoot move. Every other
  pair keeps today's order: props underfoot, terminals, the S25a
  fallback rules, contracts, commerce and the Wake Hall id ordering.
- **Probe clean-up.** Once the rule ships, drop #126's interim "wait for
  the advertised door focus" from `NativeProbe.travel`, or keep it only
  as a harmless assertion that the door is focused.

## Out of scope

- Any other E reordering. Each one is its own owner decision.
- Moving NPCs, spawn regions or authored placements.
- Prompt wording. The existing exit hint stays.

## Open point for the presentation lead before work starts

Adjacent **vendors**. On `main` a vendor's trade also routes ahead of
exits (`commerce` precedes `simulation`). The rule as decided names
talkers. The presentation lead confirms on #155 whether a door
underfoot also outranks an adjacent vendor before the slice starts. If
it does, the same precedence applies with no further owner decision,
because the rule ("what you stand on beats what stands beside you")
already covers it.

## Tests

- **Matrix.** Extend P3's predicted-equals-dispatched matrix with an
  exit tile and an adjacent talker, in both directions: the caller on
  the exit gets the exit, and the caller on the neighbouring tile gets
  the talker. Cover a hidden exit (named only on its tile) and an
  apartment doorstep.
- **Shipped street.** A headless test on Sodium Row puts a real wandering
  regular next to the Tin Halo door. A caller on the door tile sees the
  exit focus and travels on E. One tile off, the same caller gets the
  regular's dialogue.
- **No other change.** Every other P3 matrix pair resolves exactly as
  before, the mechanics fingerprint is unchanged, and goldens change
  only where a capture shows a caller on an exit beside a talker. Name
  each rebaseline.

## Acceptance

1. A caller on an exit tile with an adjacent wandering talker sees the
   exit focus and goes through on E.
2. One tile off the exit, the talker wins.
3. The advertised focus and the dispatch stay one mechanism and never
   give two answers.
4. #126's "wait for door focus" in the travel probe can be dropped.

Native evidence: the S19 network contract route through the Tin Halo
door at 80x24 and 132x50, run through NetBBS Telnet to native stdio,
with no wait-for-focus step. The presentation lead gives the
presentation acceptance.
