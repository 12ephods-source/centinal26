# Generated continuity schema reference

Model version: `1.0.0`  
Proposal schema: `frost.automation.continuity_migration_proposal.v1`

This file is generated from `automation/continuity_schema_source.json`. Do not edit it independently.

## Entity types

- `ai_session`
- `artifact_metadata`
- `code_module`
- `decision`
- `environment`
- `evidence`
- `experiment`
- `finding`
- `knowledge_revision`
- `knowledge_task`
- `project`
- `run`
- `security_case`
- `test_plan`
- `theory_claim`
- `workbench_capture`

## Epistemic statuses

- `Verified`
- `Reported`
- `Derived`
- `Proposed`
- `Speculative`
- `Rejected`
- `Superseded`
- `Partially implemented`
- `Reconstructed`
- `Unknown`

## Authority invariants

- proposal status is `PROPOSAL_ONLY`;
- machine continuation remains `automation/PROJECT_STATE.json`;
- execution authority is false;
- automatic epistemic promotion is false;
- automatic contradiction resolution is false;
- alias/current-pointer mutation is false.
