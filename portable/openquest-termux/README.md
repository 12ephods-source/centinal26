# Portable OpenQuest Termux control plane

This directory is the canonical self-update channel for the portable OpenQuestRPG + Centinal26 Termux export.

Files:
- `frost_autopilot_update.sh`: clean fast-forward-only updater for registered Git projects; dirty/divergent trees fail closed.
- `centinal26_autopilot_bridge.sh`: reads canonical automation state and reuses the repository-owned Termux autopilot/physical-boundary implementation.
- `openquest_launcher.sh`: updates Centinal26, runs OpenQuest regression tests, then launches the localhost browser app.

Current Centinal26 Termux implementation reused by the bridge:
- `deploy/termux/library_cleaner/install_autopilot.sh`
- `deploy/termux/library_cleaner/physical_resume.py`
- `deploy/termux/physical_boundary_solver/run.sh`

After a verified Centinal26 fast-forward, `frost_autopilot_update.sh` refreshes the installed updater/bridge/launcher from this directory. No force reset, rebase, dirty-tree overwrite, physical-validation inference, or synthetic gate promotion is allowed.
