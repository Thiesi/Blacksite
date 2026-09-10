# Blacksite — Catalog

Every item class in the game with numbers. Canon for what things *are* is
`00-bible.md` §9; the rules these numbers plug into are
`../design/00-game-design.md` §3 (attributes), §5.3 (combat), §6.3
(programs), §8 (economy). Numbers are initial values for the balance
slice; a slice that changes one changes it here too and keeps the test.

Every row has an ID slug. The content slice turns these tables into data
files keyed by that slug; the slug is the stable contract, the display
name is not.

Conventions:

- **Tier** 1 to 3. Tier 1 is what a Wake can afford in the first hour.
  Tier 3 is faction-gated or fabricated.
- **Range** in tiles. **Cooldown** in seconds. **Accuracy** is the base
  to-hit term before skill, evasion, cover and range (design §5.3).
- **Ammo** is a type slug; a magazine is a stack of that ammo item.
- **Weight** in kilograms; carry weight is Frame / 2 kg (design §3.1).
- Prices in **chits** at neutral standing (design §8.2 modifies by standing).

Manufacturers, so the brand language stays consistent:

| Maker | Who | Makes |
|---|---|---|
| Halvard Ordnance | Halvard subsidiary | kinetic and energy weapons, heavy armour |
| Ostrom Optical | Halvard subsidiary | eyes, sights, energy weapons |
| Sablier | Sablier | implants, medical consumables, detox, drugs with a label |
| Kestrel Issue | Kestrel | cheap, sturdy, everywhere; convoy guard kit |
| Civic Pattern | Wardens | standard-issue Warden gear; sold only to Wardens |
| Sable Works | Red Sable workshops in the Sink | chemical weapons, black-clinic implants, drugs without a label |
| Old Works Collective | the Unmoored | rigs, programs, jury-rigged energy gear |
| Chapel Foundry | the Choir | resonance implants (built from Sablier parts), dissonance projectors |
| Ferry-make | Ferrymen | anything built from Ring-fall; ugly, heavy, hits hard |

---

## 1. Weapons

### 1.1 Damage types and what resists them

| Type | Typical source | Armour stat that reduces it |
|---|---|---|
| kinetic | slugs, flechettes, blades, clubs | `arm_k` |
| energy | lasers, arc coils, pulse | `arm_e` |
| chemical | acid, nerve agents, incendiary gel | `arm_c` |
| dissonance | Cantor projectors and hymns | `arm_d` (rare) |

### 1.2 Ranged, tier 1

| ID | Name | Maker | Type | Range | Dmg | CD | Acc | Ammo | Wt | Price | Line |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `wpn_kestrel_sidearm` | Kestrel Issue Sidearm | Kestrel Issue | kinetic | 6 | 12 | 0.8 | 55 | `ammo_9x` | 1.0 | 120 | The starter pistol. Everyone in Karst has fired one; most of them at the wrong person. |
| `wpn_halvard_hv7` | Halvard HV-7 Carbine | Halvard Ordnance | kinetic | 9 | 16 | 1.0 | 55 | `ammo_5x` | 3.2 | 340 | A guard's rifle. Boring, accurate, never jams, never surprises anyone. |
| `wpn_sable_streetsweeper` | Sable Works Streetsweeper | Sable Works | kinetic | 3 | 28 | 1.6 | 40 | `ammo_shell` | 3.8 | 300 | Pipe shotgun. In the Sink, "nice to meet you" is a sound. |
| `wpn_ostrom_pinlight` | Ostrom Pinlight | Ostrom Optical | energy | 7 | 10 | 0.6 | 65 | `ammo_cell` | 1.1 | 260 | A laser pointer that grew up. Quiet, precise, useless against plate. |
| `wpn_sable_spitter` | Sable Works Spitter | Sable Works | chemical | 4 | 9 (+4/s, 3 s) | 1.2 | 50 | `ammo_gel` | 2.0 | 280 | Sprays a caustic gel that keeps working after you stop. Don't stand downwind. |
| `wpn_ferry_slugthrower` | Ferry-make Slugthrower | Ferry-make | kinetic | 5 | 22 | 1.5 | 45 | `ammo_scrap` | 4.5 | 200 | Half of it fell out of the sky. The other half is a bicycle. |
| `wpn_kestrel_flare_pistol` | Kestrel Issue Flare Pistol | Kestrel Issue | chemical | 8 | 6 (+6/s, 4 s) | 2.0 | 35 | `ammo_flare` | 1.2 | 90 | Meant to call a convoy. Also sets things on fire, which sometimes calls a convoy. |
| `wpn_ow_arcpen` | Old Works Arc-Pen | Old Works Collective | energy | 5 | 11 | 0.7 | 60 | `ammo_cell` | 0.8 | 240 | A soldering tool with ambitions. Runners carry it because it fits next to a rig. |

### 1.3 Ranged, tier 2

| ID | Name | Maker | Type | Range | Dmg | CD | Acc | Ammo | Wt | Price | Line |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `wpn_halvard_hv9` | Halvard HV-9 Battle Rifle | Halvard Ordnance | kinetic | 11 | 24 | 1.1 | 60 | `ammo_5x` | 4.0 | 1400 | The rifle the HV-7 wanted to be. Spire security carry it with the safety off. |
| `wpn_halvard_dmr` | Halvard Longline DMR | Halvard Ordnance | kinetic | 16 | 40 | 2.4 | 70 | `ammo_7x` | 5.5 | 1900 | Marksman's rifle. In the Scour, you hear it after you're already down. |
| `wpn_ostrom_lance` | Ostrom Lance | Ostrom Optical | energy | 10 | 22 | 1.0 | 70 | `ammo_cell` | 2.6 | 1600 | Corporate laser rifle. Draws a line from you to the problem and removes the problem. |
| `wpn_ow_coilgun` | Old Works Coilgun | Old Works Collective | kinetic | 9 | 30 | 1.8 | 50 | `ammo_flechette` | 3.4 | 1200 | Rails from a tram motor, capacitor from a vat. Sounds like a slammed door. |
| `wpn_sable_needler` | Sable Works Needler | Sable Works | chemical | 8 | 14 (+5/s, 4 s) | 0.9 | 60 | `ammo_needle` | 1.8 | 1300 | Fires hypodermic darts. What's in them is up to you. |
| `wpn_sable_pump` | Sable Works Twelve | Sable Works | kinetic | 4 | 42 | 1.9 | 45 | `ammo_shell` | 4.2 | 1100 | A proper shotgun, machined, with the maker's mark filed off out of habit. |
| `wpn_kestrel_convoy_smg` | Kestrel Issue Convoy SMG | Kestrel Issue | kinetic | 7 | 13 | 0.5 | 50 | `ammo_9x` | 2.8 | 1000 | Convoy guards get one each and a box of magazines. Spray, reload, repeat. |
| `wpn_ferry_meteor_cannon` | Ferry-make Meteor Cannon | Ferry-make | kinetic | 6 | 60 | 3.0 | 40 | `ammo_scrap` | 9.0 | 1500 | A satellite thruster housing loaded with bolts. Heavy weapon (Hardline only). |
| `wpn_ostrom_arc_projector` | Ostrom Arc Projector | Ostrom Optical | energy | 5 | 18 (arc: 2 targets) | 1.4 | 55 | `ammo_cell` | 3.9 | 1700 | Jumps between targets. Halvard uses it on crowds and calls it "de-escalation". |
| `wpn_sable_torch` | Sable Works Torch | Sable Works | chemical | 3 | 20 (+8/s, 3 s) | 1.5 | 50 | `ammo_gel` | 5.0 | 1250 | Flamethrower. The Sink's answer to a locked door. Heavy weapon (Hardline only). |
| `wpn_chapel_tuning_fork` | Chapel Foundry Tuning Fork | Chapel Foundry | dissonance | 6 | 15 | 1.2 | 65 | none (Resonance) | 1.4 | 1500 | A dissonance projector. Cantor only. It does not make a sound you can hear; the target disagrees. |

### 1.4 Ranged, tier 3

| ID | Name | Maker | Type | Range | Dmg | CD | Acc | Ammo | Wt | Price | Line |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `wpn_halvard_hv12` | Halvard HV-12 Assault Rifle | Halvard Ordnance | kinetic | 12 | 32 | 0.9 | 65 | `ammo_5x` | 4.4 | 5200 | Spire issue. If you see one outside the Spire, someone died for it. |
| `wpn_halvard_anvil` | Halvard Anvil LMG | Halvard Ordnance | kinetic | 10 | 26 | 0.5 | 45 | `ammo_7x` | 11.0 | 6800 | Heavy weapon (Hardline only). Suppression as a personality. |
| `wpn_ostrom_scalpel` | Ostrom Scalpel | Ostrom Optical | energy | 14 | 48 | 2.0 | 80 | `ammo_cell` | 3.0 | 6500 | Surgical laser rifle. Ostrom says it's for eye clinics. Ostrom says a lot of things. |
| `wpn_ostrom_sunlance` | Ostrom Sunlance | Ostrom Optical | energy | 8 | 70 | 3.0 | 60 | `ammo_cell` | 8.5 | 7400 | Heavy weapon (Hardline only). Brief, bright, final. |
| `wpn_sable_widow` | Sable Works Widow | Sable Works | chemical | 9 | 18 (+9/s, 5 s) | 1.0 | 65 | `ammo_needle` | 2.2 | 5600 | Needler with a nerve-agent reservoir. Illegal in the Core, which is where it's used. |
| `wpn_ow_railpistol` | Old Works Railpistol | Old Works Collective | kinetic | 8 | 38 | 1.3 | 60 | `ammo_flechette` | 1.9 | 5000 | Coilgun tech, pocket size. Runners' choice for the walk home. |
| `wpn_ferry_ringfall_rifle` | Ferry-make Ring-fall Rifle | Ferry-make | kinetic | 15 | 55 | 2.6 | 60 | `ammo_scrap` | 7.0 | 4800 | Barrel from a satellite boom, sight from an optics grade. Nobody makes two alike. |
| `wpn_kestrel_gate_gun` | Kestrel Issue Gate Gun | Kestrel Issue | kinetic | 9 | 30 | 0.7 | 55 | `ammo_5x` | 5.0 | 4600 | Gate-guard carbine, Kestrel's only tier-3 design. Ugly, cheap for what it is, replaces itself. |
| `wpn_chapel_choir_bell` | Chapel Foundry Choir Bell | Chapel Foundry | dissonance | 7 | 30 (cone: 3 tiles) | 2.2 | 60 | none (Resonance) | 2.8 | 6000 | Cantor only. A cone of pure disagreement. Wardens classify it as a musical instrument. |
| `wpn_ostrom_pulse_carbine` | Ostrom Pulse Carbine | Ostrom Optical | energy | 10 | 28 | 0.8 | 65 | `ammo_cell` | 3.3 | 5400 | Energy counterpart to the HV-12, sold to Sablier security. Cleaner. Same result. |

### 1.5 Melee

Melee uses Frame and *Melee* skill, costs stamina per swing, ignores half
of armour, and has a fixed 1.0 s cooldown (design §5.3). Range is 1.

| ID | Name | Maker | Type | Dmg | Stamina | Wt | Tier | Price | Line |
|---|---|---|---|---|---|---|---|---|---|
| `wpn_kestrel_baton` | Kestrel Issue Baton | Kestrel Issue | kinetic | 14 | 6 | 0.9 | 1 | 40 | Starter melee. A stick that has been to meetings. |
| `wpn_sable_shiv` | Sable Works Shiv | Sable Works | kinetic | 18 | 5 | 0.3 | 1 | 60 | Fast, quiet, easily lost, easily replaced. |
| `wpn_ferry_wrench` | Ferry-make Ring Wrench | Ferry-make | kinetic | 26 | 10 | 3.0 | 1 | 110 | A tool for satellites. Also for people who touch your salvage. |
| `wpn_halvard_shock_baton` | Halvard Shock Baton | Halvard Ordnance | energy | 22 (+10 shock) | 8 | 1.2 | 2 | 700 | Adds shock on hit. Security issue; the humane option, by Halvard's definition. |
| `wpn_sable_machete` | Sable Works Machete | Sable Works | kinetic | 34 | 9 | 1.6 | 2 | 650 | The Sink's ceremonial blade. The ceremony is short. |
| `wpn_ow_arc_knuckles` | Old Works Arc Knuckles | Old Works Collective | energy | 20 (2-hit) | 7 | 0.7 | 2 | 800 | Capacitor gloves. Two fast hits per swing. Don't shake hands. |
| `wpn_sable_acid_blade` | Sable Works Etcher | Sable Works | chemical | 24 (+6/s, 3 s) | 9 | 1.4 | 3 | 3200 | A blade that keeps cutting after you've put it away. |
| `wpn_halvard_ram` | Halvard Breaching Ram | Halvard Ordnance | kinetic | 60 (+30 shock) | 20 | 9.0 | 3 | 4000 | Heavy weapon (Hardline only). Knocks down anything smaller than a door. Most things are. |
| `wpn_chapel_hand_bell` | Chapel Foundry Hand Bell | Chapel Foundry | dissonance | 28 | 6 | 0.9 | 3 | 3600 | Cantor only. Touch-range dissonance. Mother Quell carries one and has never been seen to use it. |

### 1.6 Ammunition

| ID | Name | Stack | Price per stack | Notes |
|---|---|---|---|---|
| `ammo_9x` | 9x pistol rounds | 50 | 25 | Kestrel Issue, everywhere |
| `ammo_5x` | 5x rifle rounds | 60 | 60 | Halvard pattern |
| `ammo_7x` | 7x heavy rounds | 40 | 110 | Halvard pattern; DMR and LMG |
| `ammo_shell` | shotgun shells | 24 | 45 | Sable Works and Kestrel |
| `ammo_cell` | energy cell | 30 charges | 70 | Ostrom pattern; rechargeable at any terminal for 10 chits |
| `ammo_gel` | caustic gel canister | 20 | 55 | Sable Works |
| `ammo_needle` | needle darts | 30 | 90 | Sable Works; loaded with whatever drug or agent you choose |
| `ammo_flechette` | flechette rails | 30 | 80 | Old Works |
| `ammo_scrap` | scrap bolts | 20 | 15 | Ferry-make; fabricated from hull salvage 1:20 |
| `ammo_flare` | flares | 6 | 30 | Kestrel Issue |

## 2. Armour

Armour is worn in three layers: **body**, **head**, **limbs**. Each piece
lists its reduction per damage type. Heavy armour is Hardline only and
reduces Evasion by the listed amount.

| ID | Name | Maker | Layer | arm_k | arm_e | arm_c | arm_d | Evasion | Wt | Tier | Price |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `arm_wake_coverall` | Sablier Wake Coverall | Sablier | body | 2 | 2 | 4 | 0 | 0 | 1.0 | 1 | 0 |
| `arm_kestrel_vest` | Kestrel Issue Vest | Kestrel Issue | body | 6 | 3 | 2 | 0 | 0 | 3.0 | 1 | 220 |
| `arm_sable_leathers` | Sable Works Leathers | Sable Works | body | 5 | 4 | 6 | 0 | 0 | 2.5 | 1 | 260 |
| `arm_ferry_scrap_plate` | Ferry-make Scrap Plate | Ferry-make | body | 10 | 4 | 3 | 0 | −4 | 7.0 | 1 | 300 |
| `arm_kestrel_helmet` | Kestrel Issue Helmet | Kestrel Issue | head | 4 | 2 | 1 | 0 | 0 | 1.0 | 1 | 120 |
| `arm_halvard_guard_suit` | Halvard Guard Suit | Halvard Ordnance | body | 12 | 8 | 6 | 0 | −2 | 5.0 | 2 | 1500 |
| `arm_ostrom_weave` | Ostrom Reflective Weave | Ostrom Optical | body | 6 | 14 | 4 | 0 | 0 | 2.0 | 2 | 1600 |
| `arm_sable_chem_suit` | Sable Works Chem Suit | Sable Works | body | 6 | 5 | 16 | 0 | 0 | 3.5 | 2 | 1400 |
| `arm_halvard_visor` | Halvard Tactical Visor | Halvard Ordnance | head | 8 | 6 | 3 | 0 | 0 | 1.5 | 2 | 800 |
| `arm_kestrel_greaves` | Kestrel Issue Greaves | Kestrel Issue | limbs | 6 | 3 | 3 | 0 | −1 | 2.5 | 2 | 700 |
| `arm_chapel_vestment` | Chapel Foundry Vestment | Chapel Foundry | body | 5 | 5 | 5 | 12 | 0 | 2.0 | 2 | 1500 |
| `arm_halvard_plate` | Halvard Breacher Plate | Halvard Ordnance | body | 24 | 14 | 10 | 0 | −10 | 14.0 | 3 | 6000 |
| `arm_ostrom_mirror` | Ostrom Mirror Shell | Ostrom Optical | body | 10 | 26 | 8 | 0 | −3 | 5.0 | 3 | 6200 |
| `arm_sable_widow_suit` | Sable Works Widow Suit | Sable Works | body | 12 | 10 | 26 | 0 | −2 | 4.5 | 3 | 5800 |
| `arm_halvard_breacher_helm` | Halvard Breacher Helm | Halvard Ordnance | head | 14 | 10 | 6 | 0 | −2 | 3.0 | 3 | 2800 |

## 3. Implants

Implants cost **tolerance** points (character has Vitals / 10, minimum 4; a Ghost's native rig costs 0;
Hardline +2) and occupy a slot. Sablier install: list price plus 20 %
surgery fee, 2 % failure. Black clinic (Sink): 60 % of list, 15 %
failure. Resonance implants require the Cantor archetype and Choir
standing +20; rig implants require Cortex 20 (Ghosts start above it).

### 3.1 Standard implants

| ID | Name | Maker | Slot | Tol | Effect | Tier | Price |
|---|---|---|---|---|---|---|---|
| `imp_ostrom_lowlight` | Ostrom Lowlight Eyes | Ostrom Optical | eyes | 1 | sight radius +3 in dark zones | 1 | 600 |
| `imp_sablier_sub_dermal` | Sablier Subdermal Mesh | Sablier | torso | 1 | arm_k +3 | 1 | 700 |
| `imp_sablier_adrenal` | Sablier Adrenal Governor | Sablier | torso | 1 | stamina regen +50 % | 1 | 650 |
| `imp_kestrel_loadframe` | Kestrel Loadframe Spine | Kestrel Issue | spine | 1 | carry weight +15 kg | 1 | 500 |
| `imp_sablier_secure_pocket` | Sablier Secure Pocket | Sablier | torso | 1 | +1 secured inventory slot | 1 | 900 |
| `imp_ostrom_rangefinder` | Ostrom Rangefinder | Ostrom Optical | eyes | 1 | range penalty halved | 2 | 1800 |
| `imp_halvard_reflex_arm` | Halvard Reflex Arm | Halvard Ordnance | arms | 2 | weapon cooldown −10 % | 2 | 2200 |
| `imp_halvard_stabiliser` | Halvard Stabiliser Arm | Halvard Ordnance | arms | 2 | accuracy +8 with kinetic | 2 | 2000 |
| `imp_sablier_shock_sink` | Sablier Shock Sink | Sablier | spine | 2 | shock decay ×2 | 2 | 2100 |
| `imp_sablier_clotting` | Sablier Clotting Glands | Sablier | torso | 2 | chemical damage-over-time halved | 2 | 1900 |
| `imp_sablier_sprint_legs` | Sablier Sprint Legs | Sablier | legs | 2 | sprint tile time 80 ms; stamina cost −20 % | 2 | 2400 |
| `imp_ow_ghost_step` | Old Works Ghost Step | Old Works Collective | legs | 2 | stealth stance sight reduction 60 % instead of 50 % | 2 | 2300 |
| `imp_ostrom_target_lock` | Ostrom Target Lock | Ostrom Optical | head | 2 | target retained through cover; shows target health | 2 | 1700 |
| `imp_sablier_second_heart` | Sablier Second Heart | Sablier | torso | 3 | health +40 | 3 | 5500 |
| `imp_halvard_dermal_plate` | Halvard Dermal Plate | Halvard Ordnance | torso | 3 | arm_k +8, arm_e +4; evasion −3 | 3 | 5200 |
| `imp_sablier_secure_vault` | Sablier Secure Vault | Sablier | spine | 2 | +2 secured slots | 3 | 4800 |
| `imp_sablier_detox_gland` | Sablier Detox Gland | Sablier | torso | 2 | drug crash duration halved; addiction window halved | 3 | 4400 |
| `imp_ow_drone_uplink` | Old Works Drone Uplink | Old Works Collective | head | 2 | Operator: +1 drone slot; others: may run one drone | 3 | 5000 |
| `imp_halvard_heavy_mount` | Halvard Heavy Mount | Halvard Ordnance | arms | 3 | Hardline: heavy weapon cooldown −15 % | 3 | 5800 |

### 3.2 Rig implants

A rig implant lets its owner jack in from anywhere (design §5.2). Ghosts
have a **native rig** equivalent to `imp_rig_native` at no tolerance cost;
they may still install a better one, which replaces it.

| ID | Name | Maker | Slot | Tol | Slots | Effect | Tier | Price |
|---|---|---|---|---|---|---|---|---|
| `imp_rig_native` | Native Rig (Ghost only, built in) | Sablier template | rig | 0 | 3 | jack in anywhere | — | — |
| `imp_rig_ow_jury` | Old Works Jury Rig | Old Works Collective | rig | 1 | 3 | jack in anywhere; trace gain +10 % | 1 | 1200 |
| `imp_rig_sablier_clinical` | Sablier Clinical Rig | Sablier | rig | 2 | 4 | jack in anywhere; integrity +10 | 2 | 3600 |
| `imp_rig_ow_deepwater` | Old Works Deepwater Rig | Old Works Collective | rig | 3 | 6 | jack in anywhere; cell move time −20 %; Silt descent allowed | 3 | 8000 |

Portable rigs (`item_rig_portable_*`, §5) give the same slot counts
without the implant, but only at a terminal and only while carried in a
secured slot.

### 3.3 Resonance implants (Cantor only)

| ID | Name | Maker | Slot | Tol | Effect | Tier | Price |
|---|---|---|---|---|---|---|---|
| `imp_res_first_ear` | Chapel First Ear | Chapel Foundry | head | 1 | unlocks hymns tier 1; Listening +10 | 1 | 900 |
| `imp_res_throat` | Chapel Throat | Chapel Foundry | spine | 1 | unlocks dissonance tier 1 | 1 | 900 |
| `imp_res_second_ear` | Chapel Second Ear | Chapel Foundry | eyes | 2 | hidden cells visible within 2 cells; Listening +15 | 2 | 2600 |
| `imp_res_chord` | Chapel Chord | Chapel Foundry | spine | 2 | hymns affect 8 tiles instead of 6; replaces Throat | 2 | 2800 |
| `imp_res_tremor` | Chapel Tremor | Chapel Foundry | arms | 2 | dissonance abilities +20 % damage | 2 | 2700 |
| `imp_res_ninefold_lattice` | Chapel Ninefold Lattice | Chapel Foundry | head | 3 | unlocks hymns and dissonance tier 3; replaces First Ear | 3 | 7000 |
| `imp_res_tenant_ear` | Chapel Tenant's Ear | Chapel Foundry | eyes | 3 | during Choir Surge: sees all ICE class and integrity; Silt residuals speak first | 3 | 7500 |
| `imp_res_silence` | Chapel Silence | Chapel Foundry | torso | 2 | arm_d +15; immune to knockdown from dissonance | 3 | 4500 |

## 4. Hymns and dissonance (Cantor abilities)

Same cooldown model as weapons (design §5.3). Hymns affect crew members
within 6 tiles (8 with Chord), including the Cantor. Dissonance targets
one actor unless noted. Skill lines *Hymns* and *Dissonance* scale effect
by (1 + skill / 200). Tier 3 requires `imp_res_ninefold_lattice`.

| ID | Name | Kind | Tier | Cast | CD | Effect |
|---|---|---|---|---|---|---|
| `hymn_steady` | Steady | hymn | 1 | 0.5 s | 12 s | crew shock −20 immediately |
| `hymn_mend` | Mend | hymn | 1 | 1.0 s | 15 s | crew health +15 over 5 s |
| `hymn_march` | March | hymn | 2 | 1.0 s | 30 s | crew stamina cost −50 % for 10 s |
| `hymn_ward` | Ward | hymn | 2 | 1.5 s | 40 s | crew arm_all +5 for 12 s |
| `hymn_ninefold` | Ninefold | hymn | 3 | 2.0 s | 90 s | crew: pick up a downed member instantly, once |
| `dis_jam` | Nerve-jam | dissonance | 1 | 0.5 s | 8 s | target weapon cooldowns +50 % for 4 s |
| `dis_stutter` | Stutter | dissonance | 1 | 0.5 s | 10 s | target movement 400 ms/tile for 4 s |
| `dis_shear` | Shear | dissonance | 2 | 1.0 s | 14 s | 25 dissonance damage, +20 shock |
| `dis_hush` | Hush | dissonance | 2 | 1.0 s | 20 s | target cannot use consumables or hymns for 6 s |
| `dis_choir` | Choir | dissonance | 3 | 2.0 s | 60 s | 30 dissonance damage to every hostile within 4 tiles, +30 shock |

## 5. Rigs, programs and Lattice gear

Programs load into rig slots (design §6.3). Program strength scales with
*Programs* skill; trace numbers are per use.

| ID | Name | Maker | Class | Cast | CD | Effect | Trace | Tier | Price |
|---|---|---|---|---|---|---|---|---|---|
| `prg_ow_pick` | Pick | Old Works Collective | attack | 0.5 s | 2 s | 10 ICE integrity damage | +2 | 1 | 150 |
| `prg_ow_shroud` | Shroud | Old Works Collective | shield | 0.5 s | 6 s | absorb 15 for 5 s | 0 | 1 | 200 |
| `prg_ow_echo` | Echo | Old Works Collective | decoy | 1.0 s | 12 s | trace gain −50 % for 8 s | 0 | 1 | 250 |
| `prg_ow_skeleton` | Skeleton | Old Works Collective | key | 1.0 s | 5 s | opens gated cells up to tier 2 | +5 | 1 | 300 |
| `prg_ow_hammer` | Hammer | Old Works Collective | attack | 1.0 s | 4 s | 24 ICE integrity damage | +4 | 2 | 900 |
| `prg_ow_mirror` | Mirror | Old Works Collective | shield | 0.5 s | 10 s | reflect next ICE attack | 0 | 2 | 1100 |
| `prg_ow_lift` | Lift | Old Works Collective | utility | 1.5 s | 8 s | pull data from a room without touching its ICE trigger | +6 | 2 | 1000 |
| `prg_ow_creep` | Creep | Old Works Collective | stealth | 1.0 s | 20 s | ICE activation delayed 4 s on next room entry | 0 | 2 | 950 |
| `prg_ow_loader` | Loader | Old Works Collective | loader | 0 | passive | cast times −20 % | 0 | 2 | 800 |
| `prg_ow_map` | Map | Old Works Collective | utility | 2.0 s | 30 s | reveals room graph of current core | +3 | 2 | 700 |
| `prg_ow_burn` | Burn | Old Works Collective | attack (runner) | 0.8 s | 3 s | 18 integrity damage to a runner in the same cell | +8 (civic) | 2 | 1200 |
| `prg_ow_sledge` | Sledge | Old Works Collective | attack | 1.5 s | 6 s | 50 ICE integrity damage | +8 | 3 | 3800 |
| `prg_ow_null` | Null | Old Works Collective | decoy | 1.0 s | 45 s | trace reset to 0 once; core remembers you | 0 | 3 | 4500 |
| `prg_ow_masterkey` | Masterkey | Old Works Collective | key | 1.5 s | 8 s | opens any gated cell; opens Silt descent | +10 | 3 | 4000 |
| `prg_ow_lantern` | Lantern | Old Works Collective | utility | 1.0 s | 20 s | reveals hidden cells within 3; Silt-safe | +2 | 3 | 3500 |
| `prg_ow_hunterkiller` | Hunter-killer | Old Works Collective | attack | 2.0 s | 15 s | 80 damage to hunter-class ICE only | +6 | 3 | 4200 |

Portable rigs:

| ID | Name | Slots | Wt | Tier | Price |
|---|---|---|---|---|---|
| `item_rig_portable_ow_brick` | Old Works Brick | 3 | 2.0 | 1 | 800 |
| `item_rig_portable_ow_slab` | Old Works Slab | 5 | 2.5 | 2 | 3000 |
| `item_rig_portable_halvard_case` | Halvard Field Case | 6 | 3.5 | 3 | 7000 |

## 6. Drugs

Effect for **duration**, then **crash** (the opposite) for half the
duration. Three doses inside the **window** creates a dependency (crash
becomes permanent until Sablier detox, 400 chits and 10 minutes).

| ID | Name | Maker | Effect | Duration | Crash | Window | Price |
|---|---|---|---|---|---|---|---|
| `drug_sablier_focus` | Focus (labelled) | Sablier | accuracy +10 | 120 s | accuracy −10 | 30 min | 60 |
| `drug_sablier_calm` | Calm (labelled) | Sablier | shock decay ×2 | 180 s | shock decay ×0.5 | 30 min | 50 |
| `drug_sable_redline` | Redline | Sable Works | weapon cooldown −20 % | 90 s | cooldown +20 % | 20 min | 120 |
| `drug_sable_glass` | Glass | Sable Works | evasion +10, sight +2 | 90 s | evasion −10 | 20 min | 130 |
| `drug_sable_brick` | Brick | Sable Works | arm_k +8, stamina cost +20 % | 120 s | arm_k −8 | 30 min | 110 |
| `drug_sable_deepwater` | Deepwater | Sable Works | Lattice: cell move −30 %, trace gain +20 % | 300 s | move +30 % | 30 min | 180 |
| `drug_ow_static` | Static | Old Works Collective | Lattice: integrity +20 | 240 s | integrity −20 | 40 min | 200 |
| `drug_chapel_hush` | Hush (sacrament) | Chapel Foundry | Listening +20; Cantor cast −25 % | 180 s | Listening −20 | 60 min | 150 |
| `drug_ferry_ringdust` | Ring-dust | Ferry-make | stamina regen ×3; health −1/s | 60 s | stamina regen ×0.3 | 15 min | 40 |
| `drug_sable_lullaby` | Lullaby | Sable Works | health +30 over 10 s; movement 400 ms/tile | 30 s | health −10 | 20 min | 90 |
| `drug_sable_chrome` | Chrome | Sable Works | tolerance +1 (temporary; implant installed under it fails when it wears off unless Vitals grew) | 20 min | shock +40 | 24 h | 500 |

## 7. Consumables

Instant, 10 s cooldown per class (design §5.3).

| ID | Name | Maker | Class | Effect | Price |
|---|---|---|---|---|---|
| `con_sablier_patch` | Sablier Med Patch | Sablier | heal | health +25 | 40 |
| `con_sablier_trauma_kit` | Sablier Trauma Kit | Sablier | heal | health +60; 2 s use time | 150 |
| `con_kestrel_ration` | Kestrel Ration Bar | Kestrel Issue | food | stamina +20; removes Ring-dust crash | 10 |
| `con_sable_stim` | Sable Works Stim | Sable Works | stim | stamina full; shock +10 | 45 |
| `con_sablier_neutraliser` | Sablier Neutraliser | Sablier | antidote | ends chemical damage-over-time | 60 |
| `con_ow_cell_charger` | Old Works Cell Charger | Old Works Collective | tool | recharges one energy cell anywhere; 3 uses | 200 |
| `con_ferry_flare_stick` | Ferry-make Flare Stick | Ferry-make | light | sight radius 8 for 3 min in dark zones | 15 |
| `con_halvard_breach_charge` | Halvard Breach Charge | Halvard Ordnance | tool | destroys a locked (not hackable-only) door; 5 s fuse; noise alerts zone | 350 |
| `con_sablier_pickup` | Sablier Pickup Kit | Sablier | revive | pick up a downed crew member in 2 s instead of 5 | 120 |
| `con_kestrel_beacon` | Kestrel Convoy Beacon | Kestrel Issue | tool | during a Convoy event, marks your position to the convoy; the convoy detours | 80 |

## 8. Drones (Operator)

Operators have two drone slots (three with `imp_ow_drone_uplink`). A
drone is an actor that follows or holds, with its own health, evasion,
weapon or tool, and a control range (tiles from the Operator) beyond which
it returns. Destroyed drones are lost; a drone in a secured slot at death
survives.

| ID | Name | Maker | Health | Evasion | Range | Weapon / tool | Tier | Price |
|---|---|---|---|---|---|---|---|---|
| `drn_kestrel_mule` | Kestrel Mule | Kestrel Issue | 60 | 5 | 8 | carrier: +20 kg carry | 1 | 400 |
| `drn_ostrom_eye` | Ostrom Eye | Ostrom Optical | 20 | 25 | 14 | scout: reveals sight radius 6 around itself; silent | 1 | 500 |
| `drn_halvard_sentry` | Halvard Sentry | Halvard Ordnance | 80 | 5 | 6 | kinetic 12 dmg, range 6, CD 1.0 | 2 | 1800 |
| `drn_sable_stinger` | Sable Works Stinger | Sable Works | 35 | 20 | 8 | chemical 8 (+4/s 3 s), range 4, CD 1.2 | 2 | 1600 |
| `drn_sablier_medic` | Sablier Medic | Sablier | 40 | 15 | 6 | heals crew +8/s within 2 tiles | 2 | 2000 |
| `drn_ow_relay` | Old Works Relay | Old Works Collective | 30 | 15 | 10 | terminal on legs: jack in from the drone's tile; drone destroyed = forced jack-out | 3 | 4200 |
| `drn_halvard_hound` | Halvard Hound | Halvard Ordnance | 120 | 10 | 8 | melee 30 kinetic, CD 1.0; hunts a target you mark | 3 | 5000 |
| `drn_ferry_lifter` | Ferry-make Lifter | Ferry-make | 90 | 5 | 6 | carrier: +60 kg; can carry salvage grade `intact` | 3 | 3800 |

## 9. Salvage

Ring-fall spawns salvage nodes in the Scour (design §8.4). Vendors buy at
base price; Ferrymen buy at +20 %; `intact` is not for sale to vendors
because it is the Custodian arc's season contribution.

| ID | Grade | What it was | Wt per unit | Base price | Fabrication use |
|---|---|---|---|---|---|
| `slv_hull` | hull | panels, booms, shielding | 4.0 | 15 | frames, plate, scrap bolts |
| `slv_optics` | optics | lenses, sensors, mirrors | 1.0 | 60 | sights, eyes, energy emitters |
| `slv_power` | power | cells, capacitors, radioisotope units | 2.5 | 80 | energy weapons, cells, drones |
| `slv_compute` | compute | boards, memory, radiation-hardened cores | 0.5 | 120 | rigs, programs, drone brains |
| `slv_intact` | intact | a component that still works | 3.0 | — | season contribution; tier-3 schematics |

Ring-fall yield by Scour ring (outermost is ring 4): ring 1 mostly hull;
ring 2 adds optics and power; ring 3 adds compute; ring 4 is the only
place `intact` lands outside story content.

## 10. Schematics

A schematic plus salvage at a workshop makes one item; *Fabrication*
skill rolls quality ±15 % on the item's main stat. Workshops: Tramyard
(Kestrel, public), the Landing (Ferrymen), Old Works (Unmoored, rigs and
programs only), the Sink (Sable, chemical and melee only).

| ID | Makes | Salvage cost | Skill min | Source |
|---|---|---|---|---|
| `sch_scrap_bolts` | `ammo_scrap` ×20 | hull 1 | 0 | any Ferrymen vendor, 50 |
| `sch_scrap_plate` | `arm_ferry_scrap_plate` | hull 6 | 10 | Ferrymen vendor, 200 |
| `sch_slugthrower` | `wpn_ferry_slugthrower` | hull 4, power 1 | 10 | Ferrymen vendor, 250 |
| `sch_ring_wrench` | `wpn_ferry_wrench` | hull 2 | 0 | Ferrymen vendor, 80 |
| `sch_flare_stick` | `con_ferry_flare_stick` ×5 | power 1 | 0 | Ferrymen vendor, 60 |
| `sch_cell` | `ammo_cell` ×1 | power 1 | 15 | Old Works vendor, 300 |
| `sch_arcpen` | `wpn_ow_arcpen` | power 2, optics 1 | 20 | Old Works vendor, 400 |
| `sch_coilgun` | `wpn_ow_coilgun` | hull 3, power 3, compute 1 | 35 | Old Works, standing +30, 1500 |
| `sch_jury_rig` | `imp_rig_ow_jury` | compute 3, power 1 | 30 | Old Works, standing +30, 1200 |
| `sch_meteor_cannon` | `wpn_ferry_meteor_cannon` | hull 8, power 2 | 40 | Ferrymen, standing +30, 1800 |
| `sch_ringfall_rifle` | `wpn_ferry_ringfall_rifle` | hull 6, optics 3, intact 1 | 60 | Ferrymen, standing +60, 4000 |
| `sch_railpistol` | `wpn_ow_railpistol` | power 4, compute 2, intact 1 | 60 | Old Works, standing +60, 4500 |
| `sch_deepwater_rig` | `imp_rig_ow_deepwater` | compute 6, power 3, intact 2 | 70 | core data, Old Works tier-3 core only |
| `sch_lifter` | `drn_ferry_lifter` | hull 8, power 3, compute 1 | 45 | Ferrymen, standing +40, 2500 |
| `sch_stinger` | `drn_sable_stinger` | hull 2, power 2, compute 1 | 30 | Sable vendor, standing +20, 1000 |
| `sch_etcher` | `wpn_sable_acid_blade` | hull 2, intact 1 | 50 | Sable, standing +50, 3000 |
| `sch_mirror_shell` | `arm_ostrom_mirror` | optics 8, hull 3, intact 1 | 65 | core data, Spire tier-3 core only |
| `sch_hunterkiller` | `prg_ow_hunterkiller` | compute 5, intact 1 | 60 | core data, Silt only |

## 11. Starter kit (end of the Wake, design §4)

| Item | Qty |
|---|---|
| `arm_wake_coverall` | worn |
| `wpn_kestrel_sidearm` | 1 |
| `ammo_9x` | 1 stack (50) |
| `wpn_kestrel_baton` | 1 |
| `con_sablier_patch` | 2 |
| `con_kestrel_ration` | 2 |
| chits | 200 |
| `story_vesper_card` (*Vesper, Tin Halo, Sodium Row*) | 1 |

Ghosts also start with `prg_ow_pick` and `prg_ow_shroud` loaded in the
native rig. Cantors start with `imp_res_first_ear` installed (Sablier's
template came with it) and `hymn_steady`. Operators start with
`drn_kestrel_mule`. Hardlines start with `arm_kestrel_vest` instead of the
coverall.

## 12. Vendor inventories

Price tier: **list** (design §8.2 standing modifiers apply), **member**
(faction members only), **restricted** (standing gate shown). Every
vendor carries ammunition for the weapons it sells and buys back at 40 %
of list within its hourly budget.

| Vendor | Zone | Stock | Tier |
|---|---|---|---|
| Kestrel Depot Counter | Tramyard | `wpn_kestrel_sidearm`, `wpn_halvard_hv7`, `wpn_kestrel_flare_pistol`, `wpn_kestrel_baton`, `arm_kestrel_vest`, `arm_kestrel_helmet`, `con_kestrel_ration`, `con_kestrel_beacon`, `imp_kestrel_loadframe` | list |
| Kestrel Convoy Armoury | Tramyard | `wpn_kestrel_convoy_smg`, `arm_kestrel_greaves`, `wpn_kestrel_gate_gun` (standing +60) | member |
| Halvard Public Concourse | The Spire | `wpn_halvard_hv7`, `arm_halvard_visor`, `imp_halvard_stabiliser`, `wpn_halvard_shock_baton` | list |
| Halvard Security Issue | The Spire | `wpn_halvard_hv9`, `wpn_halvard_dmr`, `arm_halvard_guard_suit`, `imp_halvard_reflex_arm`, `drn_halvard_sentry`; `wpn_halvard_hv12`, `wpn_halvard_anvil`, `arm_halvard_plate`, `arm_halvard_breacher_helm`, `wpn_halvard_ram`, `imp_halvard_dermal_plate`, `imp_halvard_heavy_mount`, `drn_halvard_hound` (standing +60) | member |
| Ostrom Showroom | The Core | `wpn_ostrom_pinlight`, `imp_ostrom_lowlight`, `imp_ostrom_rangefinder`, `drn_ostrom_eye`, `ammo_cell` | list |
| Ostrom Contract Sales | The Spire | `wpn_ostrom_lance`, `wpn_ostrom_arc_projector`, `arm_ostrom_weave`, `imp_ostrom_target_lock`; `wpn_ostrom_scalpel`, `wpn_ostrom_sunlance`, `wpn_ostrom_pulse_carbine` (Halvard or Sablier member, standing +50) | restricted |
| Sablier Clinic (any) | Vatside, faction halls | all Sablier implants, `con_sablier_patch`, `con_sablier_trauma_kit`, `con_sablier_neutraliser`, `con_sablier_pickup`, `drug_sablier_focus`, `drug_sablier_calm`, detox, surgery | list |
| Sablier Wake Outfitter | Vatside | starter kit items, `arm_wake_coverall` | list |
| Warden Quartermaster | The Core | Civic Pattern equivalents of `arm_halvard_guard_suit`, `wpn_halvard_hv9`, `wpn_halvard_shock_baton` (same stats, blue) | member |
| Sink Market | The Sink | `wpn_sable_streetsweeper`, `wpn_sable_spitter`, `wpn_sable_shiv`, `arm_sable_leathers`, `con_sable_stim`, all Sable drugs, `ammo_gel`, `ammo_needle` | list |
| Sable Works Back Room | The Sink | `wpn_sable_needler`, `wpn_sable_pump`, `wpn_sable_torch`, `wpn_sable_machete`, `arm_sable_chem_suit`, `drn_sable_stinger`; `wpn_sable_widow`, `arm_sable_widow_suit`, `sch_etcher` (standing +50) | member |
| Black Clinic | The Sink | any standard implant at 60 % list, 15 % failure; `drug_sable_chrome` | list |
| Old Works Bench | Old Works | `wpn_ow_arcpen`, all tier-1 and tier-2 programs, `item_rig_portable_ow_brick`, `item_rig_portable_ow_slab`, `imp_rig_ow_jury`, `con_ow_cell_charger`, `drug_ow_static`, `sch_cell`, `sch_arcpen` | list |
| Old Works Deep Bench | Old Works | `wpn_ow_coilgun`, `wpn_ow_arc_knuckles`, `imp_ow_ghost_step`, `imp_rig_sablier_clinical` (stolen stock), `imp_ow_drone_uplink`, tier-3 programs; `wpn_ow_railpistol`, `sch_railpistol`, `drn_ow_relay` (standing +60) | member |
| Chapel Almoner | Chapel Ward | `arm_chapel_vestment`, `drug_chapel_hush`, `imp_res_first_ear`, `imp_res_throat` (Cantor, Choir standing +20) | restricted |
| Chapel Foundry | Chapel Ward | `wpn_chapel_tuning_fork`, all tier-2 resonance implants; `wpn_chapel_choir_bell`, `wpn_chapel_hand_bell`, tier-3 resonance implants (standing +60) | member |
| The Landing Trade Post | The Landing | `wpn_ferry_slugthrower`, `wpn_ferry_wrench`, `arm_ferry_scrap_plate`, `con_ferry_flare_stick`, `drug_ferry_ringdust`, `ammo_scrap`, tier-1 schematics; buys salvage at +20 % | list |
| Ferry's Own | The Landing | `wpn_ferry_meteor_cannon`, `drn_ferry_lifter`, tier-2 and tier-3 Ferry-make schematics (standing gates as listed) | member |
| The Tin Halo (Vesper) | Sodium Row | contracts, rumours, `drug_sable_glass`, `con_sable_stim`, one rotating tier-2 item per day from any maker at +40 % | list |

## 13. Apartments

Rented in the Terraces per real-time week (design §8.7).

| ID | Name | Storage slots | Core tier | Rent / week |
|---|---|---|---|---|
| `apt_terrace_cell` | Terrace Cell | 40 | 1 | 300 |
| `apt_terrace_flat` | Terrace Flat | 80 | 2 (upgradeable to 3, 2 000 chits) | 900 |
| `apt_terrace_corner` | Corner Flat | 120 | 3 | 2 200 |

All apartments include a safe (banked chits), a terminal, and a door with
a tier-1 lock (upgrade to tier 3, 800 chits). Eviction after two weeks
lapsed; impound reclaim fee 10 % of stored value.

## 14. Balance notes

- **Time to kill.** At equal grade with tier-matched gear, an uncovered
  target should drop in 6 to 10 seconds of sustained fire; cover of 2 or
  more should stretch that past 15 seconds. Worked example, tier 1:
  `wpn_halvard_hv7` (16 dmg, 1.0 s CD, acc 55) against a grade-5 Ghost
  (Vitals 25, health 100, evasion 20, `arm_sable_leathers` arm_k 5) at
  Kinetic skill 20: to-hit 55 + 10 − 20 = 45 %; damage 16 × 1.1 − 5 ≈
  12.6; expected 5.7 per second; about 17 s uncovered. That is *too slow*
  for the pillar, and the fix in the balance slice should raise tier-1
  base accuracy by about 15 (starter gear should hit 60 % of the time
  against starter evasion) rather than raise damage. Tier 2 and 3 already
  land inside the window against tier-matched armour.
- **Shock.** Half of damage becomes shock; a target in the 6–10 s window
  reaches shock 80 (slowed) around second 5, which is the intended "you
  are losing, decide now" signal.
- **Price ladder.** A grade-10 character with about four hours of play
  should have earned 6 000 to 9 000 chits net of clone debt and ammo,
  enough for one tier-2 weapon, one tier-2 armour piece, and one tier-2
  implant with surgery. Tier 3 is a grade-18-plus purchase or a faction
  member's fabrication project.
- **Ammunition** is a real sink: a tier-2 rifle burns about 120 chits of
  ammo per hour of contested play.
- **Rig economy.** A Ghost never needs to buy a rig; every other archetype
  pays 1 200 chits and one tolerance point to jack in away from a
  terminal, which is the intended asymmetry.
- **Dissonance** ignores kinetic, energy and chemical armour entirely;
  only `arm_d` reduces it, and only two items grant `arm_d`. Cantors are
  the anti-Hardline, and the Choir vestment is the counter.
- **Drugs.** Every Sable drug's effect is worth roughly one tier of gear
  for its duration; the addiction window is the price. Sablier's labelled
  drugs are weaker and the window is the same, on purpose: the only safe
  thing about them is the label.

## 15. Passes, charges and story items

Items other documents reference that do not fit the tables above. Passes
and charges are bought at faction vendors at the standing shown; story
items are contract objectives (class `data` or `misc`), weigh 0.5, are
secured by default, and cannot be sold.

| ID | Name | Class | Source | Wt | Price | Line |
|---|---|---|---|---|---|---|
| `key_containment_charge` | Containment Charge | consumable | Halvard vendor, standing +50 | 1.5 | 1 500 | Cuts a core's power from any tile within 3 of its hardware, through the wall. Single use. Halvard's answer to a locked server room. |
| `key_curfew_pass` | Curfew Pass | pass | Warden vendor, standing +30 | 0.1 | 400 | Admits the holder to the Core during a Curfew. Expires after 7 days. Marked holders are refused at the line. |
| `key_row_pass` | Row Pass | pass | Red Sable vendor, standing +30 | 0.1 | 250 | Lifts a Tin Halo or Sodium Row bar ban. The Row remembers the ban; the pass makes it look away. |
| `key_visitor_pass` | Spire Visitor's Pass | pass | Halvard vendor, or lifted from the Gatehouse pass registry | 0.1 | 600 | Admits one non-Halvard character to the Spire Mezzanine for 30 minutes. |
| `key_silt_beacon` | Silt Beacon | consumable | Choir vendor, standing +30 | 0.5 | 900 | Marks a descent cell for the crew for one hour; crew members see it on the sector view from any cell. |
| `key_ringfall_chart` | Ring-fall Chart | data | Ferrymen Charter rank (+70) reads it at the Landing | 0.2 | 1 200 | Names the next Ring-fall ring one hour early. Sells to anyone who did not earn it. |
| `prg_choir_cantillation_1` | Cantillation I | program (attack) | Choir vendor, Cantor only, tier 2 | — | 1 000 | 0.8 s cast, 4 s cooldown, 20 ICE damage plus Resonance / 5, +4 trace. The Choir's programs are sung, not run. |
| `prg_choir_cantillation_2` | Cantillation II | program (attack) | Choir vendor, Cantor only, standing +50, tier 3 | — | 3 600 | 1.2 s cast, 6 s cooldown, 40 ICE damage plus Resonance / 3, +6 trace. Cantillation ICE takes double. |
| `prg_ow_residual_fragment` | Residual Fragment | program (utility), single use | Unmoored Deep rank (+90) | — | not sold | Loads a dead runner's hands for one run: +25 Programs skill until jack-out, then the fragment is gone. |
| `story_vesper_card` | Vesper's Card | misc | starter kit | 0.1 | — | A contract card. *Vesper, Tin Halo, Sodium Row.* |
| `story_telemetry_unit_warm` | Warm Telemetry Unit | data | Halvard Season 1 | 0.5 | — | Site Zero salvage that is still warm. |
| `story_halvard_seal_beacon` | Seal Beacon | misc | Halvard Season 1 | 0.5 | — | A monitor beacon Halvard wants planted at the seal. |
| `story_sealed_template_canister` | Sealed Template Canister | misc | Sablier Season 1 | 0.5 | — | A canister from below the outworks. Sablier does not say what is in it. |
| `story_template_shield_rig` | Template Shield Rig | misc | Sablier Season 1 | 0.5 | — | Shields walked templates from Sablier's recall signal. |
| `story_resonance_beacon` | Resonance Beacon | misc | Choir Season 1 | 0.5 | — | Quell's beacon for a cell that should not exist. |
| `story_listening_stake` | Listening Stake | misc | Ferrymen Season 1 | 0.5 | — | A stake the Ferrymen drive at a conduit head to hear it hum. |
| `story_residual_fragment_99b` | Residual Fragment 99-B | data | Unmoored Season 1 | 0.5 | — | A second copy of Ninety-Nine that says one thing. |
| `story_unmoored_drop_cache` | Drop Cache | misc | Unmoored Season 1 | 0.5 | — | The cache under Terrace Nine. |
| `story_authority_image_copy` | Authority Image Copy | data | Halvard Season 2 | 0.5 | — | A copy of the Dispatcher's process image. |
| `story_holt_manual_schedule` | Holt's Hand Schedule | data | Kestrel Season 2 | 0.5 | — | A convoy schedule written by hand. Late, unreliable, human. |
| `story_choir_beacon_2` | Choir Beacon II | misc | Choir Season 2 | 0.5 | — | A beacon for the shaft head. |
| `story_ferrymen_repeater` | Ferrymen Repeater | misc | Ferrymen Season 2 | 0.5 | — | A repeater for the Far Relay. |
| `story_stuck_door_package` | Stuck-door Package | misc | Vesper's first contract | 0.5 | — | A package behind a door that sticks. |

## Glossary

Glossary: merged into 07-glossary.md.
