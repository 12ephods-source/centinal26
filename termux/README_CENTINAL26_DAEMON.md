# Centinal26 Termux Execution Plane

This runtime is the Android/Termux physical execution capability of the existing Centinal26 autopilot. It is not a second autonomous controller.

## Install

Paste `CENTINAL26_TERMUX_ONE_PASTE_INSTALLER_v1.sh` explicitly into a Termux shell, or execute the file locally. The installer is idempotent: it repairs/updates an existing clean installation, backs up replaced runtime files, verifies Python/Bash syntax, scans the installed payload for selected high-risk execution patterns, registers a Termux:Boot hook where supported, starts the daemon, and writes an install manifest.

## Control

`~/.centinal26/bin/centinal26ctl.py status`

Queue a hash-pinned local script:

```sh
SHA=$(sha256sum ~/.centinal26/src/centinal26/path/to/script.py | awk '{print $1}')
~/.centinal26/bin/centinal26ctl.py enqueue \
  --intent 'run approved project verifier' \
  --capability local.script \
  --source-revision "$(git -C ~/.centinal26/src/centinal26 rev-parse HEAD)" \
  --payload "{\"path\":\"$HOME/.centinal26/src/centinal26/path/to/script.py\",\"sha256\":\"$SHA\",\"args\":[],\"timeout\":120}"
```

Queue a bounded GitHub operation:

```sh
~/.centinal26/bin/centinal26ctl.py enqueue \
  --intent 'inspect PR checks' \
  --capability github.cli \
  --payload '{"op":"pr_checks","repo":"12ephods-source/centinal26","number":304}'
```

Provider-neutral AI/agent/app-builder/image/assistant integrations use `provider.invoke`. Providers are configured locally in `~/.centinal26/config/providers.json`; each provider exposes a fixed adapter executable plus an explicit capability allowlist. Provider credentials remain outside the daemon evidence database and repository.

## Evidence and lifecycle

The daemon records execution-start, execution-result/error, and local postcondition-verification records in SQLite with SHA-256 evidence digests. Those records prove what the daemon observed locally but do **not** independently certify the daemon itself. Consequently daemon-local success can support a physical-execution candidate record after authentic Android origin is established, but `device-tested` requires a separately sourced verifier/postcondition path. `production-ready` requires every applicable release and operational gate.

## Recovery

Expired RUNNING leases are reconciled into RETRY_WAIT. Transient execution failures receive bounded exponential backoff with jitter, capped attempts, and durable checkpoints. A single SQLite `BEGIN IMMEDIATE` claim prevents concurrent workers sharing the same database from claiming the same operation.

## Stop / uninstall

`~/.centinal26/bin/centinal26_daemon_service.sh stop`

`~/.centinal26/bin/centinal26-uninstall.sh`

The uninstall helper stops the daemon and removes its boot hook but deliberately preserves state/evidence/backups. Destructive removal of the durable evidence directory is never automatic.
