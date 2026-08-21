# Gemini Interactions v1 provider

Status: `HOST_CANDIDATE / CONNECTED_VALIDATION_NOT_YET_OBSERVED`

The provider integrates the stable Gemini Interactions v1 API behind the existing provider registry without making Gemini an implicit default or a verification authority.

Pinned host contract:

- endpoint: `https://generativelanguage.googleapis.com/v1/interactions`;
- model: `gemini-3.7-flash` only;
- thinking levels: `low`, `medium`, `high` only;
- `store=false` for every request;
- no tools are supplied and `generation_config.tool_choice=none`;
- credentials are read from `GEMINI_API_KEY` at call time and are not persisted by this module;
- only `public` and `internal` privacy classes may route remotely;
- prompt and response plaintext are excluded from receipts; SHA-256 and bounded metadata are retained instead;
- model output is always labeled `UNVERIFIED_MODEL_OUTPUT` and requires independent verification before any consequential use.

Maturity boundary:

- host-qualified code may produce only a `HOST_VALIDATED` provider record with unknown availability;
- only a real authenticated exact-response probe may produce `CONNECTED_VALIDATED`;
- a connected probe never implies `PROMOTED`, `DEFAULT_ELIGIBLE`, device validation, or semantic truth.

This module is an execution adapter only. It grants no authority to select itself, change privacy classifications, use tools, or promote its output into canonical state.
