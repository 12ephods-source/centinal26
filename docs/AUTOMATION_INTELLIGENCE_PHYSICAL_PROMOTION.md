# Automation Intelligence Controller — Physical Android Promotion

This layer turns host-qualified controller code into a falsifiable Android/Termux promotion gate.

## Gate sequence

1. Confirm execution is actually inside Termux on Android.
2. Install the current repository checkout into a local virtual environment.
3. Start the persistent controller supervisor and prove the process remains alive.
4. Record a physical state-change event, claim its exact work item, and complete it on the device.
5. Prove expired-lease recovery by reclaiming a one-second lease after expiry.
6. Prove heartbeat advancement and the controller event-chain invariant.
7. Install a reversible Termux:Boot hook and stop at `AWAITING_REBOOT`.
8. After a real device reboot, require a different boot identity and boot-generated controller evidence.
9. Prove the controller returned, heartbeat freshness, event-chain validity, and a post-reboot work completion.
10. Only then emit `PHYSICAL_VALIDATED`.

The scripts never initiate a reboot remotely. A real device reboot is deliberately an external physical gate.

## GitHub coordination

`install_intelligence_github_control.sh` installs a dedicated allowlisted GitHub job worker. It only accepts issue bodies with:

```json
{"schema":"automation.github_job/v2","command":"intelligence_controller_physical_gate_v1","parameters":{}}
```

No arbitrary shell command is read from the issue. The worker publishes evidence hashes to the issue and closes it only after post-reboot validation passes.

## State and evidence

Local evidence is stored under `~/.automation_intelligence_gate/` and controller state under `~/.local/state/centinal26/` by default. The pre- and post-reboot reports are JSON and may be independently hashed and archived.

Host CI can validate syntax and static safety contracts, but it cannot satisfy the physical gate. Android/Termux promotion requires the evidence produced on the device.
