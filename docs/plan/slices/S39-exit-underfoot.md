# S39 — Exit underfoot: a door on your tile outranks an adjacent talker or vendor

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
  talker's dialogue and an adjacent vendor's trade.
  - **Exit:** any `meta.exits` tile of the caller's zone, including
    hidden exits. Hidden exits keep D-T4: they are named only while the
    caller stands on the tile.
  - **Door:** the apartment door a dedicated public doorstep already
    selects (game design 5.5, housing).
- **Everywhere else talkers and vendors keep winning,** including on
  the tile next to the door. To talk or trade at a threshold, the caller
  steps off the door tile.
- **No special cases.** An anchored talker gets no exception. An
  authored talker placed on an exit tile is a layout problem for its
  zone, not something focus works around.
- **One mechanism.** The rule lives in the composed resolver that both
  the advertised focus (`ZoneView.focus`) and E dispatch use
  (`Core.resolve_interaction`). There is no second resolver, no
  probe-only path and no client-side guess.
- **Scope limits.** Only exits and doors underfoot move. Every other
  pair keeps today's order: props underfoot, terminals, the S25a
  fallback rules, contracts, other commerce and the Wake Hall id
  ordering.
- **Probe clean-up.** Once the rule ships, drop #126's interim "wait for
  the advertised door focus" from `NativeProbe.travel`, or keep it only
  as a harmless assertion that the door is focused.

## Out of scope

- Any other E reordering. Each one is its own owner decision.
- Moving NPCs, spawn regions or authored placements.
- Prompt wording. The existing exit hint stays.

## Vendors

Settled by the presentation lead on #156 (comment 6634841544): a door or
exit underfoot also beats an adjacent vendor, and one tile off, the
vendor wins. On `main` a vendor's trade routes ahead of exits
(`commerce` precedes `simulation`), so this slice moves it the same way
as a talker. The owner's rule ("what you stand on beats what stands
beside you") already covers it.

## Tests

- **Matrix.** Extend P3's predicted-equals-dispatched matrix with an
  exit tile and an adjacent talker, in both directions: the caller on
  the exit gets the exit, and the caller on the neighbouring tile gets
  the talker. Add the same pair for an adjacent vendor: on the exit the
  caller gets the exit, and one tile off it gets the vendor's trade.
  Cover a hidden exit (named only on its tile) and an apartment
  doorstep.
- **Shipped street.** A headless test on Sodium Row puts a real wandering
  regular next to the Tin Halo door. A caller on the door tile sees the
  exit focus and travels on E. One tile off, the same caller gets the
  regular's dialogue.
- **No other change.** Every other P3 matrix pair resolves exactly as
  before, the mechanics fingerprint is unchanged, and goldens change
  only where a capture shows a caller on an exit beside a talker. Name
  each rebaseline.

## Acceptance

1. A caller on an exit tile with an adjacent wandering talker or a
   vendor sees the exit focus and goes through on E.
2. One tile off the exit, the talker or vendor wins.
3. The advertised focus and the dispatch stay one mechanism and never
   give two answers.
4. #126's "wait for door focus" in the travel probe can be dropped.

Native evidence: the S19 network contract route through the Tin Halo
door at 80x24 and 132x50, run through NetBBS Telnet to native stdio,
with no wait-for-focus step. The presentation lead gives the
presentation acceptance.
