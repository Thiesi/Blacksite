# S36 — Tags: one short public mark per character

**Status:** planned (approved by the owner 2026-10-31)
**Primary model:** Codex · **Reviewer:** automated review, technical lead, presentation lead (glyph, drawing and wording)
**Depends on:** S08, S09, P6 (place layer and charted ground) · **Milestone:** asynchronous presence (#125)
**Issue:** https://github.com/Thiesi/Blacksite/issues/138

Canon: game design §11.1, "Tags", from #128. Where this file and canon
differ, canon wins.

**Timing (owner, 2026-10-31):** starts after H1, beside C1 and S25c.
Until P10's cutover, every view is built in both presentations.

## Goal

A character can leave one short text tag on the tile they stand on, so
other players find traces of each other's passing. A tag can never
imitate a thing or an exit, and never reveals anything hidden.

## Spec references

- Game design §11.1 (tags, every sub-bullet), §11 (chat text rules,
  ignore, report).
- Terminal UI §2.2 (map vocabulary; the tag glyph sits outside the rule
  glyphs), §2.3 (seen, known and charted ground).
- Architecture §5.5.4 (disclosure), §5.5.5 (charted public ground).
- Build notes on #125 (drawing rules, HERE listing, refusal wording).

## Scope

- **Persistence.** A migration (numbered in merge order): tag (author, zone, x, y,
  text, placed). Pruned at 7 days; one per author, so a new tag
  replaces the old.
- **Placement.** Only on a passable tile in a contested or open zone.
  Refused on walls and impassable tiles, doors and other visible
  interaction tiles, safe zones and pockets, all with the one message
  "You can't leave a tag here." Accepted on any other standable tile,
  hidden content included. 40 characters, chat text rules, one place
  or replace per 10 minutes, at most 3 per tile with the oldest
  replaced.
- **Drawing.** The presentation lead picks the one tag glyph. A tag is
  drawn only where nothing visible is, only the newest per tile, and
  place-layer dressing yields to it. On a hidden exit it is drawn and
  listed only for viewers who found that exit. On charted ground it is
  drawn only when the tile is seen or remembered. Undiscovered contents
  never change whether a tag is drawn.
- **HERE and look.** HERE lists up to three tags, newest first, with
  the start of their text, under the same hidden-exit rule. Looking at
  a tag shows it whole.
- **Retirement.** Retirement deletes the author's tag, through character retirement (the existing character-delete path in
  `server/characters.py`, through its `before_delete` hook).
  A later character who reuses the name starts with no tag.
- **Ignore, report and admin.** A tag by an ignored author is never
  drawn or listed for the ignorer. Tags are covered by report. Admin
  CLI `tag list <zone>`, `tag remove`.

## Out of scope

- Tags in the Lattice.
- Any change to authored signs or marks.

## Protocol and view models

- `ZoneView.tags[] {x, y}` for the drawn newest tag per visible tile,
  filtered per viewer by the rules above. HERE and look entries carry
  the text. No field reveals a tag the viewer may not see.

## Tests

- Each refusal, and that every refusal gives the same message.
- Acceptance on a hidden interaction tile, drawn as on plain floor.
- A hidden exit's tag: absent from map and HERE for a viewer who has
  not found it, present once they have.
- Charted ground: no tag drawn on a cell that is neither seen nor
  remembered.
- Visible item, hazard, actor or object outranks the tag; HERE still
  lists it.
- The 10-minute limit, 3 per tile with the oldest replaced, 7-day
  expiry, replacement of one's own tag.
- Ignore filter; report and admin removal.
- Retirement deletes the tag; a character reusing the name is neither
  shown as its author nor blocked by it.
- Goldens at both sizes and three
  tiers.

## Acceptance script

1. A tags a corridor tile "watch the vent". B walks past and sees the
   glyph; standing on it, B's HERE shows the text; a look shows it
   whole.
2. A tries a door, a wall and a safe zone, and gets the same refusal
   each time.
3. A tags a hidden exit's tile. B, who hasn't found it, sees no tag.
   After finding it, B sees it.

## Definition of done

Roadmap §7, plus: the disclosure tests pass and the presentation lead
signs off the glyph, drawing and wording.

## Implementer notes

- Filter tags per viewer on the server, as other disclosure is.
  The client never receives a tag it must hide.
- Tag eviction by three characters is accepted for now and tuned at
  the pacing gate (#125, review point 3).
