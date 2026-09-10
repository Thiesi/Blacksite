# S19 — Contracts: template engine, six types, boards, crew scaling, story chains, Vesper

**Status:** planned
**Primary model:** Opus (engine) · **Reviewer:** Gemini or Sonnet writes the content half from the world docs; Opus reviews it
**Depends on:** S11, S14 · **Milestone:** M3
**Issue:** (filled in when filed)

## Goal

Give the city work to hand out. A contract engine that instantiates the
six contract types from templates with parameter pools, contract boards
at every faction hall and at the Tin Halo, Vesper as the Freelance
handler, crew-scaled objectives and rewards, expiry, turn-in, and story
chains that advance a season. After this slice a Wake's contract card
leads to Vesper, and Vesper always has something.

## Spec references

- `docs/design/00-game-design.md` §9 (types fetch, hack, escort, clear,
  plant, survey; rewards chits, standing, items, XP; templates plus
  story contracts; crew scaling; boards at halls and the Tin Halo), §4
  step 7 (Wake contract card), §7.1 (standing from contracts), §10
  (crew XP sharing).
- `docs/design/01-entities.md` §1.10 (contract template fields), §2.7
  (contract instance and states), §1.11 (dialogue hook for handlers:
  S27).
- `docs/design/03-terminal-ui.md` §4 (contract board, active
  contracts), §5.1 (`Q` contracts).
- `docs/world/02-factions.md`: per-faction "Contracts" sections (three
  template ideas each and story hooks per season), handler names.
- `docs/world/05-story-arcs.md`: season 1 story-contract chains per
  faction (3–5 each) with objectives, zone/core slugs, and beats; the
  Tin Halo first-contract script.
- `docs/world/04-dramatis-personae.md`: Vesper and handler voices.

## Scope

- `server/contracts/engine.py`: load `content/contracts.json`; template
  fields per `01-entities.md` §1.10; instantiate with resolved params
  from pools (zone, core, NPC template, item, count, room); states
  `offered → active → complete | failed → turned_in`; expiry (default
  60 min real time for generated, none for story); at most 3 active
  generated contracts per player plus any story contracts; a board
  offers 5 generated contracts per faction refreshed every 30 min (lazy
  clock) plus the player's available story contract.
- Types and their progress hooks:
  - `fetch`: bring item `X` (spawned as a world object in zone `Z` or
    an existing item class) to the handler; progress on pickup, complete
    on turn-in.
  - `hack`: lift data `D` from core `C` (S14 `contract_key` data kind;
    the engine registers a keyed data entry in the core at offer time,
    removed at expiry).
  - `escort`: walk NPC `N` (S11 `follow` behaviour) from zone `A` to
    tile in zone `B`; fails if the NPC dies; scales by adding threat
    spawners along the route.
  - `clear`: kill `n` of NPC template `T` in zone `Z` (S11 death
    events); crew kills count.
  - `plant`: place item `X` in room `R` of core `C` (S14 `lat.plant`,
    3 s, +10 trace; add the intent here).
  - `survey`: visit `k` cells in sector `S` or tiles/regions in zone
    `Z` (S13/S06 visit events).
- Rewards on turn-in: chits (range × crew factor), standing deltas
  (with the faction, halved to allies, negative halved to enemies per
  §7.1: S20 applies; until then stored), XP (S16 `contract` source),
  item from a pool; crew scaling: objectives × (1 + 0.5 × (crew − 1)),
  rewards to every crew member in the zone at turn-in × (1 + 0.25 ×
  (crew − 1)).
- Story chains: `story: true`, `season`, `chain` next id; offered only
  by the chain's handler when the previous is turned in and the
  season matches; beats delivered as `TextView` on offer and turn-in
  (texts from the story-arcs doc); a chain's final contract calls a
  season hook (`on_story_chain_complete`, S26).
- Handlers: `talker` NPCs with a `contracts` role (S11/S27) at each
  hall; Vesper at `sodium-tin-halo` offers Freelance contracts from
  every faction's non-member pool plus her own; the Wake contract card
  is a `fetch` (deliver yourself: `survey` of the Tin Halo tile) that
  turns in with the first-contract script.
- Boards: `contract_board` object kind (halls, Tin Halo) opening
  `MenuView` kind `contracts` with tabs offered / active / done; accept
  from the board or the handler; turn in at the handler only.
- Player-issued bounties are S23.
- Persistence: contract instances with resolved params, progress, and
  timestamps; flush on every state change.

## Out of scope

- Dialogue trees for handlers and Vesper beyond the contract offer and
  turn-in texts: S27.
- Standing application and Marked effects: S20 (engine emits deltas).
- Season hooks and the Chronicle: S26.
- Bounties: S23.
- Convoy event's auto-posted escort/raid contract: S24 (uses this
  engine's `escort` and `clear` types with an `event` flag).

## Data and content

- `content/contracts.json`: at least 3 generated templates per faction
  (24) plus 6 for Vesper, and the season-1 story chains for all eight
  factions from the story-arcs doc; `content/text/contract-*.md` for
  offer and turn-in texts; `content/text/tin-halo-first.md`.
- Content half (Gemini or Sonnet): templates and story chains as data
  with the world docs' slugs, run through the validator (every zone,
  core, room, NPC template, and item it names must exist).

## Protocol and view models

- `MenuView` kind `contracts`: rows type, title, handler, objective
  summary, reward summary, expiry; detail pane with the offer text;
  actions accept / abandon / track.
- `ZoneView.hint` shows the tracked contract's next objective; `me`
  gains `tracked {title, progress}`.
- Intents: `contract.accept`, `contract.abandon`, `contract.track`,
  `contract.turn_in`, `lat.plant`.

## Tests

- `tests/test_contracts_content.py::test_all_templates_resolve_slugs`
- `tests/test_contracts_content.py::test_story_chains_link_and_season_tag`
- `tests/test_contracts.py::test_instantiate_from_pools_deterministic_seed`
- `tests/test_contracts.py::test_max_3_generated_active`
- `tests/test_contracts.py::test_board_refresh_30min_lazy`
- `tests/test_contracts.py::test_expiry_60min_fails_and_removes_core_key`
- `tests/test_contracts.py::test_fetch_pickup_and_turn_in`
- `tests/test_contracts.py::test_hack_lifts_registered_key_data`
- `tests/test_contracts.py::test_escort_fails_on_npc_death`
- `tests/test_contracts.py::test_clear_counts_crew_kills`
- `tests/test_contracts.py::test_plant_3s_trace_plus_10`
- `tests/test_contracts.py::test_survey_cells_and_tiles`
- `tests/test_contracts.py::test_crew_scaling_objectives_and_rewards`
- `tests/test_contracts.py::test_story_chain_offered_only_in_sequence`
- `tests/test_contracts.py::test_wake_card_leads_to_tin_halo_script`
- `tests/test_sim_multi.py::test_two_crew_members_share_clear_progress_and_rewards`
- `tests/test_sim_multi.py::test_escort_npc_follows_leader_across_zone_exit`
- `tests/test_door_menus.py::test_contract_board_golden_80x24`

## Acceptance script

1. A fresh Wake walks to the Tin Halo, presses `E` on Vesper, sees the
   first-contract script, and the board shows five offers.
2. Accept a `clear` contract for fixture drones in Vatside; the hint
   line tracks "0/4"; kill four; return; turn in; chits, standing, and
   XP lines appear.
3. Two callers crew up (S22) and accept the same `clear` contract: the
   objective reads 6 and both get the scaled reward.
4. A faction member at their hall sees the season-1 story contract
   with its offer text; complete it; the next chain entry appears.

## Definition of done

Roadmap §7, plus: the validator rejects a template naming a missing
slug, and every faction has a season-1 chain that plays end to end in
a test.

## Implementer notes

- Reward ranges and the crew factors above are new numbers; add them
  to `00-game-design.md` §9 in this PR.
- The `hack` type must register its key data in the live core instance
  and in the core state row so a restart keeps it.
- Story texts live in `content/text/`; the engine never embeds prose.
- Vesper's pool is "every faction's non-member templates": implement
  as a `handler_pool` field, not a copy of the templates.
