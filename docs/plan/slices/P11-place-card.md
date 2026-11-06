# P11 — The text place card

**Status:** proposed by the presentation lead, 2026-11-06, at the owner's request (S38 ruling, #159); not yet approved
**Primary model:** Codex · **Reviewer:** automated review, technical lead, presentation lead (presentation acceptance)
**Depends on:** P5, P6a, S38 (`truce_text`) · **Milestone:** presentation track

Canon: terminal UI 2.6. Where this file and canon differ, canon wins,
apart from the two canon changes listed under Scope, which this slice
makes once approved.

## Goal

The first time you see a place, it introduces itself: district, name,
how safe it is and what it's like, for a few seconds, without ever
costing you a keypress or hiding a danger. Terminal UI 2.6 has described
this since P0, but no slice owned it. P5 left it out, and V3 only owns
the drawn 16-colour art.

The owner moved S38's two card strings here on 2026-11-06:
`CONTESTED · TRUCE` and "<Keeper> keeps the peace here."

## Scope

**Where it shows.** The new presentation only, on the zone view. The old
renderer gets no card and P10 retires it. The card is a box inside the
map pane. The header, side panel, log and hint row stay live and
visible, so the safety word and any danger line are never covered.

**Contents, top to bottom:**

1. District in letter-spaced capitals, unspaced if it doesn't fit.
2. Zone name in letter-spaced capitals, unspaced if it doesn't fit.
3. The safety word in its header colour. In a truce zone it reads
   `CONTESTED · TRUCE`, under the same condition as the header's truce
   word.
4. The zone's text: the first paragraph of its first `lore` asset, the
   same paragraph first arrival logs.
5. In a truce zone, `truce_text` ("Sable keeps the peace here.").
6. A closing line: "Any key continues."

**Text is never cut.** The trial's card silently dropped lines that
didn't fit. Here a test fails any shipped zone whose card doesn't fit at
80x24. Today's 10 zone files fit: the longest first paragraph wraps to 4
lines at 45 columns.

**Light.** The box takes the place's most common ground colour from the
visible `looks`, worked out once when the card opens, so it doesn't
change or cost anything per frame. A zone with no looks uses the plain
panel background. Text on the ground meets P6's contrast floors, and at
16 colours the backgrounds stay within 0 to 7. 16-colour callers get
this text card until V3 supplies drawn cards.

**When it opens.**

- On first sight of a zone, which the server decides from `seen_zones`.
  The door must not treat every zone change as first sight, as the trial
  did: returning to a place opens nothing, and neither does reconnecting.
- Only on the zone view with no prompt, menu or overlay open.
- Never while anything threatens you (below). A first sight that can't
  open is not retried. The log already has the paragraph, and the card
  can be asked for later.

**When it closes.**

- After 8 seconds, on any key, or the moment a threat appears or you are
  hit.
- **Any key closes it and still acts.** A move on the card is a move, in
  the same frame and with no added delay. `Ctrl-X` and `Ctrl-L` behave as
  they always do.

**On request.** `Z` shows the current zone's card again, in both keymaps.
A card you asked for stays until a key or a threat closes it, since you
asked to read it (canon change 1). While threatened, `Z` opens nothing
and the hint row says "Not with danger this close." `Z` is added to the
key table and to help.

**Threat.** The decision reads only fields the server has already
declared and masked: `hazards`, `target`, a `!` in `nearby`,
`me.heat_until`, and danger or combat log lines within the existing
`PROTECT_SECONDS`. There is no door-side inference. Plan §11 note 12
applies: when the card opens or closes is a visible signal, so a covered
NPC must never change it before the caller could know.

**Data.** The door needs the card's text at first sight and on request,
and it must not sit in every view body. Suggested shape, which the
technical lead may change: one additive frame from the server, sent when
`discover` finds a first sight and in answer to a request intent, marked
as opening or requested. It carries only the current zone's paragraph.
The door discards it on zone change, under architecture 5.5.4. `truce_text`
stays in `me`.

**Canon changes, made by this slice:**

1. Terminal UI 2.6: "It lasts up to 8 seconds" gains "unless you asked
   for it, when it stays until a key or a threat closes it." `Z` replaces
   the unnamed request.
2. Terminal UI 2.6: "A truce zone's card (planned) shows..." loses
   "(planned)". S38 adds that line.

## Decisions for the owner

1. **The paragraph shows twice.** On first arrival it's on the card and in
   the log below it at once. I recommend keeping both. The log is the
   record (S25b TR-9), and the card closes on your first key.
2. **Slice number and order.** I'd make this P11, before P10's cutover,
   since 2.6 calls it the default way a place presents itself. It takes no
   place ahead of the current queue (S38, S40, A9, S39).
3. **Sodium Row playtests.** I recommend not waiting for this slice and not
   adding it to them. Play them as planned, and if the owner wants the
   first impression judged with a card, that can be a later pass.

## Out of scope

- The on-entry setting. 2.6 makes this a setting, and the settings path is
  S30a. If S30a isn't merged when this starts, on-entry stays on and the
  setting joins S30a's list. `Z` ships either way.
- Drawn 16-colour art and its format (V3, assets 4). Vignettes above the
  text (S33). Strip modes and a larger dashboard (PT1).
- The Lattice, which never gets a card, and text, menu, Wake and dead views.
- A new per-zone card sentence. The card reads existing lore.
- Any change to the first-arrival log lines.

## Tests

- First sight opens the card. Revisiting and reconnecting don't, using a
  saved `seen_zones`.
- Any key closes the card and still acts: a move on the card moves the
  caller, with the same intent as with no card.
- The timer closes it at 8 seconds on the injected clock. A requested card
  has no timer.
- It doesn't open with each threat input present (hazard, target, `!`,
  heat, recent danger line). It closes when each one appears.
- Disclosure: a covered NPC on the Row doesn't change opening or closing,
  including for a Marked or heated caller, until it reveals itself.
- Prompt, menu and overlay block opening. `Ctrl-X` confirm still works over
  a card.
- `Z` works in both keymaps, and refuses with the approved line while
  threatened.
- Every shipped zone's card fits at 80x24 and 132x50 with no cut text,
  including the longest district and zone names.
- The truce label appears only where the header shows the truce word.
- Contrast floors hold on every shipped ground, at every tier.
- With the card closed, rendering is byte-identical to before this slice.
- The mechanics fingerprint doesn't move. If the frozen E/J digest would,
  the PR stops for a ruling.
- Style goldens at 80x24 and 132x50 in all three tiers: Meridian Plaza,
  Clinic Row, Sodium Row (truce), and a zone with no looks.

## Definition of done

Roadmap §7, plus native evidence through NetBBS Telnet to native stdio,
at both sizes and all three tiers: first arrival on Sodium Row opens the
card, a move key closes it and moves, `Z` reopens it, and a threat closes
it. CPU stays within the P1 budget with the card open and closed.
Presentation lead acceptance from captures. H1 and S25 layout approval
are not part of this slice and aren't granted by it.

Interaction to check at build time: if the tram ride (#157, T1) has merged,
the car view counts as not the zone view, so a first sight waits for arrival.
