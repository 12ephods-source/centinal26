# Frost Forge Reusable Improvement-Cycle Memory

For repeated engineering blockers, use this sequence:

1. Observe the exact failure and preserve evidence.
2. Measure whether the blocker is code, harness, infrastructure, authorization, physical access, or missing evidence.
3. Hypothesize the smallest plausible causes.
4. Criticize and compare alternatives; prefer the repair that reduces future failure modes and human labor without weakening gates.
5. Implement the smallest bounded repair.
6. Test deterministically. Simulations must avoid unnecessary real side effects; every lifecycle branch gets a timeout and explicit terminal state.
7. Run the real path when authorized and physically possible.
8. Independently verify; execution is not verification.
9. Preserve hashes, logs, artifacts, and rollback information.
10. Register and reuse the solution rather than rebuilding equivalent machinery.
11. Repeat until no demonstrated higher-value safe defect remains.
12. Stop only at a genuine external boundary and name the smallest action that crosses it.

Important improvement learned here:
- Separate simulation from payload installation and other expensive real side effects.
- Use dependency injection for device/auth states.
- Use terminal states such as WAITING_ANDROID_ADB_PAIRING, QUALIFICATION_FAILED_DISARMED, REAL_DEVICE_EXECUTED_EVIDENCE_PENDING, and REAL_DEVICE_EXECUTED_EVIDENCE_PRESERVED.
- For destructive actions: exact target -> preserve bytes -> hash/ledger -> re-identify -> execute -> verify postcondition -> preserve evidence.
- Host PASS never substitutes for physical-device execution.

Additional lesson from Cycle 3:
- Do not equate `evidence packager exited 0` with `evidence preserved`.
- A terminal evidence state requires independently recomputing the evidence artifact SHA-256 on the device and comparing it to its sidecar/manifest.
- Start long-running destructive automation only after that device-side evidence verification succeeds.
- Prefer shell-only simulation harnesses when Python startup itself is part of the host environment under test or can introduce unrelated warmup latency.
