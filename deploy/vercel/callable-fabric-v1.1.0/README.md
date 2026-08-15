# Frost Callable Fabric v1.1.0 — Vercel adapter

Provider-neutral semantic execution adapter for canonical `12ephods-source/centinal26` commit `6e5731bfbb073573c044bcc2e106d3906f6dddf5`.

Endpoints: `/api/health`, `/api/capabilities`, `/api/invoke`, `/api/mcp`.

Policy: semantic operations only; unrestricted remote shell disabled; Guardian gates high-risk operations; schema validation fails closed; each invocation returns a self-verifiable SHA-256 provenance receipt. Durable cross-request control-plane state remains outside the serverless filesystem.

Source identity SHA-256: `623c8ab6ae44939098fbdbd5f1b362d4239077498a277616f6dee76b38ada733`.
Deployment adapter spec SHA-256: `96fedc9ec3affe883fd3fa8f67e1813db9ca153ce9cd3b3aea7fd3379268676a`.

As of 2026-08-14, local doctor validation passes 10/10. Vercel deployment creation is externally blocked by team-role permission (403) for both production and preview; that provider-state blocker is not a host-code failure.
