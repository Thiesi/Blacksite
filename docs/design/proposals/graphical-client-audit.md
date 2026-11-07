# Could Blacksite have a different visual client? An audit (proposal input)

**Status:** input for a later owner decision. Nothing here is approved or
planned, apart from S41. Written by the technical lead, 2026-11-07, at the
owner's request, on `main` around e0cfc7d.

**How far to trust it.** An agent read the code and reported it; nothing
was run or measured. I checked the main claims against the code: unknown
frames, terminal requirements, authentication and missing facing data.
Everything else is one careful reading. Code cited here will drift.

## Why this exists

After the first Sodium Row playtest the owner said: "I wanna see it all!"
The owner's concern is broader than one view. Blacksite competes for
people's time with games that look far better, and people judge a game
partly by how it looks. The owner might one day want a different visual
subsystem, a proprietary client or a stand-alone version, and doesn't yet
know. So the question was whether the architecture allows that without
throwing away what Blacksite is and how it feels.

## The answer

**Yes.** The door holds no game rules. The server sends no terminal colour
codes, and its menus are structured data. What makes Blacksite feel like
Blacksite lives on the server: the rules, factions, the Row's truce, the
persistent world and the short session.

The architecture isn't the main obstacle. **Art production and leaving
NetBBS are.**

## What's already in good shape

- **A graphical client on the same machine could connect today** by
  claiming to be a large terminal. That gives it no extra sight, because
  sight doesn't depend on the size it claims.
- **Disclosure is server-side.** Tiles, actors, objects, hidden exits and
  covered NPCs are masked before sending. A client can't see what it was
  never sent.
- **Input is half-ready.** Most actions exist as named intents, and the
  test bot plays through them. A few paths work only by keypress: the
  character sheet, the Wake briefing and city-map paging.

## What a graphical client would lack

| Gap | Today |
|---|---|
| Shape of the world | No heights, wall facing or sign facing. Opacity, passability and cover stay on the server, and the door hardcodes its own opaque list. |
| Appearance | All NPCs share one symbol. Only class, role and colour differ. No light data. Audio is an unsent text field. |
| Animation | The server sends snapshots at up to 10 per second, not events. Walking could be inferred from position changes. An attack could only be keyed from log text. Frames carry no tick number. |
| Camera | The view is tied to terminal size, which also drives text wrapping. Terrain can end 4 tiles ahead near a map edge. |
| Proportions | One tile is one terminal cell, and cells are tall. Drawn square, places look stretched. Fixing that is content work. |
| Long views | Sight is 8 to 13 tiles, so figures would pop in. Raising it changes a rule, and doubling the radius costs roughly eight times as much per sight rebuild. |
| Text | Some hints are prose with key names in them, and some text is wrapped for a width. Menu actions use a key as their identity. |

None of these strictly blocks a client. They limit how good it could look.

## Leaving NetBBS is the big one

Today NetBBS supplies the user's identity, handle, guest exclusion and
timezone, and the door enforces the session limit. One shared door secret
authenticates to the service, so whoever holds it can claim to be any user.
That's fine on one machine, and not on the internet. The socket is local,
with no encryption.

A stand-alone version would need accounts and per-user login, an encrypted
public connection, limits before login, moderation tools (`bans` is read,
but I found nothing that writes to it), handle rules, a way to deliver art,
and support for mixed client versions. It would also need players to find
it, where a door game's audience already exists. That's a project of its
own, and has nothing to do with graphics.

## What would keep the option open

All additive, with no rule changes. Costs are the audit's rough estimates.

1. **Send basic world facts:** tile opacity and passability, actor facing,
   your own position. About 10 lines.
2. **Separate camera size from text size.** About 20 lines.
3. **Doors ignore unknown frames.** About 5 lines plus tests. **Filed as
   S41.** It also makes new frames safer.
4. **Time and cause on the wire:** a tick number on frames, and structured
   combat events alongside the log text. About a day.
5. **An intents-only playthrough test,** then close the gaps it finds. About
   a day.

Only number 3 is scheduled. The others wait for the steps below, because
they only matter if a client is worth pursuing.

## How to explore this without betting anything

Cheapest first, none of it touching the game or the queue:

| Step | What it answers | Cost |
|---|---|---|
| Two first-person frames of the Row, plain and dressed | Does seeing it deliver what the owner imagines? | Hours to about a day |
| This audit | Is the server neutral enough? | Done |
| A thin prototype client: one street, real server, read-only | Does the Row still feel like the Row in a graphical view? | Days, by a rough guess |
| An art test: one street's assets, made the way we'd really make them | Can we make it look good, and what does a district cost? | Unknown. This is the one that could change the answer |

## Points to keep in mind

- **Art is the hard limit.** Models, textures and animation are where 3D
  games spend their money. There's no evidence yet that this team can make
  them at quality and at scale.
- **Don't try to beat WoW on its own ground.** A strong, achievable style
  has to do the work that budget does elsewhere. The SPARE PARTS sign made
  the owner want more without any 3D.
- **Some of the feeling may come from the text.** Rendering a place pins it
  down, and a poor 3D Row could feel smaller than the one in your head.
- **This rests on one player so far,** who knows the design better than
  anyone. A newcomer's reaction would be better evidence.

## Standing rule until this is decided

Don't make a graphical client needlessly hard. New server data should
describe the world, not terminal layout. The owner's October scope (D-T11)
stands, and wider 3D is decided after a playtest of the final build.

## What the audit didn't check

No sizes or timings were measured. Not read: the Lattice view beyond a few
lines, most subsystem menus, whether every action has an intent, terminal
UI canon, the NetBBS repository, and tests beyond the frame fixtures. The
first-person spike's branch (`design/presentation-v1`) is stale and was read
only in part.
