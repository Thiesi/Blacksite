# Upstream requests to NetBBS

Blacksite is developed as a third-party native door: no commit access to
NetBBS, no control over its release cycle. Everything the game needs
from the platform is written up here first and then filed as an issue in
the NetBBS repository (`Thiesi/NetBBS`). Each file below is one request;
its header records the NetBBS issue number once filed and which
Blacksite slices depend on it.

| # | Request | Blocks | Filed as |
|---|---|---|---|
| 01 | Door services: supervised long-lived companion process per door | S31 (target integration); S05 provides the interim | [Thiesi/NetBBS#466](https://github.com/Thiesi/NetBBS/issues/466) |
| 02 | Per-door CPU and wall-time limits for service-backed doors | none hard; S30 UX, S29 load budget | [Thiesi/NetBBS#467](https://github.com/Thiesi/NetBBS/issues/467) |
| 03 | Forward terminal resize to running native doors | none; S04 handles the static case | [Thiesi/NetBBS#468](https://github.com/Thiesi/NetBBS/issues/468) |
| 04 | Enrich `door_info.json` (Unicode preference, timezone, transport, node identity, API version) | none hard; S04 reads what exists, S32 federation audit | [Thiesi/NetBBS#469](https://github.com/Thiesi/NetBBS/issues/469) |
| 05 | Show the door name in who-is-online and a narrow outbound hook (post to a board) | none; S28 optional | [Thiesi/NetBBS#470](https://github.com/Thiesi/NetBBS/issues/470) |
| 06 | Third-party door install path: interpreter-module preset and guide section | none; S31 documents the manual path | [Thiesi/NetBBS#471](https://github.com/Thiesi/NetBBS/issues/471) |

Rules for this directory:

- A request describes the platform gap, why Blacksite needs it, the
  smallest change that closes it, and what Blacksite does meanwhile. It
  does not contain NetBBS code.
- Once filed, add the issue URL to the file header and do not edit the
  request text further; discussion happens on the NetBBS issue.
- If NetBBS declines a request, record the decision here and keep the
  interim path permanently.
