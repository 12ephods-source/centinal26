# Automation OS Universal Installer v3.1

A manifest-driven Android/Termux deployment framework.

## Canonical installable modules

- Centinal26/Frost core v1.0
- Frost fleet v1.7
- Hermes/C05 v1.0
- Base44 worker v1.0
- bounded capability provider v1.0

All canonical modules are fetched from immutable Git commits and checked against
expected Git blob identities before execution.

## Profiles

- `bootstrap`
- `centinal26-core`
- `android-fleet`
- `hermes-c05`
- `base44-worker`
- `base44-capabilities`
- `automation-core-current`

Example:

```bash
AUTOMATION_OS_PROFILE=automation-core-current bash AUTOMATION_OS_UNIVERSAL_INSTALLER_v3.1.sh
```

The Base44 profiles may require interactive user-owned credentials.

## Deliberately not promoted yet

AICCEP-OS, GuardianLLM, SDOS, and Hermes Sentinel artifacts have been found, but
are not represented as fresh-phone modules until exact complete sources are
canonicalized and validated.

## Security boundary

This framework does not embed credentials, bypass Android permissions, or add
arbitrary remote shell execution. Physical Android qualification remains a
separate gate from host/CI validation.
