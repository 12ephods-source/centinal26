# Wazoo26 naming decision

Date: 2026-08-18

## Decision

The active Automation OS line formerly called **Centinal26** is renamed **Wazoo26**.

`Wazoo26` is the canonical human-facing product name from this decision forward.

## Compatibility boundary

This is a product-name migration, not a destructive provenance rewrite. The following identifiers remain unchanged unless a separately validated migration explicitly changes them:

- GitHub repository slug: `12ephods-source/centinal26`
- Python distribution name: `centinal26`
- Python import package: `centinal26`
- legacy CLI entry point: `centinal26`
- default state directory: `~/.local/state/centinal26`
- legacy environment variable: `CENTINAL26_HOME`
- historical release names, paths, hashes, manifests, receipts, PR text, and evidence records

The current release adds:

- canonical CLI entry point: `wazoo26`
- canonical environment variable: `WAZOO26_HOME`
- runtime product identity: `Wazoo26`

`WAZOO26_HOME` takes precedence over `CENTINAL26_HOME`. When neither is set, Wazoo26 continues using the existing `~/.local/state/centinal26` directory so the naming change cannot silently fork durable state.

## Provenance rule

Historical artifacts that contain the name `Centinal26` remain historically correct and must not be rewritten solely for branding. New user-facing documentation and messages should use `Wazoo26`; compatibility identifiers should be identified explicitly as compatibility identifiers when relevant.

## Non-goals

This rename does not by itself:

- rename the GitHub repository;
- rename the Python package/import namespace;
- alter release hashes or historical evidence;
- promote any host result to device validation;
- change authorization, execution, verification, or audit semantics.

Any later repository/package namespace migration must be handled as a separate compatibility and provenance gate.
