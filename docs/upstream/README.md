# Upstream requests to NetBBS

Blacksite is developed as a third-party native door: no commit access to
NetBBS, no control over its release cycle. Everything the game needs
from the platform is written up here first and then filed as an issue in
the NetBBS repository (`Thiesi/NetBBS`). Each file below is one request;
its header records the NetBBS issue number and released outcome. The six
original requests are closed and shipped; their original proposal text
below each header is historical, not the current API specification.

Verified 2026-10-22 against released NetBBS v7.33.0 and its guide/source;
see [issue #56 catch-up](../plan/01-netbbs-platform.md) for pinned sources,
Blacksite ownership and the supported NetBBS >= 7.45.0 release baseline.
The initial implementation was NetBBS v7.3.0, PRs
[#499](https://github.com/Thiesi/NetBBS/pull/499) and
[#506](https://github.com/Thiesi/NetBBS/pull/506).

| # | Request | Original consumer (platform work now released) | Filed as |
|---|---|---|---|
| 01 | Door services: supervised long-lived companion process per door | S31 (target integration); S05 provides the interim | [Thiesi/NetBBS#466](https://github.com/Thiesi/NetBBS/issues/466) |
| 02 | Per-door CPU and wall-time limits for service-backed doors | none hard; S30 UX, S29 load budget | [Thiesi/NetBBS#467](https://github.com/Thiesi/NetBBS/issues/467) |
| 03 | Forward terminal resize to running native doors | none; S04 handles the static case | [Thiesi/NetBBS#468](https://github.com/Thiesi/NetBBS/issues/468) |
| 04 | Enrich `door_info.json` (Unicode preference, timezone, transport, node identity, API version) | none hard; S04 reads what exists, S32 federation audit | [Thiesi/NetBBS#469](https://github.com/Thiesi/NetBBS/issues/469) |
| 05 | Show the door name in who-is-online and a narrow outbound hook (post to a board) | none; S28 optional | [Thiesi/NetBBS#470](https://github.com/Thiesi/NetBBS/issues/470) |
| 06 | Third-party door install path: interpreter-module preset and guide section | none; S31 documents the manual path | [Thiesi/NetBBS#471](https://github.com/Thiesi/NetBBS/issues/471) |

| Request | Released outcome and difference from proposal | Blacksite consumer |
|---|---|---|
| 01 | v7.3.0: one service, exact five-key schema, own memory/no CPU ceiling; install-dir backup is opt-in/unquiesced/manual restore | S31 supervisor; S28 consistent snapshots |
| 02 | v7.3.0: `time_limit`/`cpu_seconds` 0-86400, zero opts out of node ceiling; finite CPU limit can SIGKILL without warning | S29 measured budget; S30 optional deadline; S31 explicit preset |
| 03 | v7.3.0: rewritten door info and opt-in SIGUSR1 for native stdio resize | S04 already supports it; S31 real acceptance |
| 04 | v7.3.0/API 3, not requested API 2: metadata includes node_id, no node_fingerprint; session limit absent when unlimited | S30 preference/limit gaps; S31 API gate; S32 identity audit |
| 05 | v7.3.0 presence/board file drops; v7.12.0/API 4 live chat; v7.31.0/API 5 events/standings. Outbound requires minimum play level zero | S21/S26 semantic facts; S31 publicity deferred under registered-only default |
| 06 | v7.3.0: native Python-module preset and third-party installation guide | S31 uses released import/guide contract |

Rules for this directory:

- A request describes the platform gap, why Blacksite needs it, the
  smallest change that closes it, and what Blacksite does meanwhile. It
  does not contain NetBBS code.
- Once filed, add the issue URL to the file header and do not edit the
  request text further; discussion happens on the NetBBS issue. Header
  status/outcome annotations may be updated with verified release facts.
- If NetBBS declines a request, record the decision here and keep the
  interim path permanently.
