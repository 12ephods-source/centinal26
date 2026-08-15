# Frost C05 Execution Protocol

Use this skill when Hermes needs execution rather than reasoning.

1. Express the desired action as a registered semantic C05 capability.
2. Use `frost_c05_status` to inspect currently registered capabilities.
3. The model may automatically call only the read-only A0 capability allowlist.
4. Never ask for, store, or reuse a direct-user approval token.
5. For a non-A0 capability, tell the user to issue and consume the one-time token outside model context.
6. `provider=github` only stages a local immutable request. It does not write to GitHub.
7. Treat `EXECUTED` and `VERIFIED` as different states.
8. Do not execute code preserved by `frost_stage_script`; it is inert migration evidence.
