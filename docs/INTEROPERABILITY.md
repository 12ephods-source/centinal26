# Automation OS A2A / MCP interoperability boundary

Status: `HOST_CONTRACT_CANDIDATE / NOT_CONNECTED_BY_CONTRACT`

This module gives the existing `a2a` and `mcp` federation entries typed capability, authentication, state, health-lease, and route-eligibility contracts. It does not add a network client, credentials, remote executor, or authorization source.

The existing federation catalog remains authoritative. Both `a2a` and `mcp` are `NOT_CONFIGURED` by default, so a syntactically and semantically valid manifest is still not route-eligible unless the ordinary federation status is separately advanced through evidence.

Protocol pins verified on 2026-08-21:

- A2A specification release `1.0.0`; protocol wire version `1.0` because A2A negotiates Major.Minor and excludes patch versions from requests, responses, and Agent Cards.
- MCP `2026-07-28`; protocol core is stateless, the initialize/initialized handshake is removed, and `Mcp-Session-Id` is no longer part of the current wire protocol.

Core invariant:

`discovery != authorization != route eligibility != execution != verification`

Security rules include no inline credential values, no wildcard capabilities, canonical-operation binding to the existing federation catalog, explicit scope requirements, bounded timeout/concurrency, verification for irreversible capabilities, health-lease freshness, and fail-closed treatment of revoked/quarantined/stale adapters.

Host validation of this contract layer does not establish that any A2A or MCP endpoint is configured, authenticated, connected, executable, or semantically verified.
