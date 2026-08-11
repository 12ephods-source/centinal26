# Termux Deployment

Target environment for Android-side Automation OS workers.

Deployment assets placed here must preserve the canonical execution invariant. Remote requests may select only allowlisted capabilities; arbitrary remote shell execution is out of scope for the canonical worker.

`centinal26 auto-daemon` is the continuous bounded worker. To make it restart after Android boot, install Termux:Boot and run:

```bash
bash scripts/enable-termux-boot.sh
```

The installed boot hook acquires a wake lock when available and starts the daemon. It does not broaden the capability allowlist or create a remote shell.

Before a deployment is labeled `DEVICE_VALIDATED`, its installer, service lifecycle, storage permissions, restart behavior, artifact hashing, and result/audit return path must be exercised on the intended Android/Termux device. Automated host gates, Termux detection, and successful boot-hook installation remain evidence inputs rather than automatic promotion.
