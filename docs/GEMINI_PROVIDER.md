# Gemini provider integration candidate

This candidate adds Gemini as a bounded remote-model provider behind `frost_core.providers`.

Key invariants:

- No implicit provider default.
- `HOST_VALIDATED` is the maximum maturity before a real authenticated probe.
- A passed connected probe can raise the record only to `CONNECTED_VALIDATED`.
- Provider execution is not semantic verification.
- Remote routing is limited to `public` and `internal`; `sensitive` and `restricted` fail closed.
- Requests use the stable Gemini Interactions API v1 surface.
- `store=false`.
- `tool_choice=none`; `requires_action` responses fail closed.
- API credentials are read from `GEMINI_API_KEY` and are not persisted by the core provider.
- Provider receipts contain hashes/metadata, not prompt/response plaintext.
- Gemini outputs are labeled `UNVERIFIED_MODEL_OUTPUT`.

Current Google documentation (verified 2026-08-20):
- Gemini 3.7 Flash is stable/GA and is the default model in this candidate.
- The Interactions API has a stable v1 version.
