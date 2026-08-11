window.AUTOMATION_OS_DATA = {
  invariant: [
    "Intent",
    "Authorization",
    "Event / Queue",
    "Capability Selection",
    "Bounded Execution",
    "Verification",
    "Evidence / Audit",
    "State Update",
    "Controlled Evolution"
  ],
  statuses: [
    { label: "Repository / provenance validation", state: "PASS", detail: "Baseline invariant, provenance, and release-state guards pass." },
    { label: "Python compilation", state: "PASS", detail: "Current repository and RC4 successor Python modules compile." },
    { label: "Ruff", state: "PASS", detail: "Current RC4 successor branch passes lint after preserving the initial failed run." },
    { label: "pytest — Python 3.11", state: "PASS", detail: "Synthetic successor regression suite passes." },
    { label: "pytest — Python 3.12", state: "PASS", detail: "Synthetic successor regression suite passes." },
    { label: "pytest — Python 3.13", state: "PASS", detail: "Synthetic successor regression suite passes." },
    { label: "Controller shell syntax", state: "PASS", detail: "Historical and successor release controllers pass bash syntax validation." },
    { label: "Physical Android / Termux", state: "PENDING", detail: "No physical RC4 candidate validation has been promoted." },
    { label: "Endurance validation", state: "PENDING", detail: "Required target endurance evidence remains open." },
    { label: "Device sync validation", state: "PENDING", detail: "Signed-bundle and pinned/trusted-peer evidence remains open." },
    { label: "Native candidate certification", state: "BLOCKED", detail: "Cannot certify before candidate construction and physical evidence gates." },
    { label: "Explicit human promotion", state: "BLOCKED", detail: "RC4 is REVIEW, not GA. Promotion remains an explicit final action." }
  ],
  architecture: [
    { name: "Control plane", code: "01", text: "Intent normalization, authorization, durable queueing, leases, capability registry, policy, and state transitions." },
    { name: "Execution plane", code: "02", text: "Termux, Hermes, and local workers execute named allowlisted capabilities under bounded arguments, timeouts, and environment constraints." },
    { name: "Evidence plane", code: "03", text: "Inputs, outputs, hashes, failures, verification results, provenance, and environment identity are preserved as durable evidence." },
    { name: "Knowledge / continuity plane", code: "04", text: "Project state, canonical objects, conflicts, decisions, and historical artifacts remain recoverable across iterations." },
    { name: "Application / agent plane", code: "05", text: "AAARD and specialized agents operate through the control plane instead of bypassing authorization and verification boundaries." }
  ],
  tools: [
    { name: "Branch convergence analyzer", text: "Accepts only exact pinned RC3 parent identities, extracts embedded payloads without executing installers, verifies hashes and manifests, then emits deterministic divergence sets." },
    { name: "Semantic candidate constructor", text: "Requires exact coverage of changed-common files plus reviewer identity, timestamp, rationale, regression-test declaration, and source/hash-bound resolution." },
    { name: "Host qualification harness", text: "Validates candidate integrity and performs non-mutating static host checks. It never claims physical Android validation." },
    { name: "Promotion evidence gate", text: "Requires candidate-bound Android, endurance, device-sync, and recovery evidence with explicit verification requirements. It outputs PASS/BLOCK, never promotion." },
    { name: "Successor release controller", text: "Orchestrates INIT → ANALYZED → CONSTRUCTED → HOST_QUALIFIED → EVIDENCE_GATED → CERTIFIED → READY_FOR_HUMAN_PROMOTION without installing or promoting automatically." }
  ],
  pipeline: [
    { label: "Exact pinned RC3 parents", state: "pending" },
    { label: "Analyze divergence", state: "pending" },
    { label: "Human semantic decisions", state: "pending" },
    { label: "Construct RC4 candidate", state: "pending" },
    { label: "Host qualification", state: "pending" },
    { label: "Android / Termux", state: "pending" },
    { label: "Endurance + sync + recovery", state: "pending" },
    { label: "Native certification", state: "blocked" },
    { label: "Explicit human promotion", state: "blocked" }
  ],
  provenance: [
    { name: "CANONICAL", text: "Authoritative current implementation or specification for its declared scope." },
    { name: "COMPATIBLE_MODULE", text: "Valid module that conforms to canonical invariants without becoming the authoritative trunk." },
    { name: "EXPERIMENTAL", text: "Promising work whose results remain bounded by incomplete validation or integration evidence." },
    { name: "SUPERSEDED", text: "Retained historical artifact that has been replaced but remains necessary for provenance and rollback reasoning." },
    { name: "REJECTED", text: "Known-invalid or intentionally excluded artifact retained so failures and rejected approaches are not erased." }
  ],
  safety: [
    { title: "No arbitrary remote shell", text: "Remote requests select structured, allowlisted capabilities rather than injecting unrestricted shell payloads." },
    { title: "No host-for-physical substitution", text: "A host PASS cannot satisfy a physical Android/Termux evidence gate." },
    { title: "Failures remain evidence", text: "Failed runs, rejected claims, and earlier defects are retained instead of rewritten out of project history." },
    { title: "Claims stay scoped", text: "Static, host, device, endurance, release, and promotion evidence are distinct validation levels." }
  ],
  timeline: [
    { date: "2026-08-07", title: "RC3 release campaign recorded", text: "Host and distribution validation evidence is preserved, while the historical release certificate remains REVIEW because Android, endurance, and device-sync evidence are missing." },
    { date: "2026-08-07", title: "RC4 convergence target established", text: "The recoverable target becomes 1.0.0-rc4-converged, schema 10, with explicit refusal to invent merge decisions, physical evidence, certification, or automatic promotion." },
    { date: "2026-08-11", title: "Automation OS repository bootstrapped", text: "Centinal26 becomes the durable engineering control plane with canonical invariants, schemas, runtime primitives, CI, Termux boundary, and release state." },
    { date: "2026-08-11", title: "Provenance ingestion completed", text: "RC3 history, RC4 controller state, known SHA-256 identities, candidate evidence, and artifact classification rules are placed under repository control." },
    { date: "2026-08-11", title: "Qualification evidence added", text: "A separate verifiable host/Termux qualification bundle and tamper detection are added without weakening host/device validation boundaries." },
    { date: "2026-08-11", title: "RC4 successor tooling passes CI", text: "Reconstructed successor convergence tooling passes repository validation, compilation, Ruff, shell syntax checks, and pytest on Python 3.11–3.13. Empirical release gates remain open." }
  ]
};
