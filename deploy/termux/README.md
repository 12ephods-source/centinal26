# Termux Deployment

Target environment for Android-side Automation OS workers.

Deployment assets placed here must preserve the canonical execution invariant. Remote requests may select only allowlisted capabilities; arbitrary remote shell execution is out of scope for the canonical worker.

Before a deployment is labeled `DEVICE_VALIDATED`, its installer, service lifecycle, storage permissions, restart behavior, artifact hashing, and result/audit return path must be exercised on the intended Android/Termux device.
