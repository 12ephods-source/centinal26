# Finished Product Qualification Policy

A finished software product and a finished deployed application are different qualification targets.

## SOFTWARE_RELEASE_COMPLETE

This state is permitted when implementation, repository synchronization, clean state, paired integration, SKY NET audit, state integrity, recovery behavior, and the fail-closed security policy all pass. Physical-device evidence is not required because this claim is about the software artifact itself, not about a particular handset deployment.

## DEPLOYED_APP_COMPLETE

This stronger state additionally requires authentic device-origin evidence for boot persistence, restart recovery, execution, and audit on the deployment target. Host or CI evidence must never be promoted to satisfy these checks.

## Invariant

No release may use the software-only state to claim that a physical deployment was tested. Conversely, absence of physical-device evidence must not prevent a fully implemented and repository-qualified software artifact from being classified as finished software.

This distinction is the canonical workaround for environments where the build/control plane is accessible but the physical execution endpoint is not currently enrolled.
