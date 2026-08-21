# Frost Bluetooth Guard v1.0

A bounded Android companion for **continuous Bluetooth connection-state monitoring**. It distinguishes actual Android Bluetooth connection/bond events from mere nearby advertising.

## What it monitors

The foreground service listens to Android framework broadcasts for:

- ACL connection established / disconnected
- bond (pairing) state changes
- remote device name / alias changes
- local Bluetooth adapter ON/OFF state
- aggregate adapter connection-state changes
- monitor start/stop/degradation events

It does **not** classify a nearby BLE advertisement as a connection and does not attempt to identify a human solely from a Bluetooth identifier.

## Warning classes

| Code | Severity | Meaning |
|---|---:|---|
| `UNKNOWN_CONNECTED` | CRITICAL | ACL connection from a device not in the trusted baseline |
| `NEW_BOND` | HIGH/LOW | New pairing; HIGH when not trusted |
| `RAPID_RECONNECT` | HIGH | At least 3 connections by the same address in 10 minutes |
| `IDENTITY_NAME_CHANGED` | HIGH | Same address observed with a changed remote name/alias |
| `MONITOR_DEGRADED` | HIGH | Permission/runtime failure makes monitoring incomplete |
| `MULTIPLE_CONNECTED` | MEDIUM | More than the configured simultaneous-connection threshold (default 3) |
| `ADAPTER_REENABLED` | MEDIUM | Bluetooth transitioned from OFF to ON while monitoring was active |
| `BOND_REMOVED` | MEDIUM | A prior pairing was removed |
| `TRUSTED_CONNECTED` | INFO | Reviewed/trusted device connected |

Android high/critical warnings use a high-importance notification channel. Informational events are retained in evidence without generating nuisance alerts.

## Evidence model

Events are appended to app-private `bluetooth_events.jsonl`. Each event includes a monotonic sequence number, UTC timestamp, event type, remote address/name when available, detail fields, Android broadcast sender UID/package when API 34+ exposes them, the previous event hash, and the SHA-256 event hash.

Warnings are appended separately to `bluetooth_alerts.jsonl` and reference the event hash that caused them. The UI exports both logs and a chain-head manifest into a user-selected ZIP using Android's document picker.

This is tamper-evident application logging, not hardware attestation. A Bluetooth address/name is device evidence, not proof of the human operator.

## Trust baseline

The app does **not** silently trust every bonded device. Review Android's Bluetooth settings first, then press **Trust all currently bonded devices** only after recognizing the list. The baseline can be cleared at any time.

## Android requirements

- Android 8.0+ (`minSdk 26`)
- `BLUETOOTH_CONNECT` runtime permission on Android 12+
- notification permission on Android 13+ for normal alert display
- foreground `connectedDevice` service for continuous monitoring
- `BOOT_COMPLETED` receiver for automatic restart

For reliable persistence on Samsung/other OEM devices, set the app's battery mode to Unrestricted if Android/OEM background restrictions suspend it.

## Build

```bash
gradle :app:testDebugUnitTest :app:assembleDebug
```

Repository CI builds a debug APK and publishes it as a workflow artifact.

## Scope boundaries

This v1 monitor intentionally does not perform continuous discovery/scanning. Continuous scans have different permissions, battery cost, and evidentiary semantics. A later scanner can feed a separate `NEARBY_*` namespace, but nearby observations must never be promoted to `CONNECTED` without a connection event.

It also does not disconnect devices, unpair devices, enable/disable Bluetooth, or execute remote commands. Monitoring and evidence collection are read-only with respect to Bluetooth state.
