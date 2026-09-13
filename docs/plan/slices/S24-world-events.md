# S24 — World events engine and the five events

**Status:** planned
**Primary model:** Opus · **Reviewer:** none
**Depends on:** S11, S14, S17, S19, S21 · **Milestone:** M5
**Issue:** https://github.com/Thiesi/blacksite/issues/24

## Goal

Make the city change on a schedule players can learn, buy, anticipate and
act upon. Ring-fall, Curfew, Choir Surge, Exhale and Convoy use committed
plans and bounded composable effects, with truthful forecasts.

## Spec references

Game design section 12 owns durations, roll interval, advance notice,
weights, cooldowns, overlap and restart. Sections 7.5-7.7 and 13 own
service, relay/perk and season modifiers. Entity model 2.15 and
architecture 15 own durable plans and layered effects. Story arcs supply
attributed announcement voices; they never redefine a rule.

## Scope

- `server/events.py`: seeded scheduler using the injected clock. Roll
  every 20 min, select eligible plan at least 60 min before start, at
  most two overlapping events and no shared zone/sector reservation.
  Persist ID, seed, scope, times and compatible variant IDs before any
  forecast is displayed. Cooldowns follow completion, not announcement.
- Implement closed typed effects: surplus salvage/mission NPC spawning,
  warned hazard, inbound restriction, relay-claim pause, new-heat
  multiplier, compatible ICE variant, ability-magnitude bonus, bounded
  Silt reveal, capped spawn multiplier, key drop, temporary route,
  event contract and convoy route. Content never executes arbitrary code.
- Curfew restricts inbound entry to the Core; outward exits and existing
  safety remain intact. It pauses relay claims and doubles new heat
  durations. It neither traps residents nor arms safe-zone Wardens.
- Surge swaps only eligible nonblack ICE into compatible equal/lower-tier
  variants after a 5 s warning, never an immediate attack. Its +30%
  affects stated ability magnitudes, not cooldown, duration or range.
  Required paths, Silt escapes and safe-body protections remain intact.
- Ring-fall reserves its actual ring in advance. Convoy follows its
  committed route and publishes ordinary public escort opportunities;
  a Route Master reservation does not deny others. Ferrymen and relay
  previews read this same plan, including explicit cancellation updates.
- Effects are named layers over baseline, service state, control state,
  relay ownership and season modifiers. End/cancel removes that layer
  only; no reverse-undo stack that resurrects stale locks or prices.
- On restart reconcile expired wall-time plans and resume valid active
  plans with the same seed and reward receipts. No rerolled forecasts,
  catch-up spawn storm or duplicate key/contract payout.
- Announce start/mid/end with resolved placeholders; expose plan status,
  warning, scope and remaining time in zone/Lattice views. Admin list,
  force and cancel are audited; force still obeys warning/safety rules
  and marks changes to a previously published plan.

## Data and protocol

`events.json`, `routes.json`, compatible ICE variant records and event
text assets. Values are already fixed in game design section 12; do not
invent another table. No client scheduling authority. Existing event
views add plan ID, revision, status and warning; forecasts use menus.

## Out of scope

S17/S11 own salvage and NPC behaviours, S19 owns contract execution,
S21 owns capture, S26 owns settlement. This slice wires their existing
hooks and tests composed effects in fixtures plus currently shipped maps.

## Tests

- Seeded plan creation, cooldown, overlap, two-event cap and future scope.
- Bought/free forecast matches actual ring/route/variant after restart;
  forced change/cancel is visible to everyone who holds that forecast.
- Curfew leaves every outward exit and essential service usable;
  contested heat works, safe guards never deal damage, capture pauses.
- Surge preserves compatible tiers, never introduces black ICE, warns,
  preserves escapes and applies magnitude bonuses only.
- Ring-fall/Convoy/Exhale spawn and reward caps; all placeholders resolve.
- End/cancel order with a work-order allocation and relay change does
  not restore old geometry or double-apply a discount.
- Restart before commitment, during warning, while active and after
  expiry produces the same legitimate plan and one reward receipt.

## Acceptance script

1. List committed plans. Read a Ferrymen forecast, note the ring and
   start time, restart, and confirm the same plan in the menu.
2. At 80x24 force Curfew: a Core resident can leave; an outside caller
   sees an inbound restriction. Neither can attack inside the safe Core.
3. Start the forecast Ring-fall through a fixture clock advance or wait
   for its schedule; its actual ring matches the previously read record.
4. Force Surge while jacked in: a five-second warning precedes a legal
   variant swap. A Cantor sees +30% magnitude and unchanged cooldown.
5. Complete a service allocation, change a relay, then cancel an event;
   the allocation/ownership remain intact. Restart during Exhale and
   confirm correct remaining time and no duplicated loot.

## Definition of done

Roadmap section 7; durable forecasts, all five event templates, composed
safety/escape checks and restart acceptance. Numeric schedules stay in
main design; measured usability remains a real-terminal review.
