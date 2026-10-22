# Apartments and protected impound

S18 supplies the housing engine. The playable ten-zone hub has no live
letting terminal or apartment doors yet. S25 commissions the Terraces
lobby and at least 24 door anchors. Do not claim fixture locations are
production content.

A legally discharged character may rent one home: grade 5 or 90 calendar
days since the identity's first decant. Signing pays one real-time week.
Weekly invoices use bank chits first, then hand, as a single payment.
Rent is checked on login, room interactions and private-core access.
There is no background rent timer. An invoice freezes when issued; relay
changes cannot rewrite it. Two full weeks after the first unpaid due date
end the lease. An already expired lapse cannot be rescued by a late
balance change.

| Class | Slots | Protected slots | Core | Weekly rent |
|---|---|---|---|---|
| Terrace Cell | 40 | 20 | 1 | 300 |
| Terrace Flat | 80 | 40 | 2; upgrade to 3 for 2,000 | 900 |
| Corner Flat | 120 | 60 | 3 | 2,200 |

At your assigned door, E enters. Storage is `*`, the safe is `$`, the bed
is `b` and the terminal uses its normal symbol. Stand on or beside an
object and press E. The bed opens home management: rent status, core and
lock upgrades, replacement key, intrusion log, surrender, exit and safe
logout. Esc/B closes menus without making a choice. Surrender asks for
Y only after you select it.

Storage transfers whole instances/stacks and keeps quality, charges,
ammunition, drone condition and secured status. T switches deposit and
withdraw; S in withdrawal view secures/unsecures in place. Half the listed
capacity can be protected. Carried secured capacity is independent and
still includes implant bonuses; a full destination refuses the transfer
without silently unsecuring anything. Only unsecured, unbound stored
units appear in the private-core manifest. S15's one-unit theft limit
belongs to the physical home for a rolling 24 hours, across tenancies.

The safe is a separate banked account. It survives clone settlement;
rent uses bank and hand, without spending safe chits. Eviction moves
stored instances and safe chits to protected personal impound. Any bank
offers Personal impound. Reclaim fees are 10% of catalog list value,
including stack/ammunition pack counts, rounded halves up. Quality never
rerolls. Impounded chits return to the bank free. Surrender moves goods
to impound without a fee. S23 will append fee-free market deliveries.

Signing includes a physical key. Residents enter without carrying it.
Someone else with a matching current key gets only a 30-second delivery
vestibule; they cannot use storage, safe, terminal or bed. The 800-chit
tier-3 lock upgrade replaces tier-1 keys and visitor grants. Passkey is a
tier-3 program and can still open the vestibule. No visitor method grants
resident privileges. Old tenancies' keys expire. Resident bodies and
drones in private room tiles are hidden from outside sight and scouting.

S21 supplies `Apartments.rent_modifier(player, invoice_due_utc)` and
`private_core_ice_slots(player)`, both neutral by default. The extra ICE
slot adds a Tripwire; the relay owner must refresh affected private cores
when that benefit changes. Keep these effects out of paid invoices.
S28 can invoke `ensure_rent(player_id)` after an authorized clock advance;
it must let queued transactions settle before reporting reconciliation.

Native acceptance:

```powershell
$env:PYTHONPATH = "$PWD/src"
& <NetBBS-venv>/Scripts/python.exe scripts/accept_s18_netbbs.py `
  --root .test-tmp/native-s18 --door-python <Blacksite-venv>/Scripts/python.exe --show
```

The probe registers an ordinary native stdio door and sends real terminal
keys over Telnet at 80x24 and 132x50, with wide names and 16 colours.
Fixtures are explicit: three anchors and letting/impound on spare Wake
floors, grade 5, signing funds, a 109%-quality HV-7, reclaim funds and a
housing-only injected UTC clock. It proves 300-chit signing, storage,
visitor rejection, bed logout/reconnect, eviction after 22 days without
rent funds and 34-chit reclaim. Results, screen text and ANSI transcripts
are written beneath the supplied root. S28 still owns production clock
tooling; S25 must repeat the flow on actual Terraces geography.
