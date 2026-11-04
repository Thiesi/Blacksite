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
  - **Exit:** an exit whose `tile` equals the caller's position,
    including hidden exits. Hidden exits keep D-T4: they are named only
    while the caller stands on the tile.
    - `Simulation.interaction_target` also returns exits on adjacent
      tiles. Those are never promoted: an exit beside the caller keeps
      today's order, so the talker or vendor still wins there.
  - **Door:** the apartment door a dedicated public doorstep selects
    (game design 5.5, housing).
    - `apartments` already routes ahead of `npcs` and `commerce`, so on
      `main` the doorstep door probably already wins.
    - The slice does not change it. A matrix case pins the behaviour
      and records whether it already passed on `main`.
- **Exactly which routes the exit may jump.**
  - The exit (from `simulation`) is promoted only over a choice from
    `commerce` or `npcs`, and only under the condition above.
  - It never lifts above `events`, `market`, `contracts`, `factions`,
    `crews`, `relays`, `apartments`, `progression`, `lattice`,
    `interlock`, `combat`, `fabrication`, `chat` or the Lattice
    `terminal`. Every pair involving those keeps the route order.
- **Dispatch honours the selection.**
  - Today `Core._echo` offers E to every route in order and passes the
    selected choice only to the selected route. `dialogue_runtime.input`
    and `commerce.input` re-query when they get no `interaction`, so they
    could still consume E ahead of the promoted exit. Focus would then
    say "exit" while E opened a dialogue: the same bug.
  - When an interaction is selected, routes other than the selected one
    must not consume that E key. The selected route handles it with the
    selected choice.
  - Non-interaction input (movement, chat, menus already open) keeps
    today's dispatch.
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
- **Scope limits.** Only an exit underfoot moves. Every other
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

- **Matrix.** Extend P3's predicted-equals-dispatched matrix. Every case
  presses E through the composed `Core._echo` path, not only the
  advertised focus.
  - An exit tile with an adjacent talker, in both directions: the caller
    on the exit goes through on E, and the caller on the neighbouring
    tile gets the talker.
  - The same pair with an adjacent vendor: on the exit the caller goes
    through, and one tile off it gets the vendor's trade.
  - An exit on an **adjacent** tile with a talker also adjacent: the
    talker wins, because only an exit underfoot is promoted.
  - A hidden exit (named only on its tile) and an apartment doorstep.
    Record whether the doorstep case already passed on `main`.
- **Arrival-tile audit.**
  - List every shipped exit whose `target_tile` lands a caller on an exit
    tile, including the exit back.
  - Report each one on the PR. Don't move any; whether a layout should
    change is for the presentation lead and the consultant.
  - A caller arriving on such a tile would get the exit, not an
    adjacent talker, until they step off.
- **Shipped street.** A headless test on Sodium Row puts a real wandering
  regular next to the Tin Halo door. A caller on the door tile sees the
  exit focus and travels on E. One tile off, the same caller gets the
  regular's dialogue.
- **No other change.** Every other P3 matrix pair resolves exactly as
  before, now also checked through `Core._echo`. If the dispatch rule
  changes what E does for any existing pair, the PR names it and stops
  for a ruling, because that would be a second, unapproved reordering.
  The mechanics fingerprint is unchanged, and goldens change only where
  a capture shows a caller on an exit beside a talker or vendor. Name
  each rebaseline.

## Acceptance

1. A caller on an exit tile with an adjacent wandering talker or a
   vendor sees the exit focus and goes through on E.
2. One tile off the exit, the talker or vendor wins.
3. The advertised focus and the dispatch stay one mechanism and never
   give two answers. E pressed through `Core._echo` does what the focus
   advertised, for every matrix case.
4. #126's "wait for door focus" in the travel probe can be dropped.

Native evidence: the S19 network contract route through the Tin Halo
door at 80x24 and 132x50, run through NetBBS Telnet to native stdio,
with no wait-for-focus step. The presentation lead gives the
presentation acceptance.
