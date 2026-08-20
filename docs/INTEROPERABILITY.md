# Wazoo26 A2A / MCP Interoperability Boundary

Status: `COMPATIBLE_MODULE_CANDIDATE / HOST_VALIDATED / NOT_PROMOTED`

Base repository: `12ephods-source/centinal26`  
Base commit: `14416d0f08cddf117a79c05104ba15c4ad3b1036`  
Prepared: `2026-08-19T22:36:00-06:00`

This additive change gives the existing Wazoo26 `a2a` and `mcp` federation entries typed
capability, authentication, session/state, health-lease and route-eligibility contracts.
It does not add a network client, credentials, remote executor or new authorization source.

The existing federation catalog remains authoritative and currently leaves both `a2a`
and `mcp` as `NOT_CONFIGURED`. Therefore a syntactically valid manifest is still
**not route eligible** under the default catalog.

Protocol pins:
- A2A `1.0.0`
- MCP `2026-07-28`

Core invariant:

`discovery != authorization != route eligibility != execution != verification`

For MCP `2026-07-28`, legacy handshake/session assumptions are rejected and transport
state is modeled as `stateless_request`.
