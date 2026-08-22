# Frost Scientific Autocycle v1

Frost Scientific Autocycle turns an explicitly marked clipboard script into a persistent evidence-producing research cycle rather than treating copied code as a final answer.

## Protocol

Version 1 clipboard autorun remains unchanged. Scientific cycles use a separate marker:

```text
# FROST-AUTORUN:2 shell=python
# FROST-CYCLE: {"goal":"emit a verified measurement","success":{"exit_code":0,"required_text":["MEASURED_PASS"]},"limits":{"max_iterations":8,"episode_timeout_seconds":120},"agent_providers":["deterministic","aider"]}
print("MEASURED_PASS")
```

The `FROST-CYCLE` JSON line is required. It binds the candidate to a declared goal, executable acceptance predicate, resource limits, perspective set, optional local agent providers, origin metadata, and capability declarations.

## Cycle

The implemented cycle records and uses:

1. observation of actual process output;
2. measurement of exit status, duration, output bytes, and acceptance checks;
3. goal-oriented orientation through the declared predicate;
4. questions and competing failure hypotheses;
5. multiple reasoning perspectives;
6. criticism and perspective comparison;
7. context-sensitive Perspective Adjudication;
8. optional local/free AI agent findings and edit proposals;
9. re-inspection of every changed candidate;
10. repeated bounded experiment episodes;
11. independent goal-predicate verification;
12. positive and negative evidence in a hash-linked SQLite event ledger;
13. a final report with immutable candidate and evidence identities.

The current deterministic perspective portfolio is engineering, empirical, causal, falsification, information-value, discovery, resource, and epistemic. The adjudicator selects a context-appropriate subset rather than declaring one permanent worldview superior.

## Guardian / vibeware preflight

Every candidate is inspected before execution. The host implementation checks language syntax, a deliberately small set of destructive-effect patterns, and low-quality/incomplete-code markers such as TODO/FIXME, `NotImplementedError`, synthetic PASS markers, and non-tests such as `assert True`.

`REJECT` never executes. `REVIEW` is preserved and can be handed to a registered edit provider, but it is not executed as though it had passed inspection. Any edited revision is inspected again before execution.

This is a bounded Frost preflight layer, not a claim to universal malware detection.

## Agent providers

The controller has one provider interface. `deterministic` is always available and generates the built-in scientific analysis. Additional local/free tools are registered on the device in:

```text
~/.config/frost/autocycle_agents.json
```

Example:

```json
{
  "aider": {
    "mode": "edit",
    "argv": ["aider", "--yes-always", "--no-git", "--message", "{prompt}", "{candidate}"]
  },
  "local-llama": {
    "mode": "critique",
    "argv": ["llama-cli", "-m", "/path/to/model.gguf", "-p", "{prompt}", "-n", "512"]
  }
}
```

Provider registration is local device state. The clipboard payload cannot supply an executable or command line. Missing providers are reported as unavailable rather than silently substituted.

An `edit` provider receives a working copy. Immutable historical revisions are never edited in place. A changed candidate becomes a new child revision and must pass Guardian again.

## Persistence and evidence

Default state root:

```text
~/.local/share/frost-scientific-autocycle/
```

Each cycle contains immutable revisions, episode JSON, agent-panel records, a SQLite WAL database with SHA-256-linked events, and `report.json`.

Terminal states include:

- `GOAL_VERIFIED`
- `POLICY_BLOCKED`
- `NO_IMPROVING_REVISION`
- `RESOURCE_LIMIT_REACHED`
- `NO_PENDING_CYCLE`

The implementation does not promote Android/device/persistence state and does not claim that self-reported candidate output is scientific verification. The explicit acceptance predicate is evaluated from observed execution evidence.

## Android clipboard handoff

Android 10+ clipboard restrictions still apply. Use Tasker Clipboard Changed plus Termux:Tasker, matching the two-phase design already used by Frost Clipboard Autorun v1.

1. Background stage action sends `%cl_text` to `frost_scientific_cycle_stage`.
2. If stdout contains `FROST_AUTOCYCLE_STAGED`, a foreground Termux:Tasker action runs `frost_scientific_cycle_run` with no stdin.

This preserves the exact copied clipboard bytes before the visible Termux scientific cycle begins.

## Scientific-method boundary

The controller explicitly distinguishes execution success from scientific truth. Its built-in perspectives are structured analysis aids. Claims requiring external measurements, real devices, calibrated data, or independent empirical evidence remain unresolved until those observations exist.
