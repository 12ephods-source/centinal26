#!/usr/bin/env node

import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import process from "node:process";

const DEFAULT_APP_ID = "6a484dc22829dd2fd4a7bcd1";
const SCHEMA = "frost.controller_evidence_export.v1";

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
  return createHash("sha256").update(typeof value === "string" ? value : canonical(value)).digest("hex");
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
    else throw new Error(`unknown argument: ${arg}`);
  }
  if (!Number.isInteger(result.limit) || result.limit < 1 || result.limit > 500) {
    throw new Error("--limit must be an integer from 1 to 500");
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
    jobs = [
      ...(await maybeGet(base44.entities.AutomationJob, selectedJobId)),
      ...jobs,
    ];
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

  const fleetMetrics = await base44.entities.AutomationFleetMetric.list("-captured_at", 20, 0);

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
    fleet_metrics: asArray(fleetMetrics),
  };
  const collectionSha256 = Object.fromEntries(
    Object.entries(records).map(([name, value]) => [name, sha256(value)]),
  );
  const bundle = {
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
  bundle.bundle_sha256 = sha256(bundle);
  return bundle;
}

function selfTest() {
  const a = { z: 2, a: [3, { y: true, x: null }] };
  const b = { a: [3, { x: null, y: true }], z: 2 };
  if (canonical(a) !== canonical(b)) throw new Error("canonical ordering failed");
  if (sha256(a) !== sha256(b)) throw new Error("canonical digest failed");
  const probe = {
    schema: SCHEMA,
    records: { workers: [] },
    collection_sha256: { workers: sha256([]) },
  };
  probe.bundle_sha256 = sha256(probe);
  if (!/^[0-9a-f]{64}$/.test(probe.bundle_sha256)) throw new Error("digest format failed");
  process.stdout.write(JSON.stringify({ status: "PASS", schema: SCHEMA }) + "\n");
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  if (options.selfTest) {
    selfTest();
    return;
  }
  if (!options.workerInstance) throw new Error("--worker-instance is required");
  if (!options.email) throw new Error("--email is required");
  if (!options.passwordStdin) throw new Error("--password-stdin is required; password arguments are forbidden");

  const password = await readPasswordFromStdin();
  const { createClient } = await import("@base44/sdk");
  const base44 = createClient({ appId: options.appId });
  await base44.auth.loginViaEmailPassword(options.email, password);
  const me = await base44.auth.me();
  const bundle = await collect(base44, options);
  bundle.authenticated_user = {
    id: me?.id || null,
    role: me?.role || null,
  };
  bundle.bundle_sha256 = sha256({ ...bundle, bundle_sha256: undefined });
  process.stdout.write(JSON.stringify(bundle, null, 2) + "\n");
}

main().catch((error) => {
  process.stderr.write(JSON.stringify({ status: "BLOCKED", error: String(error?.message || error) }) + "\n");
  process.exitCode = 2;
});
