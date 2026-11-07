# P11 — The text place card

**Status:** planned (approved by the owner 2026-11-06)
**Primary model:** Codex · **Reviewer:** automated review, technical lead, presentation lead (presentation acceptance)
**Depends on:** P5, P6a, S38 (merged; supplies `me.truce_text`), S41 (#173, shipped in an earlier upgrade than this slice) · **Milestone:** presentation track
**Issue:** https://github.com/Thiesi/Blacksite/issues/164

Canon: terminal UI 2.6 and the key table in section 5, marked "planned,
P11". Where this file and canon differ, canon wins.

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

**A zone with no lore.** The card still opens and leaves out the text block.
Every shipped zone has lore today, so this only guards against a later zone
or a missing asset.

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
- Only on the zone view with no prompt, menu or overlay open. A first
  sight that arrives during the Wake, a screen, a menu or a prompt is held
  until that closes, as long as you're still in that zone. The server marks
  a zone seen when `discover` runs, which can be before the zone view
  appears, so a new character's first zone would otherwise never get a card.
- Only when a zone view for that zone has arrived, judged by that view's
  `me.threat`. A `place_card` frame alone paints nothing, so a card can't
  flash for one frame ahead of a threatened view.
- Never while anything threatens you (below). A first sight that meets a
  threat, including a held one, is dropped and not retried. The log already
  has the paragraph, and the card can be asked for later.

**When it closes.**

- After 8 seconds, on any key, or the moment a threat appears or you are
  hit.
- **Any key closes it and still acts.** A move on the card is a move, in
  the same frame and with no added delay. `Ctrl-X` and `Ctrl-L` behave as
  they always do.
- **The one exception is the card's own key.** `A` on an open card closes
  it and does nothing else: it sends no request and opens no second card.
- **When the connection drops.** The door can't see a threat while it's
  disconnected, so the card closes then.

**On request.** `A` (`a` in vi, as in the key table) shows the current
zone's card again. `keymaps.json` leaves `a` unbound on the zone view in
both keymaps; contract and crew menus use it, and a menu blocks the card.
A card you asked for stays until a key or a threat closes it, since you
asked to read it. While threatened, `A` opens nothing and the hint row says
"Not with danger this close." `A` is added to `keymaps.json`, the key table
and help.

**Threat.** The card reads two things, and you're threatened if either
says so. The later Auto decider can use the same two.

- `me.threat`: null, or the reason you're threatened now. Plan §11 note 12
  and the P4 row in §12 called for a declared signal, but P4 shipped without
  it, so P11 adds this field. One server function sets it from the view's
  already-masked `hazards`, `target` and `nearby` (a `!`) and from heat, so
  a covered NPC can't leak through a second code path.
- A danger or combat line that arrived within `PROTECT_SECONDS`: the door's
  existing arrival-stamped check (in `_notice_to_header`), shared rather than copied.
  This isn't new inference under note 12. The server already sent and masked
  these lines, and the check only times them. It uses the door's own clock,
  and it agrees with the existing notice and log protection by construction.

The door works out no other threat for the card. When the card opens or
closes is a visible signal, so `me.threat` carries the disclosure test.

A new door process stamps replayed log lines on arrival, so after a reconnect
recent danger lines count afresh. `A` can refuse for up to 10 seconds then.
That's harmless, because reconnecting opens no card. A door that's still
running skips lines it has already seen.

**Data.** The door needs the card's text at first sight and on request,
and it must not sit in every view body. The server sends one one-shot frame
when `discover` finds a first sight and in answer to a request intent:
`Frame("place_card", {"zone": <id>, "reason": "first" | "requested", "text": <paragraph>})`.
It isn't replayed on reconnect. District, name, safety and `truce_text` come
from `me` and aren't repeated.

**This frame relies on S41.** Without S41, `protocol.validate` raises
`ProtocolError` on an unknown frame type and the door's client treats that as a
disconnect and redials, so a door session still running across a service
upgrade would drop its player on the first `place_card`. S41 makes a door drop a
frame type it doesn't know and stay connected. That door simply shows no card,
and a request it sends gets an answer it ignores. So S41 has to reach operators
in an earlier upgrade than this slice, and the PR says so for the operator. The
slice adds `place_card` to the protocol's frame types and to `validate`'s
`server` set with its fields checked, so a known frame with bad fields is still
a protocol error. Lockstep upgrades stay the supported path, as S41 says.

The frame usually arrives first. `transition` and login call `discover`
before the new zone's first view goes out, so the door can't compare the
frame with its current zone on arrival, or it would discard most first
sights. The door keeps the latest frame, keyed by zone. If it already holds a
view for that zone from this connection, that view judges the frame. Otherwise
the next zone view does: a view for the frame's zone can open the card, and a
view for any other zone drops the frame. Frames arrive in order on one session,
so no older view can follow the frame.

**A redial starts clean.** `welcome` comes first on every connection and already
replaces the door's view (`Display.receive`), so a view from before a disconnect
can't judge a frame. The slice adds the rest to the same place: `welcome` also
clears any held frame and held first sight. Otherwise a frame held from the old
connection would open a card after a reconnect, and reconnecting opens nothing.

A frame lost to a disconnect is lost, and that's accepted: the zone is
already seen, the log keeps the paragraph, and `A` shows the card again.
Tracking delivery would cost more than one missed introduction.

The server answers a request only when the caller has a body in a zone.
During a tram ride, in the Lattice and on non-zone views it sends nothing,
so `A` can't read the wrong zone.

**Canon.** The PR filing this slice wrote the card's behaviour into terminal
UI 2.6 and the key table, marked "planned, P11". The implementation removes
both marks. It also adds the new wire contract to architecture: `place_card`
to the server-to-client frame table in 5.3, and `me.threat` to the `me` shape
in 5.4.

## Owner decisions, 2026-11-06

1. **The paragraph shows twice.** On first arrival it's on the card and in
   the log below it at once. Both stay. The log is the record (S25b TR-9),
   and the card closes on your first key.
2. **Slice number and order.** This is P11, before P10's cutover, since 2.6
   calls it the default way a place presents itself. It takes no place
   ahead of the current queue (S38, S40, A9, S39).
3. **Sodium Row playtests.** They don't wait for this slice and don't
   include it. If the first impression should be judged with a card, that
   can be a later pass.

## Out of scope

- The on-entry setting. 2.6 makes this a setting, and the settings path is
  S30a. If S30a isn't merged when this starts, on-entry stays on and the
  setting joins S30a's list. `A` ships either way.
- Drawn 16-colour art and its format (V3, assets 4). Vignettes above the
  text (S33). Strip modes and a larger dashboard (PT1).
- The Lattice, which never gets a card, and text, menu, Wake and dead views.
- A new per-zone card sentence. The card reads existing lore.
- Any change to the first-arrival log lines.

## Tests

- First sight opens the card. Revisiting and reconnecting don't, using a
  saved `seen_zones`.
- A new character's first zone gets its card when the Wake closes, and a
  first sight held behind a screen or menu opens when that closes. A held
  one is dropped on leaving the zone or meeting a threat.
- `A` conflicts with no zone-view binding in either keymap, and `Z` still
  toggles stealth.
- Any key closes the card and still acts: a move on the card moves the
  caller, with the same intent as with no card.
- The timer closes it at 8 seconds on the injected clock. A requested card
  has no timer.
- `me.threat` is set for each input (hazard, target, `!`, heat). The card
  doesn't open while it's set or while a danger or combat line is within
  `PROTECT_SECONDS`, and closes when either applies.
- The card and the notice protection share one recent-line check.
- A `place_card` frame that arrives with a threatened view, in either order,
  never paints the card, not even for one frame.
- Disclosure: a covered NPC on the Row doesn't change `me.threat`,
  including for a Marked or heated caller, until it reveals itself.
- Prompt, menu and overlay block opening. `Ctrl-X` confirm still works over
  a card.
- `A` (`a` in vi) works in both keymaps, and refuses with the approved line
  while threatened. The server sends no card for a request during a ride, in
  the Lattice or on a non-zone view.
- `A` on an open card, first-sight or requested, closes it, sends no frame and
  opens nothing.
- Redial: after a disconnect from a zone view, a `place_card` for that same zone
  arrives after `welcome` and before the new view. The old view doesn't judge
  it, nothing paints until the new view arrives, and a threatened new view
  never paints the card. A frame held from before the disconnect opens nothing
  after the redial. A disconnect with a card open closes it.
- `validate` accepts `place_card` from the server with valid fields, and rejects
  it from a client or with invalid fields. This door's old renderer, which draws
  no card, ignores the frame and doesn't fail.
- A first-sight frame that arrives before its zone's first view opens the
  card when that view arrives, on a transition and at login. A view for
  another zone drops it.
- A zone with no lore opens a card without the text block.
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
card, a move key closes it and moves, `A` reopens it, and a threat closes
it. CPU stays within the P1 budget with the card open and closed.
Presentation lead acceptance from captures. H1 and S25 layout approval
are not part of this slice and aren't granted by it.

Interaction to check at build time: if the tram ride (#157, T1) has merged,
the car view counts as not the zone view, so a first sight waits for arrival.
