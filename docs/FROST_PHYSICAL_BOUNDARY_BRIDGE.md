# Frost Forge Physical Boundary Bridge

Use this tool when host automation is complete but authentic Android/Termux execution is still required.

The same script supports two modes:

- **Host/preflight:** validates itself and writes a handoff receipt. It never treats host execution as device execution.
- **Android/Termux:** syncs the canonical source, reuses the existing verified evidence-gate collector and Library Cleaner, reconnects previously paired local ADB when possible, runs a bounded improvement cycle, commissions device-origin evidence, and emits one combined ZIP plus SHA-256.

The improvement loop is:

`observe → measure → hypothesize → criticize → retry only recoverable conditions → verify → preserve evidence`

The loop does not self-modify source on the phone and does not weaken gates. Source improvements remain subject to normal repository review and CI.

## First-time Android authorization

If Android Wireless Debugging has never been paired, Android must authorize that pairing once. The bridge detects this state, emits `ADB_PAIRING_REQUIRED`, disarms the cleaner, stops retrying the non-recoverable condition, and asks for the same script to be rerun after pairing.

Previously paired endpoints are rediscovered with local ADB mDNS and reconnected automatically where possible.

## Cleaner safety

The bridge reuses the Library Cleaner transaction rather than implementing a second deletion path. After installation, it explicitly disarms the cleaner and only re-arms through the cleaner's own qualification control when the combined cycle passes.

A commissioning failure disarms the cleaner and packages failure evidence before returning.

## Evidence output

Device mode produces:

`~/storage/downloads/FrostForgePhysicalBoundaryEvidence_<timestamp>.zip`

with a sibling `.sha256` file.

Local success remains `DEVICE_EVIDENCE_CAPTURED_PENDING_INDEPENDENT_VERIFICATION`. The bridge never self-promotes `DEVICE_VALIDATED`, `PERSISTENT_VALIDATED`, or the Library Cleaner to device/UI `VERIFIED` solely from local execution.
