# No Android/Termux Worker Recovery Pattern

Canonical failure class: the control plane observes zero eligible Android/Termux workers.

This condition is not immediately classified as an irreducible external blocker. The canonical first response is bounded self-recovery:

1. Detect whether the local bounded worker process is already alive.
2. If stopped, restart the existing authenticated worker using its local protected configuration.
3. If the worker is absent or damaged, verify the canonical repository copy of `deploy/termux/FROST_BASE44_WORKER_BOOTSTRAP_v1.0.sh` against the tracked Git object before execution.
4. Reuse only legitimate local non-interactive Base44 authentication already present in protected local configuration/environment.
5. Run the canonical bounded bootstrap, which self-registers/upserts the Android/Termux worker and exposes only its allowlisted capabilities.
6. Persist the recovery watchdog through Termux:Boot and retry periodically.
7. If no legitimate local authentication is available, report `AUTH_REQUIRED`; do not invent credentials, enrollment, signatures, device identity, or physical evidence.
8. If canonical source identity cannot be established, report `SOURCE_UNTRUSTED`; do not execute it.
9. Never translate successful worker recovery into device-validation success. Physical/deployment gates remain independently evidence-gated.

Executable implementation: `deploy/termux/FROST_ANDROID_WORKER_SELF_RECOVERY_v1.0.sh`.

This file is the durable recurrence rule. Future automation encountering the same failure class should reuse or repair this mechanism before creating a new watcher, bootstrap, worker, or workaround.
