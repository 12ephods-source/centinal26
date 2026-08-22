# Frost Learning OS — reference snapshot v1.4

This directory is a temporary GitHub durability boundary for the independently built Frost Learning OS reference implementation. It is **not** part of the Wazoo26/Centinal26 Automation OS runtime and must not be imported as an Automation capability merely because it is stored in the same repository.

Current champion: **v1.4**, host-validated against frozen product-truth, trajectory-safety, efficiency/recovery, and delayed-retention standards.

Empirical boundary: the 14-day freshness rule is a controller policy, not an empirically established optimal retention interval. The `retention/` tooling exists to collect and analyze real delayed-recall/transfer observations without modifying the frozen champion.

Promotion rule: do not create or promote v1.5 from synthetic tuning alone. A threshold change requires real pilot evidence and held-out/later validation.

Repository boundary: this subtree is a temporary source snapshot because the connected GitHub surface currently exposes no dedicated Frost Learning OS repository. It should be re-homed into its own repository when repository creation becomes available; it should not be merged into Wazoo26 runtime modules by default.
