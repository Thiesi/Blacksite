# S10 — Combat v1: targeting, weapons, cooldowns, cover, damage, shock, down/dead, clone vats, corpse caches, hymns

**Status:** planned
**Primary model:** Opus · **Reviewer:** Astra or Fable (balance read against the catalog before merge)
**Depends on:** S07 · **Milestone:** M1
**Issue:** https://github.com/Thiesi/blacksite/issues/10

## Goal

Real-time combat between actors in a zone with the design's numbers:
targeting, ranged and melee weapons with cooldowns and ammo, to-hit and
damage with armour and cover, shock, down and dead, the decant at a
Sablier vat with clone debt, corpse caches, consumables, and the Cantor
hymns and dissonance abilities. The Wake corridor drone becomes real.
After this slice two players can fight in Clinic Row and one of them
can wake up in a vat.

## Spec references

- `docs/design/00-game-design.md` §3.1 (health, stamina, shock,
  evasion, tolerance), §5.2 (stealth stance sight rule), §5.3 (combat:
  to-hit, damage, melee, cover, consumables, hymns, drones stub), §5.4
  (down 5 s, dead, decant 20 s, clone debt 5 % + fee, fade 2 %, corpse
  cache 5 min, secured slots 3, killer loots first 60 s), §4 step 5
  (corridor drone), §14 (Wake Hall pocket; no attacks in safe/pocket).
- `docs/design/01-entities.md` §2.1 (player fields), §2.2 (item
  instance), §3.1 (actor cooldowns, effects, stance).
- `docs/design/03-terminal-ui.md` §2 (TARGET block, vitals), §5.1
  (Tab, F, quick slots 1–5), §7 (dead screen).
- `docs/world/06-catalog.md` §1 (weapons: range, damage, cooldown,
  accuracy, ammo, damage type; melee), §1.6 (ammo), §2 (armour by
  layer and type), §4 (hymns and dissonance), §7 (consumables), §14
  (balance notes: 6–10 s time to kill).

## Scope

- `src/blacksite/server/rules/combat.py`: pure functions:
  `to_hit(accuracy, skill, evasion, cover, range_penalty)` = accuracy +
  skill/2 − evasion − cover×10 − range_penalty (range penalty 5 per
  tile beyond half the weapon's range; 0 within); `damage(base, skill,
  armour_vs_type)` = base × (1 + skill/200) − armour, min 1; shock
  added = damage/2; melee ignores half of armour, 1.0 s cooldown,
  stamina cost 10; shock ≥ 80 slows actions by 50 %, shock 100 =
  knockdown 2 s; shock decays 5/s when not damaged for 3 s; chemical
  damage-over-time from the catalog's `(+n/s, t s)` fields; dissonance
  reduced only by `arm_d`.
- `src/blacksite/server/combat/engine.py`: per-zone combat subsystem
  ticked at 10 Hz: target selection (`target_next/prev` cycling
  visible hostiles by distance; in this slice every other player is a
  valid target outside safe/pocket zones, relation rules arrive in
  S20), `fire` intent resolves against the equipped weapon's cooldown,
  ammo (consumes one round of the matching `ammo_*` stack; "click" log
  line when empty), range and line of sight; melee via `fire` when
  adjacent with a melee weapon; combat log lines with the roll and
  reasons on request (`intent combat_log_verbose`); `in_combat` flag
  for 10 s after any exchange (read by S07's sleeper penalty).
- Safe and pocket zones: `fire` at a player is refused with a log line;
  the Warden response itself is S11.
- Down and dead: health 0 → `down` stance for 5 s (any crew member
  adjacent with `E` picks up — crews arrive in S22; for now any
  non-hostile player), then `dead`: the dead `TextView` with the 20 s
  decant timer and Sablier boilerplate; respawn at the nearest Sablier
  vat (`vatside-wake-hall` vats; faction vats in S20) with full health,
  shock 0; clone debt 5 % of `chits_hand` plus a fee by grade (grade ×
  10, from the design doc's "fixed fee by grade": make the table
  explicit in `00-game-design.md` in this PR), fade 2 % of XP toward
  next grade.
- Corpse cache: in contested/open zones a `cache` object at the death
  tile holding all unsecured inventory for 5 min; killer may loot at
  once, others after 60 s; `E` opens a `MenuView` to take items; secured
  slots (3 by default, `secured` flag on item instances) never drop;
  safe/pocket: nothing drops.
- Consumables: quick slots 1–5 bound in the inventory (S12 provides the
  binding UI; here a default binding of the first patch); instant with
  10 s cooldown per class; `con_sablier_patch` +25 health.
- Hymns and dissonance: the ten abilities from the catalog as cooldown
  actions on the same engine, gated on archetype Cantor and the
  resonance implant tiers (implants land in S16; until then a Cantor
  has tier 1 unlocked); hymns affect "crew members within 6 tiles"
  (crew in S22; until then self only).
- Stealth stance toggle (`intent stance {stealth}`) for Ghosts:
  halves range at which others see you (S06 rule), broken by firing.
- Wake step 5: the corridor drone NPC template `npc_wake_drone`
  (grade 1, 20 health, a 5-damage 1.5 s weapon) spawned per new
  character, hostile only to that character, despawns on death; the
  Wake advances when it dies.
- `ZoneView.target` and `me.cooldowns`/`effects` populated; client
  renders the TARGET block (name, faction placeholder, HP bar as
  percent, range, cover, relation), flashes the border on being hit
  at every tier, shows cooldown ticks on the hint line.
- Bot: `blacksite.bot` gains a "fire at nearest" loop.

## Out of scope

- NPC behaviours beyond the scripted drone, Warden response (S11).
- Equipment management, ammo purchase, vendors (S12).
- Implants, surgery, drugs, XP from kills (S16).
- Crew pickup and shared XP (S22), faction relations and Marked (S20),
  faction vats (S20), drones as Operator tools (S16 or a later slice;
  `drone` actor kind exists from S06).

## Data and content

- `items.json`: the tier-1 weapons, ammo, armour and consumables from
  the catalog by ID (`wpn_kestrel_sidearm`, `wpn_kestrel_baton`,
  `wpn_halvard_hv7`, `wpn_sable_streetsweeper`, `wpn_ostrom_pinlight`,
  `wpn_sable_spitter`, `wpn_ferry_slugthrower`, `wpn_kestrel_flare_pistol`,
  `wpn_ow_arcpen`, all `ammo_*`, `arm_wake_coverall`, `arm_kestrel_vest`,
  `arm_sable_leathers`, `arm_ferry_scrap_plate`, `arm_kestrel_helmet`,
  `con_sablier_patch`, `con_kestrel_ration`, `con_sable_stim`) if S12
  has not shipped them; `hymns.json` with all ten abilities;
  `npcs.json` with `npc_wake_drone`; `text/dead-screen.md`.

## Protocol and view models

- `intent {name: "target_next" | "target_prev" | "target_clear" |
  "fire" | "use_slot" (args {slot}) | "ability" (args {id}) | "stance"
  | "pickup" | "loot_take" (args {item}) | "combat_log_verbose"}`;
  `key F/Tab/1–5` map to these.
- `ZoneView.target`, `me.hp/sta/shock/cooldowns/effects/in_combat`,
  `view {kind: "dead", body: {seconds_left, text}}`, cache objects with
  `state: {items: n, killer_only_until}`.

## Tests

- `tests/rules/test_combat.py::test_to_hit_formula`,
  `::test_range_penalty_beyond_half_range`, `::test_damage_min_1`,
  `::test_shock_half_of_damage`, `::test_shock_80_slows_100_knockdown`,
  `::test_melee_half_armour_and_stamina`, `::test_chemical_dot`,
  `::test_dissonance_only_arm_d`, `::test_ttk_hv7_vs_grade5_ghost_between_6_and_10s`
  (with the raised tier-1 accuracy or Nerve/3 evasion; assert the
  catalog's balance-note scenario lands in the window).
- `tests/combat/test_engine.py::test_cooldown_enforced`,
  `::test_ammo_consumed_and_click`, `::test_los_required`,
  `::test_safe_zone_refuses_fire`, `::test_down_5s_then_dead`,
  `::test_pickup_during_down`, `::test_decant_20s_at_vat`,
  `::test_clone_debt_5pct_plus_fee`, `::test_fade_2pct_xp`,
  `::test_cache_unsecured_only`, `::test_cache_killer_first_60s`,
  `::test_cache_expires_5min`, `::test_no_drop_in_pocket`,
  `::test_consumable_class_cooldown_10s`, `::test_hymn_steady_shock_minus_20`,
  `::test_dis_jam_cooldowns_plus_50pct`, `::test_stealth_broken_by_fire`,
  `::test_wake_drone_hostile_only_to_owner_and_advances_wake`.
- `tests/harness/test_duel.py::test_two_sessions_duel_deterministic`
  (seeded RNG, scripted fire, assert the loser dies within the window
  and respawns in the Hall).
- `tests/door/test_combat_render.py::test_target_block_golden`,
  `::test_border_flash_16_colour`, `::test_dead_screen_golden`.

## Acceptance script

1. New character: the corridor drone shoots; `Tab`, `F` repeatedly;
   it dies in a few seconds; the Wake continues.
2. Two callers in Clinic Row with starter sidearms: `Tab` targets the
   other; `F` fires on cooldown; both HP bars fall; shock slows the
   loser around second 5; the loser is down, then dead, then in a vat
   after 20 s with 5 % fewer chits. The winner opens the cache with `E`
   and takes the loser's ration bars; the coverall (secured) is not
   there.
3. Same in Meridian Plaza: `F` refused with a log line.
4. A Cantor uses `hymn_steady` (key `1` after binding) and sees shock
   drop by 20; `dis_jam` on a target slows their fire.
5. A 16-colour terminal shows the hit flash as a border colour change.

## Definition of done

- Roadmap §7 holds; the balance read is summarised in the PR and the
  design doc's §3.1/§5.3 numbers (and the new clone-fee table) are the
  ones the tests assert.

## Implementer notes

- Latency: at 150 ms Telnet round trip a 0.8 s cooldown weapon fires
  visibly on rhythm; do not add client-side prediction.
- Everything rolls on the zone's seeded RNG so duels are reproducible
  in tests.
- The dead `TextView` must be leavable only by the timer, and the
  client must keep rendering the log underneath (crew talk while you
  decant is the intended feel).
- Corpse caches are zone objects, not items on the ground; they must
  survive the zone going dormant (lazy expiry on wake).
- `RLIMIT_CPU`: the client's border flash is one frame; never animate
  with timers on the client.
