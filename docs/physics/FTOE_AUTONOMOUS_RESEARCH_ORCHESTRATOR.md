# FToE Research Orchestrator

This layer automates repeated falsification-first research cycles on Android/Termux while preserving the project's rule that model output is not scientific verification.

## Architecture

`Termux runit daemon -> deterministic local gates -> multi-provider LLM panel -> hash-linked cycle artifact -> publication gate -> repeat`

The panel roles are theorist, group-theory auditor, phenomenology auditor, numerical verifier, adversarial referee, literature synthesizer, and manuscript editor. Every configured provider may answer every role; missing API keys are skipped.

Supported adapters: OpenAI Responses, Anthropic Messages, Gemini generateContent, xAI OpenAI-compatible chat, DeepSeek OpenAI-compatible chat, Mistral chat, and Cohere v2 chat. Model IDs are environment-overridable. API keys are read only from a local chmod-600 environment file and are never committed.

## Safety / epistemic boundary

The daemon cannot merge PRs, publish papers, execute arbitrary remote shell commands, or promote a claim because LLMs agree. Local execution is restricted to the explicit Python test/gate allowlist in `scripts/ftoe_research_daemon.py`.

Publication readiness is fail-closed. `physics/ftoe/publication_gate.json` must have top-level `PASS` and every mandatory subgate must be `PASS`; a manuscript draft must exist; and all local gates must return zero.

## Termux

Install Termux:Boot and then run:

```bash
bash termux/install_ftoe_research_daemon.sh
```

Edit only the providers you can authenticate:

```bash
nano ~/.config/ftoe-research/providers.env
chmod 600 ~/.config/ftoe-research/providers.env
sv restart ftoe-research
```

Inspect:

```bash
sv status ftoe-research
tail -f ~/.local/state/ftoe-research-log/current
```

The daemon persists cycles under `artifacts/ftoe-research-agent/` with a SHA-256 sidecar and updates `physics/ftoe/autonomous_research_state.json`.

## Publication stop condition

The daemon exits only when the publication gate is explicit PASS. It does not convert a REVIEW or FAIL to PASS automatically. A failed branch must be repaired by a new derivation or removed from the manuscript.
