# NPCs and patrols

The ten-zone hub now has data-driven residents, couriers, guards and
service attendants. `Tab` cycles visible targets; colour is supplemented
by `!` hostile, `~` neutral and `+` allied in NEARBY. Targeting alone has
no legal consequence. Freelance callers remain neutral unless they
provoke a patrol or enter a declared hostile perimeter.

Refused attacks in a safe zone issue a Warden warning within two seconds,
bring two local responders and record ten minutes of heat. Repeated
attempts refresh that deadline. Heat persists across reconnect/restart;
Curfew's future integration doubles new duration rather than damage.
Patrols pursue heat outside protection. They cannot hurt a body in a
safe zone or pocket, and stop pursuing once heat/provocation expires.
Sodium residents call local Sable guards. NPC attacks use the shared
two-second threat warning and physical safety checks.

Summoned responders drop no loot and award no XP. First heat saves at
once; repeated refusals coalesce warnings and saves to one per second,
while retaining the live deadline. A crash can shorten the final refresh
by less than a second. Nonfatal HP/shock updates follow architecture
6.2's five-second player checkpoint; down/death, spent goods and action
cooldowns remain immediate.

Ordinary NPCs return after their authored respawn delay. Their loot and
dead-slot deadline commit together. A failed save publishes no loot.
Zones dormant for thirty minutes rebuild ordinary actors on return;
named service anchors remain. Public counters/vats do not depend on a
killable attendant being present. No NPC XP is awarded until S16.

The Wake's owner-only drone now uses a `per_player` spawner. Its shots
cannot kill, another caller cannot see/interfere with it, and B skips.
Training never grants XP, caches or clone debt.

Run deterministic checks from the repository root with `pytest`. For
the mandatory live proof, use the NetBBS interpreter in a real terminal:

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
& ../NetBBS/.venv/Scripts/python.exe scripts/accept_s11_netbbs.py `
  --root C:/Temp/blacksite-s11-proof `
  --door-python .venv/Scripts/python.exe --show
```

Use an unused private root. The probe registers a real native stdio door,
walks the real maps, records ANSI captures at 80x24 and 132x50, and waits
out the actual ten-minute heat deadline at each size. It checks local
Sable response and production authenticated admin status with all ten
hub zones active. It uses no player teleports or progression/funding
fixtures. Dormant catch-up and restart safety use deterministic tests.
This establishes operation through the node, not human fun or balance.
