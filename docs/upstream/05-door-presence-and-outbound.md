# 05 — Door name in who-is-online, and a narrow outbound hook

**NetBBS issue:** (to be filled in when filed)
**Blocks:** nothing. Blacksite S28 has an optional step behind it.
**Recommended model for the NetBBS side:** Opus 5 for the outbound hook (touches the capability model discussed under issue #200 in design doc §16); Sonnet for the presence half alone.

## The gap

Two separate, small things:

1. **Presence.** NetBBS's activity and who-is-online show a caller as
   "in a door" (to be verified in `netbbs.activity`); they do not show
   which door. For a multiplayer door, "3 callers in Blacksite" on the
   main menu is the single best recruitment tool the game can have on a
   BBS.
2. **Outbound.** A door has no way to tell the BBS anything. Blacksite
   would like, once per season, to post the season's Chronicle entry to
   a SysOp-chosen board, and optionally to post relay-capture one-liners
   to a chat channel. Design doc §16 (issue #200 notes) already sketches
   the right shape: a capability-scoped service identity minted for the
   door, not the player's own account level.

## Requested change

1. Include the door's registered name in the activity record for a door
   session and show it in who-is-online and the SysOp status overview.
2. Provide a minimal outbound capability: a per-door, SysOp-enabled
   allowlist of board or channel targets, and a small file-drop or
   socket protocol the door can use to post plain text there as the
   door's service identity, rate-limited, audit-logged, off by default.

## Non-goals

No door-driven reads of BBS data, no mail, no user lookups.

## What Blacksite does meanwhile

The Chronicle lives inside the game; the SysOp can export it with
`blacksite admin export chronicle` and post it by hand.
