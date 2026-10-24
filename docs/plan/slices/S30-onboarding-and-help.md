# S30 — Onboarding and help: hint system, help pages, first-run screen, session-limit UX, colour-blind palettes, settings

**Status:** planned
**Primary model:** Sonnet · **Reviewer:** Human (a first-time player pass by the user)
**Depends on:** S07, S09, S13, S19 · **Milestone:** M6
**Issue:** https://github.com/Thiesi/blacksite/issues/30

S18 housing help must teach the `*` storage, `$` safe and `b` bed, bed
management/logout, and Personal impound at banks. Half the class storage
can be secured in place, independently of carried secured slots; quality
and secured status survive transfers. A full protected destination
refuses without unsecuring goods. The safe is separate from bank/hand
rent funds. Keys and Passkey open only a 30-second visitor vestibule;
crew membership grants no resident permissions. Explain the first paid
week and two-week unpaid lapse, and distinguish S25's actual locations
from S18's native fixtures. See game design 8.7, [S18](S18-apartments.md)
and accepted [PR #38](https://github.com/Thiesi/Blacksite/pull/38).

## Goal

S19 native input handoff: preserve the door's successful read result when
an Escape deadline and reader completion race. The input pump retains
that task and drains pending bytes before treating its ordinary 200 ms
framing grace as a lone Escape. Extend coverage with S30's API-5, zero-time
and Unicode checks; do not restore a cancelling timeout that can discard
consumed arrow bytes and type a chat hotkey. S19 records its real native
rerun separately from deterministic key-decoder fixtures.

Make the first hour self-explanatory and the hundredth hour
comfortable. Ship the server-driven hint line, the contextual help
pages, the first-run "what is this" screen, the wall-time warnings and
reconnect UX, the two colour-blind palette variants, and the settings
menu that ties keymap, palette, log verbosity, and sitrep visibility
together. Nothing here changes a rule; it explains them.

## Spec references

- `docs/design/03-terminal-ui.md` §1 (tiers, palette roles and
  variants), §5.1 (two keymaps, rebinding is a settings change), §7
  (title, Wake, dead, disconnected, banned screens), §8 (deutan and
  protan variants; no information by colour alone; relation tags), §10
  (help pages; hint system: first three sessions, next useful key until
  used).
- `docs/design/00-game-design.md` §2 (warn at five and one minutes;
  reconnect resumes), §4 (the Wake must complete in five minutes), §11
  (sitrep visibility trade), §15 (accessibility, no plain mode, refuse
  below 80×24).
- `docs/design/02-architecture.md` §2.2 (reconnect backoff up to 60 s),
  §8.2 (`DOOR_BLACKSITE_SESSION_LIMIT`, standalone alias
  `BLACKSITE_SESSION_LIMIT`, optional deadline and reconnect),
  §5.4 (`hint` in views; `TextView`).
- `docs/design/01-entities.md` §2.1 (`settings`).
- `docs/world/08-found-texts.md` (title tagline block, the 16-line
  first-run screen), `docs/world/07-glossary.md` (in-game glossary
  page), `docs/world/05-story-arcs.md` (Wake briefing text used by S07;
  this slice only adds hints around it).
- `docs/upstream/02-session-limits.md` and `04-door-info-enrichment.md`
  (`session_limit_seconds` if present).

## Scope

- Hint engine (`src/blacksite/server/hints.py`): an ordered list of
  hints keyed by context (zone, lattice, menu kind) and a "used"
  predicate (the player performed the action). For a character's first
  three sessions, the view's `hint` shows the first unused hint for the
  context; afterwards the static key line. Hints: move, target, fire,
  interact, chat, inventory, jack in, program slot, crew invite, sitrep,
  help, map. Stored as a bitset in `settings`.
- Help (`TextView`): `?` opens two pages: keys for the current context,
  then the full keymap; a third page "Glossary" with the glossary
  entries; a fourth "The rules in one page" (safety classes, Marked,
  death, clone debt, secured slots) written from the design doc.
- First-run screen: shown once per BBS user before the Wake, from the
  found-texts asset, any key continues; stored as a flag on the player
  row.
- Session-limit UX (`blacksite.door`): take the minimum positive host
  `session_limit_seconds` and explicit `DOOR_BLACKSITE_SESSION_LIMIT`
  (standalone `BLACKSITE_SESSION_LIMIT`). Zero/unset game override
  adds no limit; absent host deadline plus no positive override is
  unlimited, not an implicit 3600 seconds. With a deadline, `toast`
  at T−300 s and T−60 s ("The line drops in five
  minutes. Karst keeps your place."); at T−5 s the client sends `bye
  {reason: session_limit}` and exits cleanly so NetBBS's watchdog never
  fires. Server marks the session `resumable` for 60 s.
- Disconnected screen: reconnect countdown with backoff (1, 2, 4, 8…
  up to 60 s total), then "The city is dark right now." and exit 0.
- Palettes: `content/palette.json` gains `deutan` and `protan`
  variants for every role at all three tiers; the nearby list and
  target block show the relation tag (`!`, `~`, `+`) at every tier and
  variant.
- Settings menu (`MenuView`): keymap (arrows/vi), palette (default/
  deutan/protan), tier override (auto/truecolor/256/16), log verbosity
  (all/combat off/chat only), sitrep visibility (visible/hidden),
  reset hints. Changes apply immediately (client re-renders on the
  palette or tier change; a full `view` follows).
- Minimum-size refusal text and the "leave door" confirmation key
  (`Ctrl-X` then `Y`).
- Respect NetBBS's boolean `unicode_style`: false gets a clear ANSI
  graphic requirement and clean return before world entry, inviting
  Unicode/CP437 selection in NetBBS. Do not silently override preference
  or add an ASCII tier. Missing is unknown; retain the graphic default.
  S31 owns platform API/version enforcement and real transport proof.
- Title screen composition with the tagline block (art itself is S33;
  the text fallback is here).

## Out of scope

- The Wake's own steps and briefing (S07). Chat channels (S09). Art
  (S33). Colour role assignment for new subsystems (each owning slice).
- Platform forwarding of the real limit (released in NetBBS v7.3.0).

## Data and content

- `content/hints.json`: `id, context, text, used_when` (closed set of
  intent names).
- `content/text/help-*.md`, `text-first-run`, `text-rules-one-page`.
- `palette.json` variants; a validator rule that every role exists in
  every tier and variant.

## Protocol and view models

- `hint` field already in `ZoneView`/`LatticeView`/`MenuView`; this
  slice populates it from the engine.
- Intents: `settings.open`, `settings.set {key, value}`, `help.open
  {page}`, `first_run.ack`.
- `welcome.palette` carries the chosen variant; `toast` for limit
  warnings.

## Tests

- `test_hint_engine_shows_first_unused_for_context`
- `test_hints_stop_after_three_sessions`
- `test_hint_marked_used_on_matching_intent`
- `test_help_pages_render_within_80x24_text_view`
- `test_first_run_shown_once_per_user`
- `test_session_limit_toasts_at_300_and_60_seconds` (fake clock)
- `test_client_sends_bye_and_exits_before_limit`
- `test_server_resumes_session_within_60_seconds_without_sleeper_penalty`
- `test_reconnect_backoff_sequence_caps_at_60_total`
- `test_palette_variants_cover_every_role_and_tier`
- `test_relation_tags_present_in_nearby_and_target_at_all_tiers`
- `test_settings_change_triggers_full_view`
- `test_min_size_refusal_message_and_exit_0`
- `test_leave_door_requires_confirmation_key`

## Acceptance script

Use the supported NetBBS integration and registered callers. Register
the door at minimum play level 255, run Check setup and Test as SysOp,
then lower only above the actual guest account level (normally 1).
A guest must not reach character selection. Keep the host wall limit
unbounded or at least 420 seconds for the seven-minute override test.

1. Register a new BBS user, enter the door at 80×24: the first-run
   screen appears once; after the Wake, the hint line says "↑↓←→ move"
   until you move, then "Tab target" and so on.
2. Press `?` in the zone, in the Lattice, and in the inventory: the
   first page differs each time; page 3 is the glossary.
3. Open settings, choose the deutan palette: hostile and crew colours
   change and the `!`/`+` tags remain; switch to 16 colours: the screen
   redraws fully and stays readable.
4. Register the door with `DOOR_BLACKSITE_SESSION_LIMIT=420` in the profile
   environment: at 2 minutes and at 6 minutes the toasts appear; at 7
   minutes the client leaves cleanly to the door picker; re-enter within
   a minute and you are exactly where you were.
5. Stop the game service while playing: the disconnected screen counts
   down; start it within 30 s: play resumes; stop it for two minutes:
   "The city is dark right now." and the door exits.
6. The user plays as a first-time player for thirty minutes and lists
   every moment they did not know what to press; each becomes a hint or
   a help line in the PR.

## Definition of done

- Tests green; validator covers hints, palette variants, help assets.
- The user's first-time pass recorded and addressed.
- Slice file marked done with PR number.

## Implementer notes

- NetBBS's wall-time watchdog terminates the door at the cap; leaving
  five seconds early avoids the caller seeing a killed process and keeps
  the session record's exit code 0.
- The host already forwards `session_limit_seconds` when bounded.
  A game override can only shorten it; zero cannot disable a host cap.
  Reconnect does not restart the launch timer. Test finite/unlimited,
  absent/zero override, shorter host/override and invalid values with
  a fake clock, plus ASCII-preference refusal before character entry.
- Palette changes must re-render through the cell buffer, not by
  re-emitting the last frame with new colours.
- Keep help text under 76 columns in the source; the client wraps by
  display width anyway but golden screens are easier to read.

## Lore review integration

Issue #56's platform follow-up is specified in
`docs/plan/01-netbbs-platform.md` and architecture 8.2/8.4. Explain the
registered-only installation policy and keep BBS publicity out of the
core onboarding promise while the guest/audience conflict persists.

Use the revised first-run text and terminal UI 11. Teach the lease/grade
distinction, secured recovery and debt, physical-body risk while jacked,
public loan rig, journal provenance, work-order allocation and personal
finale choice. Finish Vesper's job with optional prose closed at 80x24;
repeat at 132x50 and all palette tiers with a wide handle. Each confusion
observed in the human run becomes a concrete UI/content fix, not a claim
that automated tests establish fun or balance.

## S17 integration handoff

Teach physical schematic purchase/find, inventory U to learn, workshop
F to craft, repeated 2-second harvest and Esc/B interruption. Explain
carried/required inputs, skill minimum and quality range. Use the same
`server.quality` selector for effective stats and help examples: fixed
permissions, slots, tolerance, durations and pack sizes never scale.

This carries the accepted [PR #38](https://github.com/Thiesi/Blacksite/pull/38)
findings 12/14 forward; see [S17](S17-salvage-and-fabrication.md).


### S20 faction integration handoff

Reference: [PR #38](https://github.com/Thiesi/Blacksite/pull/38) and S20.

Explain card +10 versus membership +30/legal discharge, once-only red-sable
standing migration, seven-day leave cooldown, four title thresholds and
current +90 perk eligibility. Describe public-default/hall decant choice,
visited Attending vats, identity daily receipts, optional-only reservations
and bound loan loss on jack-out. Kin free forecasts require +90; learned
programs/installed hardware survive membership loss.

### S22 crew integration handoff

Teach S22 [PR #61](https://github.com/Thiesi/Blacksite/pull/61)'s actual
two-to-five-person crews: sixty-second invites, leadership on logout,
ten-second loot offers, useful-action/guard participation and private
interior limits. Show names, not opaque IDs. Escape decoding follows
UI 5.3, including ready-input priority before treating an elapsed grace
as a lone Escape.

<!-- s19-services:start -->
### S19 source and service handoff

Reference: [S19 PR #62](https://github.com/Thiesi/Blacksite/pull/62),
[acceptance record](../../ops/s19-acceptance.md) and
[PR #38](https://github.com/Thiesi/Blacksite/pull/38).

S19 supplies the implemented source interfaces, 68 authored contracts
and four service nodes. Full root pytest passed 1344 tests with one
skip. Installed native acceptance covers both sizes and allocations,
forks, repair reconnect and paid restart. Consume the merged PR;
S25/S27/S26 still own real geography, referrals and activation.

Preserve Q active/done/journal tabs, compact objective/cost hints and header
service state without displacing danger, vitals or escape. Explain helpers,
contribution/guard requirements, original reservation deadlines and explicit
withdrawal. A stale clinic discount requires a fresh quote; it cannot
silently increase the bill.
<!-- s19-services:end -->

### S23 market handoff

Consume terminal UI 4 and S23, retaining the accepted
[PR #38](https://github.com/Thiesi/Blacksite/pull/38) product boundaries.
F9 beside a public terminal opens services even where E opens a contract
board. Services use M market, O bounties, J jack and C collection. Street
M/O/C remain map/drone/chat. Market D bids, U buys out, L lists, M shows
own history, C collects, K cancels, F filters and S sorts. Esc/B leaves;
Y is the last step of a selected financial action. Bank C also opens
market collection. Explain cursor/PgUp/PgDn paging, banked escrow, own-bid
credit toward buyout, the whole-chit fee, free purchased delivery and
the return of unsold inventory weight. Bounties grant no combat exemption.

<!-- s24-handoff:start -->
### S24 event integration and acceptance handoff

Reference: [S24 #24](https://github.com/Thiesi/Blacksite/issues/24),
[PR #38](https://github.com/Thiesi/Blacksite/pull/38) and
[platform #56](https://github.com/Thiesi/Blacksite/issues/56).

Explain F9 public services -> V forecasts, R to save/read, H held
forecasts and Esc/B back. A carried Ring-fall Chart uses the same reader
without consumption; Ferrymen +90 Kin reads the ring free. Public impact
warnings remain available to everyone. Cancellation/revision is explicit.
Explain Curfew inbound-only restrictions, preserved public shelters,
shared Convoy work, actual route-leg attendance and the one-hour turn-in
window after completion. Keep body risk, escape, selected runner, ally
health and full rig usable with overlapping event summaries at 80x24.
S25 must verify discoverability and pacing on actual full-city routes.
<!-- s24-handoff:end -->


<!-- s24-review-policy:start -->
### S24 practical review follow-up

Reference: [PR #65](https://github.com/Thiesi/Blacksite/pull/65), retaining
[PR #38](https://github.com/Thiesi/Blacksite/pull/38) and #56.

H shows the caller's 128 recent forecast reads, including compact final
outcomes after global history retirement and restart. Explain unread
corrections and deliberate R acknowledgement. A Convoy Beacon diversion ends
on arrival or after 60 seconds, and actual arrival/loss revises its forecast
so callers do not walk to a closed job.
<!-- s24-review-policy:end -->

<!-- s25-access:start -->
### S25 physical route access handoff

Reference: [S25 #25](https://github.com/Thiesi/Blacksite/issues/25),
[PR #38](https://github.com/Thiesi/Blacksite/pull/38) and platform #56.
Game 5.6 and entities 1.1 now specify typed member/story credentials,
alternative requirements and a missing-credential message. This bounded
runtime support is necessary to commission the canonical physical city;
S25 otherwise remains content work. Missing NPC profiles use the
initial values documented in game 5.5 and require pacing acceptance.

Explain missing physical credentials with each exit's `locked_text`:
standing or visitor pass for the Atrium, actual membership or story
authorization for the service lift, and the active finale for the Shaft
cage. Friendly standing alone is not membership. Show a usable outward
alternative; no question may gate the screen.
<!-- s25-access:end -->

<!-- s25-city-decisions:start -->
### S25 commissioning decisions (in progress)

Reference: [S25 #25](https://github.com/Thiesi/Blacksite/issues/25),
[PR #38](https://github.com/Thiesi/Blacksite/pull/38) and
[platform #56](https://github.com/Thiesi/Blacksite/issues/56).

The draft uses game 5.6's carried key OR exact local open-latch state for
the optional Drowned bulkhead. Ordinary Outworks/Shaft Foot travel is
free; a key is retained, not consumed. Hidden physical exits allow
explicit Interact on their tile and never auto-travel on a walk. All
Undercity base sight is five before carried light. Whole-zone `pocket`
safety protects clinics, just as an authored pocket does.

The existing Terraces sector expands from 36 to 48 cells: a public
register wing supplies 24 distinct apartment addresses without reusing
entry/uplink cells or changing existing hidden/gated routes. Halvard's
member hall, vat and counter are in the Mezzanine; public recruitment,
care and banking remain in the Atrium. Three secondary ration/flare and
salvage counters bring ordinary vendors to 22; only Landing retains its
20% salvage premium. New NPC profiles and gantry damage are documented
initial values in game 5.5/6.4 and must pass actual-city pacing.

Explain key-or-local-core access, physically found hidden exits and
open ordinary return routes. Point public Halvard visitors to the Atrium
and members to the Mezzanine. Show actual prices and letting locations;
do not claim the new population has passed human pacing yet.

These are in-progress decisions, not a claim of merge, native acceptance
or completion of the Shaft Foot/Far Ring and broader human pacing gates.
The real walled apartments also exposed a geometry-admission bug:
a closed private door must not freeze unrelated public controls.
Housing supplies the occupant's explicit Interact-to-leave doorstep as
the escape origin; occupied tiles remain passable and private entry
permissions still apply. Retain that proof under tenants, visitors,
restart and overlapping effects. The Lobby's five inert private-door
props are replaced by the real 24-unit Block Street pool.

S25 places `ferrymen-corpse`, `choir-shrine`, `unmoored-dead-drop` and the
empty Far Ring artifact sites as physical source hooks. S27 owns the
corpse's one-time personal map and the shrine's daily claim receipt;
S26 owns season artifact activation. A prop label alone grants no reward.
Permanent hazards are excluded from salvage-node placement because
incoming damage interrupts the harvest channel. If an optional opening
closes over a saved position, reconnect recovers to the nearest free,
non-hazardous tile in the public spawn component, respecting housing
entry permissions. Include both in actual-city restart and event tests.

Mezzanine physical admission does not grant a Citadel network credential;
its loan terminal keeps the normal network gate. The Far mast uses the
Scour sector and cannot bypass Static's Ring-fall gate. All 16 relay
sites are mapped, but Shaft Relay retains `requires_level`; S26 must bind
its availability to the committed level phase, alongside the story-route
providers. Mapping never pretends that this seasonal gate is open.

Native city commissioning also preserves fallback Interact on a physical
prop underfoot before any adjacent public network terminal. Shaft Foot
therefore reports its sealed season-console status; explicit J still
jacks in. Retain this actual-map regression through S26 activation and
later interaction handlers. See PR #66, alongside PR #38 and issue #56.
<!-- s25-city-decisions:end -->
