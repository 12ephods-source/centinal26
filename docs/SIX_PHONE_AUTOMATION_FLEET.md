# Six-Phone Automation Fleet

Status: DESIGNED / CONTROL-PLANE SCAFFOLDED / PHYSICAL DEVICE BINDING PENDING

## Objective

Coordinate six Android phones as independently attributable Termux execution workers under the existing Centinal26 control plane. GitHub remains durable project/source state. Base44 Superagent is the worker/job/evidence coordination plane. ChatGPT Autopilot selects and advances work. Lovable is an operator dashboard, not a source of truth.

## Canonical flow

ChatGPT Autopilot -> Centinal26 canonical state -> Base44 Superagent -> bound Android/Termux worker -> bounded capability -> independent verification -> evidence/provenance -> canonical state update -> next action.

## Fleet slots

The control plane maintains six logical slots, `phone-01` through `phone-06`. A slot is `UNBOUND` until a genuine authenticated Android/Termux worker with stable worker instance identity is observed and associated with the slot. Demo, CI, Vercel, browser, host, or simulated workers may not satisfy this binding.

## Installed-app inventory

The bounded operation is `device.apps.inventory`.

It is read-only and must not install, uninstall, enable, disable, launch, or modify applications. For each phone, the device worker should collect a deterministic package inventory using Android/Termux-visible package-manager metadata, then produce a normalized artifact containing at least:

- fleet device ID;
- worker instance ID;
- boot ID;
- capture timestamp;
- package name;
- version name/code when exposed;
- installer/source when exposed;
- enabled/system/user classification when exposed;
- APK/source path only when normally visible to the worker;
- inventory package count;
- SHA-256 of the normalized inventory artifact.

Each phone's inventory remains separate evidence. A fleet-level comparison is derived only after per-device verification.

## Lifecycle

`attempted -> built -> sandbox-tested -> device-tested -> production-ready`

The existence of schemas, UI, Base44 records, GitHub code, or host tests does not establish `device-tested`. Genuine phone-origin evidence and independent verification are required.

## Blocked-device policy

If a phone is not connected, its slot remains `WAITING_FOR_DEVICE`. Autopilot continues work on all other phones and all non-device dependencies. It does not fabricate heartbeat, package inventory, boot identity, or device-test evidence.

## Dashboard

Lovable fleet UI should expose:

- six fleet slots and binding status;
- worker heartbeat/boot/runtime identity;
- inventory status/count/hash;
- package-by-phone/version comparison;
- jobs and postcondition state;
- evidence and lifecycle state;
- blockers/external conditions.

Dashboard mutations are limited to bounded job requests against an already-bound worker. No arbitrary shell, arbitrary URL, package installation/uninstallation, credential editing, or lifecycle promotion by assertion.
