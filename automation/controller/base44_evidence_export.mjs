#!/usr/bin/env node

import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import process from "node:process";

const DEFAULT_APP_ID = "6a484dc22829dd2fd4a7bcd1";
const SCHEMA = "frost.controller_evidence_export.v1";
const HEX64 = /^[0-9a-f]{64}$/;

function canonical(value) {
  if (value === null || typeof value !== "object") {
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) {
    return `[${value.map(canonical).join(",")}]`;
  }
  const keys = Object.keys(value).sort();
  return `{${keys.map((key) => `${JSON.stringify(key)}:${canonical(value[key])}`).join(",")}}`;
}

function sha256(value) {
  const payload = typeof value === "string" ? value : canonical(value);
  if (typeof payload !== "string") throw new Error("canonical payload must be a string");
  return createHash("sha256").update(payload).digest("hex");
}

function finalizeBundle(bundle) {
  const { bundle_sha256: _ignored, ...unsigned } = bundle;
  return { ...unsigned, bundle_sha256: sha256(unsigned) };
}

function parseArgs(argv) {
  const result = {
    appId: DEFAULT_APP_ID,
    workerInstance: null,
    jobId: null,
    contractId: null,
    proposalKey: null,
    email: null,
    passwordStdin: false,
    limit: 100,
    selfTest: false,
    verifyBundle: null,
    phase: "phase-a",
    maxAgeSeconds: 900,
  };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === "--self-test") result.selfTest = true;
    else if (arg === "--password-stdin") result.passwordStdin = true;
    else if (arg === "--app-id") result.appId = argv[++i];
    else if (arg === "--worker-instance") result.workerInstance = argv[++i];
    else if (arg === "--job-id") result.jobId = argv[++i];
    else if (arg === "--contract-id") result.contractId = argv[++i];
    else if (arg === "--proposal-key") result.proposalKey = argv[++i];
    else if (arg === "--email") result.email = argv[++i];
    else if (arg === "--limit") result.limit = Number(argv[++i]);
    else if (arg === "--verify-bundle") result.verifyBundle = argv[++i];
    else if (arg === "--phase") result.phase = argv[++i];
    else if (arg === "--max-age-seconds") result.maxAgeSeconds = Number(argv[++i]);
    else throw new Error(`unknown argument: ${arg}`);
  }
  if (!Number.isInteger(result.limit) || result.limit < 1 || result.limit > 500) {
    throw new Error("--limit must be an integer from 1 to 500");
  }
  if (!Number.isInteger(result.maxAgeSeconds) || result.maxAgeSeconds < 60 || result.maxAgeSeconds > 86400) {
    throw new Error("--max-age-seconds must be an integer from 60 to 86400");
  }
  if (!["phase-a", "phase-b"].includes(result.phase)) {
    throw new Error("--phase must be phase-a or phase-b");
  }
  return result;
}

async function readPasswordFromStdin() {
  const input = await readFile(0, "utf8");
  const password = input.replace(/[\r\n]+$/, "");
  if (!password) throw new Error("empty password on stdin");
  return password;
}

function asArray(value) {
  if (Array.isArray(value)) return value;
  if (value && Array.isArray(value.entities)) return value.entities;
  return [];
}

async function filtered(entity, query, sort, limit) {
  return asArray(await entity.filter(query, sort, limit, 0));
}

async function maybeGet(entity, id) {
  if (!id) return [];
  try {
    const record = await entity.get(id);
    return record ? [record] : [];
  } catch (error) {
    const message = String(error?.message || error);
    if (message.includes("404") || message.toLowerCase().includes("not found")) return [];
    throw error;
  }
}

async function collect(base44, options) {
  const workerRecords = await filtered(
    base44.entities.AutomationWorker,
    { instance_id: options.workerInstance },
    "-updated_date",
    options.limit,
  );

  let jobs = options.jobId
    ? await maybeGet(base44.entities.AutomationJob, options.jobId)
    : await filtered(
        base44.entities.AutomationJob,
        { worker_instance_id: options.workerInstance },
        "-updated_date",
        options.limit,
      );

  const selectedJobId = options.jobId || jobs[0]?.id || null;
  if (selectedJobId && !jobs.some((record) => record.id === selectedJobId)) {
    jobs = [...(await maybeGet(base44.entities.AutomationJob, selectedJobId)), ...jobs];
  }

  const leases = selectedJobId
    ? await filtered(base44.entities.AutomationLease, { job_id: selectedJobId }, "-updated_date", options.limit)
    : [];
  const audits = selectedJobId
    ? await filtered(base44.entities.AutomationAudit, { job_id: selectedJobId }, "sequence", options.limit)
    : [];
  const results = selectedJobId
    ? await filtered(base44.entities.AutomationResult, { job_id: selectedJobId }, "-created_date", options.limit)
    : [];
  const rebootEvidence = await filtered(
    base44.entities.AutomationRebootEvidence,
    { instance_id: options.workerInstance },
    "-observed_at",
    options.limit,
  );
  const bootSentinels = await filtered(
    base44.entities.AutomationBootSentinel,
    { instance_id: options.workerInstance },
    "-observed_at",
    options.limit,
  );
  const physicalGates = options.proposalKey
    ? await filtered(
        base44.entities.AutomationPhysicalGate,
        { proposal_key: options.proposalKey },
        "-observed_at",
        options.limit,
      )
    : [];
  const workContracts = options.contractId
    ? await filtered(
        base44.entities.AutomationWorkContract,
        { contract_id: options.contractId },
        "-updated_date",
        options.limit,
      )
    : [];
  const judgeRoleResults = options.contractId
    ? await filtered(
        base44.entities.AutomationRoleResult,
        { contract_id: options.contractId, role: "JUDGE" },
        "-created_at_client",
        options.limit,
      )
    : [];
  const verificationVerdicts = options.contractId
    ? await filtered(
        base44.entities.AutomationVerificationVerdict,
        { contract_id: options.contractId },
        "-created_at_client",
        options.limit,
      )
    : [];
  const fleetMetrics = asArray(
    await base44.entities.AutomationFleetMetric.list("-captured_at", 20, 0),
  );

  const records = {
    workers: workerRecords,
    jobs,
    leases,
    audits,
    results,
    reboot_evidence: rebootEvidence,
    boot_sentinels: bootSentinels,
    physical_gates: physicalGates,
    work_contracts: workContracts,
    judge_role_results: judgeRoleResults,
    verification_verdicts: verificationVerdicts,
    fleet_metrics: fleetMetrics,
  };
  const collectionSha256 = Object.fromEntries(
    Object.entries(records).map(([name, value]) => [name, sha256(value)]),
  );
  return {
    schema: SCHEMA,
    exported_at: new Date().toISOString(),
    app_id: options.appId,
    access_mode: "AUTHENTICATED_USER_RLS",
    selector: {
      worker_instance_id: options.workerInstance,
      requested_job_id: options.jobId,
      selected_job_id: selectedJobId,
      contract_id: options.contractId,
      proposal_key: options.proposalKey,
    },
    records,
    collection_sha256: collectionSha256,
  };
}

function validAuditChain(audits) {
  if (!Array.isArray(audits) || audits.length === 0) return false;
  const ordered = [...audits].sort((a, b) => Number(a.sequence || 0) - Number(b.sequence || 0));
  let previous = "";
  for (const event of ordered) {
    if (!HEX64.test(String(event.event_hash || ""))) return false;
    if (String(event.prev_hash || "") !== previous) return false;
    previous = event.event_hash;
  }
  const types = new Set(ordered.map((event) => String(event.event_type || "").toLowerCase()));
  const completed = [...types].some((value) => value.includes("completed") || value.includes("acknowledged"));
  const claimed = [...types].some((value) => value.includes("claimed"));
  return claimed && completed;
}

function freshTimestamp(value, exportedAt, maxAgeSeconds) {
  if (!value) return false;
  const observed = Date.parse(value);
  const exported = Date.parse(exportedAt);
  if (!Number.isFinite(observed) || !Number.isFinite(exported)) return false;
  const ageSeconds = Math.max(0, (exported - observed) / 1000);
  return ageSeconds <= maxAgeSeconds;
}

function verifyBundleIntegrity(bundle) {
  if (!bundle || bundle.schema !== SCHEMA) throw new Error("unsupported controller evidence schema");
  const supplied = bundle.bundle_sha256;
  const { bundle_sha256: _ignored, ...unsigned } = bundle;
  if (!HEX64.test(String(supplied || "")) || sha256(unsigned) !== supplied) {
    throw new Error("controller evidence bundle SHA-256 mismatch");
  }
  if (!bundle.records || typeof bundle.records !== "object") throw new Error("records object missing");
  for (const [name, records] of Object.entries(bundle.records)) {
    const expected = bundle.collection_sha256?.[name];
    if (!HEX64.test(String(expected || "")) || sha256(records) !== expected) {
      throw new Error(`collection SHA-256 mismatch: ${name}`);
    }
  }
  return true;
}

function evaluateEvidence(bundle, phase, maxAgeSeconds) {
  verifyBundleIntegrity(bundle);
  const records = bundle.records;
  const selector = bundle.selector || {};
  const workerInstance = String(selector.worker_instance_id || "");
  const jobId = String(selector.selected_job_id || "");
  const contractId = String(selector.contract_id || "");

  const worker = records.workers.find((row) => row.instance_id === workerInstance);
  const workerPlatform = `${worker?.platform || ""} ${worker?.runtime || ""}`.toLowerCase();
  const workerIsAndroid = workerPlatform.includes("android") || workerPlatform.includes("termux");
  const workerFresh = Boolean(worker && freshTimestamp(worker.last_seen, bundle.exported_at, maxAgeSeconds));
  const job = records.jobs.find((row) => row.id === jobId);
  const jobBound = Boolean(job && job.worker_instance_id === workerInstance);
  const jobComplete = Boolean(jobBound && String(job.status || "").toLowerCase() === "completed");
  const lease = records.leases.find((row) => row.job_id === jobId && row.instance_id === workerInstance);
  const auditRows = records.audits.filter((row) => row.job_id === jobId);
  const auditChainValid = validAuditChain(auditRows);
  const result = records.results.find(
    (row) => row.job_id === jobId && row.worker_instance_id === workerInstance,
  );
  const resultSuccess = Boolean(
    result &&
      String(result.status || "").toLowerCase() === "success" &&
      (!result.postcondition_status || result.postcondition_status === "PASS"),
  );
  const leaseEventChainVerified = Boolean(lease && auditChainValid && resultSuccess);

  const judgeVerdict = records.verification_verdicts.find(
    (row) =>
      row.contract_id === contractId &&
      row.verdict === "VERIFIED" &&
      String(row.verifier || "").toLowerCase().includes("frost judge"),
  );
  const independentJudgeVerified = Boolean(contractId && judgeVerdict && HEX64.test(String(judgeVerdict.verdict_hash || "")));
  const contractObserved = Boolean(
    contractId && records.work_contracts.some((row) => row.contract_id === contractId),
  );

  const reboot = records.reboot_evidence.find(
    (row) =>
      row.instance_id === workerInstance &&
      row.status === "PASS" &&
      row.pre_boot_id &&
      row.post_boot_id &&
      row.pre_boot_id !== row.post_boot_id,
  );
  const postBootResultBound = Boolean(
    phase === "phase-b" && reboot && resultSuccess && result?.boot_id === reboot.post_boot_id,
  );
  const rebootControllerVerified = Boolean(reboot && postBootResultBound);
  const physicalGatePass = records.physical_gates.some((row) => row.status === "PASS");
  const latestFleetMetric = records.fleet_metrics[0] || null;

  const phaseAEligible = Boolean(
    workerIsAndroid &&
      workerFresh &&
      jobComplete &&
      leaseEventChainVerified &&
      contractObserved &&
      independentJudgeVerified,
  );
  const phaseBEligible = Boolean(phaseAEligible && rebootControllerVerified);

  return {
    schema: "frost.controller_evidence_verification.v1",
    phase,
    bundle_sha256: bundle.bundle_sha256,
    selector,
    checks: {
      worker_is_android_termux: workerIsAndroid,
      worker_fresh: workerFresh,
      job_bound_to_worker: jobBound,
      job_completed: jobComplete,
      lease_observed: Boolean(lease),
      audit_chain_valid: auditChainValid,
      result_success: resultSuccess,
      lease_event_chain_verified: leaseEventChainVerified,
      contract_observed: contractObserved,
      independent_judge_verified: independentJudgeVerified,
      reboot_controller_verified: rebootControllerVerified,
      physical_gate_pass_observed: physicalGatePass,
      fleet_event_chain_valid: latestFleetMetric?.event_chain_valid === true,
    },
    device_validated_controller_evidence_eligible: phaseAEligible,
    persistent_validated_controller_evidence_eligible: phaseBEligible,
    promotion_performed: false,
  };
}

function selfTest() {
  const a = { z: 2, a: [3, { y: true, x: null }] };
  const b = { a: [3, { x: null, y: true }], z: 2 };
  if (canonical(a) !== canonical(b) || sha256(a) !== sha256(b)) {
    throw new Error("canonical digest failed");
  }
  const base = {
    schema: SCHEMA,
    exported_at: "2026-08-21T23:00:00.000Z",
    app_id: DEFAULT_APP_ID,
    access_mode: "AUTHENTICATED_USER_RLS",
    selector: {
      worker_instance_id: "android-1",
      requested_job_id: "job-1",
      selected_job_id: "job-1",
      contract_id: "contract-1",
      proposal_key: "physical-1",
    },
    records: {
      workers: [{ instance_id: "android-1", platform: "android", runtime: "termux", last_seen: "2026-08-21T22:59:00.000Z", boot_id: "boot-b" }],
      jobs: [{ id: "job-1", worker_instance_id: "android-1", status: "completed" }],
      leases: [{ job_id: "job-1", instance_id: "android-1", lease_until: "2026-08-21T23:01:00.000Z" }],
      audits: [
        { job_id: "job-1", sequence: 1, event_type: "claimed", prev_hash: "", event_hash: "a".repeat(64) },
        { job_id: "job-1", sequence: 2, event_type: "completed", prev_hash: "a".repeat(64), event_hash: "b".repeat(64) },
      ],
      results: [{ job_id: "job-1", worker_instance_id: "android-1", status: "success", postcondition_status: "PASS", boot_id: "boot-b" }],
      reboot_evidence: [{ instance_id: "android-1", status: "PASS", pre_boot_id: "boot-a", post_boot_id: "boot-b" }],
      boot_sentinels: [],
      physical_gates: [{ proposal_key: "physical-1", status: "PASS" }],
      work_contracts: [{ contract_id: "contract-1" }],
      judge_role_results: [{ contract_id: "contract-1", role: "JUDGE", status: "PASS" }],
      verification_verdicts: [{ contract_id: "contract-1", verdict: "VERIFIED", verifier: "Frost Judge", verdict_hash: "c".repeat(64) }],
      fleet_metrics: [{ event_chain_valid: true }],
    },
  };
  base.collection_sha256 = Object.fromEntries(
    Object.entries(base.records).map(([name, value]) => [name, sha256(value)]),
  );
  const bundle = finalizeBundle(base);
  const phaseA = evaluateEvidence(bundle, "phase-a", 900);
  const phaseB = evaluateEvidence(bundle, "phase-b", 900);
  if (!phaseA.device_validated_controller_evidence_eligible) throw new Error("phase A synthetic verification failed");
  if (!phaseB.persistent_validated_controller_evidence_eligible) throw new Error("phase B synthetic verification failed");
  process.stdout.write(JSON.stringify({ status: "PASS", schema: SCHEMA }) + "\n");
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  if (options.selfTest) {
    selfTest();
    return;
  }
  if (options.verifyBundle) {
    const bundle = JSON.parse(await readFile(options.verifyBundle, "utf8"));
    process.stdout.write(
      JSON.stringify(evaluateEvidence(bundle, options.phase, options.maxAgeSeconds), null, 2) + "\n",
    );
    return;
  }
  if (!options.workerInstance) throw new Error("--worker-instance is required");
  if (!options.email) throw new Error("--email is required");
  if (!options.passwordStdin) {
    throw new Error("--password-stdin is required; password arguments are forbidden");
  }

  const password = await readPasswordFromStdin();
  const { createClient } = await import("@base44/sdk");
  const base44 = createClient({ appId: options.appId });
  await base44.auth.loginViaEmailPassword(options.email, password);
  const me = await base44.auth.me();
  const bundle = await collect(base44, options);
  bundle.authenticated_user = { id: me?.id || null, role: me?.role || null };
  process.stdout.write(JSON.stringify(finalizeBundle(bundle), null, 2) + "\n");
}

main().catch((error) => {
  process.stderr.write(
    JSON.stringify({ status: "BLOCKED", error: String(error?.message || error) }) + "\n",
  );
  process.exitCode = 2;
});
