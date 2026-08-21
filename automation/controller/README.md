# Frost Automation Controller v1

Purpose: coordinate bounded automation workflows.

Pipeline:

REQUEST -> PLAN -> ASSIGN -> EXECUTE -> VERIFY -> ARCHIVE

Design rules:
- No self-granted authority.
- Every consequential action requires provenance.
- Verification is separate from execution.
- Unknown states remain unknown.
