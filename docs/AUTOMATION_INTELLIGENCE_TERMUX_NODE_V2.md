# Automation Intelligence Termux Node v2

`termux/intelligence_node.sh` is the durable Android/Termux execution-node wrapper for the Automation Intelligence Controller.

## Purpose

Node v2 converts the prior boot-time controller plus one-shot GitHub worker into a bounded, recoverable local node without broadening execution authority.

The authority boundary is unchanged:

- GitHub issues remain transport/proposal records.
- The GitHub worker accepts only `automation.github_job/v2` with command `intelligence_controller_physical_gate_v1`.
- The node never executes issue-supplied shell.
- The node never initiates a reboot.
- Physical promotion still requires real Android/Termux and post-reboot evidence.

## Improvements

- periodic heartbeat advancement;
- controller watchdog and restart when the fixed controller process exits;
- PID start-time and command-line identity checks to reject stale/reused PID files;
- bounded GitHub worker retry with exponential backoff;
- API connect/max-time limits and transient retry;
- atomic node status snapshots;
- repository SHA/branch/dirty-state reporting;
- memory, storage, battery and temperature telemetry when Android sysfs exposes it;
- bounded log rotation;
- explicit `doctor`, `status`, `heartbeat`, `kick`, `restart` and `upgrade` commands;
- explicit fast-forward-only upgrade path;
- installer refuses to overwrite a dirty checkout;
- physical-gate worker enforces `expected_branch` and `minimum_merge_commit`.

## Commands

```bash
termux/intelligence_node.sh doctor
termux/intelligence_node.sh status
termux/intelligence_node.sh start
termux/intelligence_node.sh kick
termux/intelligence_node.sh heartbeat
termux/intelligence_node.sh restart
termux/intelligence_node.sh upgrade
termux/intelligence_node.sh stop
```

`upgrade` is intentionally explicit. It fetches `origin/main`, refuses dirty or divergent repositories, performs only a fast-forward merge, reinstalls the editable package, and restarts the node.

## Persistent evidence

Node v2 writes under `~/.automation_intelligence_gate/`:

- `node.pid` and `node.pidstart`
- `node.log`, rotated to `.1`/`.2`
- `node_status.json`
- `heartbeat.json` and `heartbeat.seq`
- existing physical-gate pre/post reboot evidence

No token is emitted by `doctor` or node status output.

## Boot behavior

The installer keeps three transparent Termux:Boot hooks:

1. controller hook starts Node v2 after 20 seconds;
2. job hook kicks the fixed allowlisted worker after 60 seconds;
3. report hook attempts post-reboot physical validation after 120 seconds.

The watchdog remains active after boot and keeps the controller heartbeat fresh even when no GitHub job is available.
