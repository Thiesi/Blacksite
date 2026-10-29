# P4 view semantics acceptance

This slice implements architecture 5.4, 5.5.3 and 5.5.4. It carries
presentation facts without changing simulation rules or the current
renderer. Codex (GPT-6) implements the Sonnet-assigned slice.

## Disclosure and compatibility

- Actor class and speech role use one caller-specific presentation
  query. `presents` is optional validated NPC content. Reveals belong
  to the live NPC instance and caller id, including attacks against a
  caller's drone. Target selection, weapon warning, a legal shot and
  applied harm record the reveal without reading presentation data.
- Covered NPC names, target faction and nearby relations do not reveal
  the true allegiance. Without a cover-name field, a covered NPC uses
  the cover class as its displayed name. Other callers retain the cover.
- New actor flags and glyph ids leave the old glyph unchanged. The
  registry contains `actor-drone` (`τ`); a later renderer selects it.
  Object roles describe their kind or the relay's committed owner;
  `legacy_role` preserves today's object style.
- `me.district` and `me.pvp` accompany zone, Lattice and menu views.
  PvP eligibility describes this body's location and grade protection,
  independently of any particular opponent or action permission.
- A sector's optional theme id defaults to its existing district id.
  Links carry the already disclosed endpoint labels. Private core cells
  report `private`, never a resident id. Black-ICE marking comes only
  from this caller's completed survey observations of the live instance.
- Every authored log emitter calls `Session.emit` with a required kind.
  Speech requires a displayed name and presented class. Transport replay
  preserves these fields and precedes new attach-time place emission.
  Crew restart notices use the existing toast
  surface and stay out of world history. Ambient generation remains P8.

## Baselines

Only `wake_hall_80x24` and `wake_hall_132x50`, including their 16, 256
and truecolor style companions, change: the previously empty first log
row now reads `[zone] You wake on a gurney under a number.` This is the
slice's specified first-entry place line. The existing toast stays.
Every other glyph/style golden and the mechanics baseline stay intact.
No map, balance, E dispatch or human approval changes here.

## Playable acceptance

Use a private local node with the source-matched installed wheel and
registered native stdio door. Run `scripts/accept_p4_netbbs.py` with
`--root` naming a new directory, `--door-python` naming that wheel's
interpreter, and `--show` to display the received 16-colour ANSI.

1. Create a wide-name caller with ordinary keys. Enter Wake Hall. The
   zone metadata includes district, PvP eligibility and actor flags.
2. Open Ctrl-P scrollback. The first-entry place sentence is present,
   tagged `place` in authoritative history; the crew restart is absent.
3. Return, walk through the corridor, explicitly skip training with B,
   and walk to the tutorial terminal. No position or funds are assigned.
4. Press J. The usual Lattice appears with sector theme, link labels and
   owner/tier on known core cells. Press J to return, then leave cleanly.

The script runs both 80x24 and 132x50 in all three colour tiers through
Telnet into NetBBS native stdio. The existing full native matrix covers
the other subsystems and transports independently. Deterministic tests
cover per-caller disguise and survey disclosure; this ordinary live
walk does not manufacture disguised NPCs or black ICE.

## Evidence

The [evidence index](captures/p4-view-semantics/README.md) contains 18
hosted text captures and small local/hosted receipts. The full local
root run passes 1,651 tests with one skipped; the strict packet passes
99 cases. Local and hosted native runs each pass all six size/tier
cases. The post-review chat/disclosure run passes 35 tests, including
the production retaliation-hook regression.

Raw ANSI and style JSON remain in the P4 acceptance CI artifacts, named
`p4-view-semantics-80x24` and `p4-view-semantics-132x50`. The manifest
records exact run/artifact ids, hashes, PR head and actual synthetic
merge execution SHA, whose tree is verified identical to the source.
Local raw captures remain outside Git. Final-head CI and technical
review remain required. Native output is engineering evidence, not
presentation approval or a performance gate.
