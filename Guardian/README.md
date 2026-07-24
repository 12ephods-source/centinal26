# Guardian Level 1 Validation Framework v1.0

Reproducibility and audit infrastructure for computational experiments.

## Overview

Guardian Level 1 proves that a computation was performed consistently and can be
replayed. It does **not** prove that the scientific model being evaluated is correct.
Scientific validation belongs to Level 2.

## Features

- Deterministic NumPy RNG with exact state restoration
- Atomic checkpoint writes (tempfile + rename)
- Append-only cryptographic event chain (SHA-256 hash chain)
- Manifest locked before execution (immutable identity contract)
- Environment identity capture (Python, platform, arch, dependencies)
- Recovery resumption from the latest valid checkpoint
- Full verification suite (6 checks)
- Attestation policy (`LOCAL_TERMUX` / `OCI_EXECUTION`)

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the crash-resume test
python -m tests.test_crash_resume
```

## Architecture

```
guardian/
├── core/
│   ├── hashing.py      # Canonical JSON + SHA-256
│   ├── environment.py  # Environment identity capture
│   ├── manifest.py     # Immutable experiment manifest
│   ├── events.py       # Append-only hash-chained event log
│   ├── checkpoint.py   # Atomic checkpoint engine + RNG restore
│   └── executor.py     # Deterministic execution + crash injection
└── verifier/
    ├── verify.py       # 6-check verification suite
    └── policy.py       # Attestation decision logic
```

## Execution Classes

| Class | Evidence | Constraints |
|---|---|---|
| `LOCAL_TERMUX` | Python, platform, arch, deps hash | `image_digest = local_termux_no_oci` |
| `OCI_EXECUTION` | Container digest, source commit, deps | Real OCI digest required; no placeholders |

## Attestation Levels

| Level | What It Proves |
|---|---|
| Level 1 (this framework) | Computation was performed deterministically and reproducibly |
| Level 2 | Scientific model produces correct/meaningful results |

Level 2 requires independent domain validation, uncertainty quantification,
adversarial testing, and external dataset comparisons. Guardian provides the
evidence mechanism; it does not substitute for scientific judgment.

## Build Verification

```bash
cd Guardian

# Verify all imports resolve
python -c "
import guardian
from guardian.core import hashing, manifest, environment, events, checkpoint, executor
from guardian.verifier import verify, policy
print('All imports: OK')
"

# Run crash-resume test
python -m tests.test_crash_resume
```

Actual captured output:

```
============================================================
Guardian Level 1 - Crash-Resume Validation Test
============================================================

[Phase 1] Run to checkpoint then crash...

JOB_CREATED + MANIFEST_LOCKED
  Execution FAILED (expected)

[Phase 2] Resume from checkpoint...

  Recovery detected: True
  Checkpoint step: 47

[Phase 3] Verification...


=== Guardian Level 1 Verification Report ===
Execution class : LOCAL_TERMUX
Manifest ID     : test-run-001
Overall status  : ALL PASSED

VERIFY_001 PASS - Manifest exists and is valid
VERIFY_002 PASS - Results hash matches (903f92a5deb212d2...)
VERIFY_003 PASS - Event chain valid (8 events)
VERIFY_004 PASS - All 6 checkpoints verified
VERIFY_005 PASS - Checkpoint sequence valid (6 checkpoints)
VERIFY_006 PASS - LOCAL_TERMUX execution confirmed


Attestation: SIGNED
Reason: ATTESTATION_APPROVED (LOCAL_TERMUX)

[Phase 4] Duplicate sample detection...
  No duplicate samples detected (RNG restored correctly)

[Phase 5] Event chain audit...
  Events logged: 9
  [OK] RESUME
  [OK] CHECKPOINT_00047
  [OK] EVALUATION_STARTED
  [OK] CHECKPOINT_00060
  [OK] CHECKPOINT_00080
  [OK] CHECKPOINT_00100
  [OK] EVALUATION_COMPLETED
  [OK] ARTIFACT_FINALIZED
  [OK] ATTESTATION_SIGNED

============================================================
Guardian Level 1 - ALL TESTS PASSED
============================================================
```

Checkpoints land at steps 20 and 40 during the initial (pre-crash) run, an
emergency checkpoint is taken at step 47 (the injected crash point), and the
resumed run continues to completion with checkpoints at 60, 80, and 100 —
6 checkpoints total, all independently hash-verified.

Version 1.0.0 | Level 1 | Guardian Project
