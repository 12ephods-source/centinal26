"""
Crash-resume test suite for Guardian Level 1.
Validates: checkpointing, RNG restoration, duplicate detection, verification.
"""

import json
import os
import shutil
import sys

# Ensure guardian is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def objective(param):
    """Dummy objective function for testing."""
    x, y = param["x"], param["y"]
    return x ** 2 + y ** 2


def run_test():
    """Run the complete crash-resume validation suite."""
    print("=" * 60)
    print("Guardian Level 1 - Crash-Resume Validation Test")
    print("=" * 60)

    # Setup clean output directory
    output_dir = "output"
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    os.makedirs(output_dir)

    events_path = "events.jsonl"
    if os.path.exists(events_path):
        os.unlink(events_path)

    manifest_path = os.path.join(output_dir, "manifest.json")
    results_path = os.path.join(output_dir, "results.json")
    verification_path = os.path.join(output_dir, "verification.json")

    # --- Phase 1: Run to checkpoint, then simulate crash ---
    print("\n[Phase 1] Run to checkpoint then crash...\n")

    from guardian import DeterministicExecutor
    from guardian.core.environment import capture_environment
    from guardian.core.hashing import hash_file
    from guardian.core.manifest import (EngineInfo, EnvironmentInfo,
                                         ExperimentManifest, SamplingInfo)

    # Create manifest
    env = capture_environment(execution_class="LOCAL_TERMUX", lockfile="requirements.txt")
    manifest = ExperimentManifest(
        manifest_version="1.0",
        experiment_id="test-run-001",
        engine=EngineInfo(
            name="GuardianFToE",
            version="1.0.0",
            code_id="test-code-id",
            code_hash="test-code-hash",
        ),
        parameters={"objective": "test"},
        sampling=SamplingInfo(method="numpy_random_pcg", samples=100, seed=42),
        environment=EnvironmentInfo(**env),
    )
    manifest.save(manifest_path)
    print("JOB_CREATED + MANIFEST_LOCKED")

    # Run to checkpoint, then crash at step 47
    executor = DeterministicExecutor(
        output_dir=output_dir,
        checkpoint_interval=20,
        chunk_size=5,
        seed=42,
        inject_failure_at=47,  # crash at step 47
        experiment_name="crash_resume_test",
    )
    result = executor.run(objective, total_samples=100, log_path=events_path)

    print(f"  Execution {'FAILED (expected)' if not result.success else 'SUCCEEDED (unexpected)'}")

    # --- Phase 2: Resume from checkpoint ---
    print("\n[Phase 2] Resume from checkpoint...\n")

    from guardian.core.checkpoint import recovery_resume

    # Clear old log to avoid confusion
    if os.path.exists(events_path):
        os.unlink(events_path)

    # Resume
    executor2 = DeterministicExecutor(
        output_dir=output_dir,
        checkpoint_interval=20,
        chunk_size=5,
        seed=42,
        experiment_name="crash_resume_test",
    )

    # Check recovery
    ckpt, prior = recovery_resume(output_dir, rng=None)
    print(f"  Recovery detected: {ckpt is not None}")
    if ckpt:
        print(f"  Checkpoint step: {ckpt.step}")

    # Run the rest
    result2 = executor2.run(objective, total_samples=100, log_path=events_path)

    # --- Phase 3: Verification ---
    print("\n[Phase 3] Verification...\n")

    from guardian.verifier import VerificationSuite, determine_attestation

    # Save final results
    with open(results_path, "w") as f:
        json.dump(result2.results, f, indent=2)

    # Hash results and update manifest
    results_hash = hash_file(results_path)
    manifest_data = json.load(open(manifest_path))
    manifest_data["verification"] = {"results_hash": results_hash}
    manifest_data["outputs"] = {
        "total_samples": result2.samples_collected,
        "mean_score": result2.results.get("summary", {}).get("mean_score", 0),
    }
    with open(manifest_path, "w") as f:
        json.dump(manifest_data, f, indent=2)

    # Run verification
    suite = VerificationSuite(
        output_dir=output_dir,
        manifest_path=manifest_path,
        events_path=events_path,
        results_path=results_path,
        verification_path=verification_path,
    )
    report = suite.run_all()
    suite.print_summary(report)

    # Attestation
    attestation = determine_attestation(
        verification_report=report,
        manifest=manifest_data,
        events_path=events_path,
        attestation_path=os.path.join(output_dir, "attestation.json"),
    )
    print(f"\nAttestation: {'SIGNED' if attestation['approved'] else 'DEFERRED'}")
    print(f"Reason: {attestation['reason']}")

    # --- Phase 4: Duplicate detection ---
    print("\n[Phase 4] Duplicate sample detection...")
    samples = result2.results.get("samples", [])
    param_signatures = set()
    duplicates = 0
    for s in samples:
        sig = (round(s["x"], 10), round(s["y"], 10))
        if sig in param_signatures:
            duplicates += 1
        param_signatures.add(sig)

    if duplicates == 0:
        print("  No duplicate samples detected (RNG restored correctly)")
    else:
        print(f"  {duplicates} duplicate samples found (RNG state issue)")

    # --- Phase 5: Event chain audit ---
    print("\n[Phase 5] Event chain audit...")
    from guardian.core.events import load_event_chain

    events = load_event_chain(events_path)
    event_types = [e["event_type"] for e in events]
    print(f"  Events logged: {len(events)}")

    required = ["RESUME", "CHECKPOINT_00047", "EVALUATION_STARTED",
                "CHECKPOINT_00060", "CHECKPOINT_00080", "CHECKPOINT_00100",
                "EVALUATION_COMPLETED", "ARTIFACT_FINALIZED", "ATTESTATION_SIGNED"]
    for evt in required:
        status = "OK" if evt in event_types else "MISSING"
        print(f"  [{status}] {evt}")

    # --- Final Summary ---
    print("\n" + "=" * 60)
    all_passed = (
        report["all_passed"]
        and attestation["approved"]
        and duplicates == 0
        and all(evt in event_types for evt in required)
    )
    if all_passed:
        print("Guardian Level 1 - ALL TESTS PASSED")
    else:
        print("Guardian Level 1 - SOME TESTS FAILED")
    print("=" * 60)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(run_test())
