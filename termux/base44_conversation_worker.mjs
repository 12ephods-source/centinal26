import { createClient } from "@base44/sdk";
import { createHash, randomUUID } from "node:crypto";
import { spawn } from "node:child_process";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";

const PROTOCOL = "frost-call/1.0";
const VERSION = "1.0.0-conversation-termux";
const ALLOWED = new Set(["conversation.ingest", "conversation.status"]);
const APP_ID = process.env.BASE44_APP_ID || "6a484dc22829dd2fd4a7bcd1";
const EMAIL = process.env.BASE44_WORKER_EMAIL || process.env.BASE44_EMAIL || "";
const TOKEN = process.env.BASE44_AUTH_TOKEN || process.env.BASE44_TOKEN || "";
const PASSWORD = process.env.BASE44_PASSWORD || "";
const PYTHON = process.env.FROST_PYTHON || "python3";
const POLL_SECONDS = Math.max(5, Number(process.env.FROST_BRIDGE_POLL_SECONDS || "8"));
const HEARTBEAT_SECONDS = Math.max(15, Number(process.env.FROST_BRIDGE_HEARTBEAT_SECONDS || "30"));
const LEASE_SECONDS = Math.max(60, Number(process.env.FROST_BRIDGE_LEASE_SECONDS || "300"));
const MAX_OUTPUT_BYTES = Math.max(65536, Number(process.env.FROST_BRIDGE_MAX_OUTPUT_BYTES || "1000000"));
const ROOT = process.env.FROST_CONVERSATION_WORKER_HOME || path.join(os.homedir(), ".frost_conversation_worker");
const STATE = path.join(ROOT, "state");
const INSTANCE_FILE = path.join(STATE, "instance_id");
const BOOT_ID_FILE = "/proc/sys/kernel/random/boot_id";

if (!EMAIL) {
  console.error("BASE44_WORKER_EMAIL/BASE44_EMAIL is required");
  process.exit(2);
}
if (!TOKEN && !PASSWORD) {
  console.error("BASE44_AUTH_TOKEN/BASE44_TOKEN or BASE44_PASSWORD is required");
  process.exit(2);
}

await mkdir(STATE, { recursive: true, mode: 0o700 });
let instanceId = "";
try { instanceId = (await readFile(INSTANCE_FILE, "utf8")).trim(); } catch {}
if (!instanceId) {
  instanceId = `termux-conversation-${randomUUID()}`;
  await writeFile(INSTANCE_FILE, `${instanceId}\n`, { mode: 0o600 });
}
let bootId = "unknown";
try { bootId = (await readFile(BOOT_ID_FILE, "utf8")).trim(); } catch {}

let base44;
if (TOKEN) {
  base44 = createClient({ appId: APP_ID, token: TOKEN });
} else {
  base44 = createClient({ appId: APP_ID });
  await base44.auth.loginViaEmailPassword(EMAIL, PASSWORD);
}

function now() { return new Date().toISOString(); }
function sleep(ms) { return new Promise(resolve => setTimeout(resolve, ms)); }
function sha256(text) { return createHash("sha256").update(text).digest("hex"); }
function truncate(text, limit = 12000) {
  const value = String(text ?? "");
  return value.length <= limit ? value : value.slice(0, limit) + "…";
}
function parseJson(text, fallback = {}) {
  if (!text) return fallback;
  try { return JSON.parse(text); } catch { return fallback; }
}

let workerRecordId = "";
async function upsertWorker(status = "online", extra = {}) {
  const payload = {
    worker_email: EMAIL,
    instance_id: instanceId,
    status,
    last_seen: now(),
    version: VERSION,
    capabilities_json: JSON.stringify({
      role: "persistent-conversation-termux-worker",
      operations: [...ALLOWED],
      arbitrary_shell: false,
      hash_pinned_local_capabilities: true,
      responder_feedback_loop: true,
      boot_id: bootId,
      ...extra,
    }),
    protocol_versions_json: JSON.stringify([PROTOCOL]),
    supported_operations_json: JSON.stringify([...ALLOWED]),
    platform: "android/termux",
    runtime: `node/${process.version}`,
    max_concurrency: 1,
    boot_id: bootId,
    heartbeat_interval_seconds: HEARTBEAT_SECONDS,
    lease_seconds: LEASE_SECONDS,
    supervisor_status: status,
  };
  if (!workerRecordId) {
    const rows = await base44.entities.AutomationWorker.filter(
      { worker_email: EMAIL, instance_id: instanceId }, "-updated_date", 1, 0
    ).catch(() => []);
    workerRecordId = rows?.[0]?.id || "";
  }
  if (workerRecordId) {
    await base44.entities.AutomationWorker.update(workerRecordId, payload);
  } else {
    const created = await base44.entities.AutomationWorker.create(payload);
    workerRecordId = created?.id || "";
  }
}

async function audit(job, eventType, details = {}) {
  const rows = await base44.entities.AutomationAudit.filter(
    { job_id: job.id, worker_email: EMAIL }, "-created_date", 1, 0
  ).catch(() => []);
  const prev = rows?.[0] || null;
  const sequence = Number(prev?.sequence || 0) + 1;
  const prevHash = prev?.event_hash || "";
  const eventTime = now();
  const detailsJson = JSON.stringify(details);
  const eventHash = sha256([
    job.id,
    EMAIL,
    PROTOCOL,
    job.request_id || "",
    String(sequence),
    eventType,
    eventTime,
    detailsJson,
    prevHash,
  ].join("\n"));
  await base44.entities.AutomationAudit.create({
    job_id: job.id,
    worker_email: EMAIL,
    event_type: eventType,
    event_time: eventTime,
    details_json: detailsJson,
    prev_hash: prevHash,
    event_hash: eventHash,
    protocol_version: PROTOCOL,
    request_id: job.request_id || "",
    sequence,
    actor: instanceId,
  });
}

function normalizedRequest(job) {
  const payload = parseJson(job.payload_json, parseJson(job.parameters_json, {}));
  const requestId = String(job.request_id || payload.request_id || job.id);
  const operation = String(job.operation || payload.operation || "");
  const conversationId = String(
    payload.conversation_id || payload.session_id || `base44:${EMAIL}:${requestId}`
  );
  const request = {
    operation,
    request_id: requestId,
    conversation_id: conversationId,
  };
  if (operation === "conversation.ingest") {
    if (typeof payload.content !== "string" || !payload.content.length) {
      throw new Error("conversation.ingest payload requires non-empty string content");
    }
    request.content = payload.content;
    if (payload.provider) request.provider = payload.provider;
    if (payload.model) request.model = payload.model;
    if (payload.max_steps) request.max_steps = payload.max_steps;
    if (payload.max_tool_calls) request.max_tool_calls = payload.max_tool_calls;
    if (payload.max_wall_seconds) request.max_wall_seconds = payload.max_wall_seconds;
  }
  return request;
}

async function runConversationCli(job, request) {
  const timeoutSeconds = Math.max(30, Number(job.timeout_seconds || request.max_wall_seconds || 900) + 60);
  return await new Promise((resolve, reject) => {
    const child = spawn(PYTHON, ["-m", "frost_core.conversation_cli"], {
      cwd: os.homedir(),
      env: process.env,
      stdio: ["pipe", "pipe", "pipe"],
      shell: false,
    });
    let stdout = Buffer.alloc(0);
    let stderr = Buffer.alloc(0);
    let killedForOutput = false;
    const append = (current, chunk) => {
      const combined = Buffer.concat([current, chunk]);
      if (combined.length > MAX_OUTPUT_BYTES) {
        killedForOutput = true;
        child.kill("SIGTERM");
        return combined.subarray(0, MAX_OUTPUT_BYTES);
      }
      return combined;
    };
    child.stdout.on("data", chunk => { stdout = append(stdout, chunk); });
    child.stderr.on("data", chunk => { stderr = append(stderr, chunk); });

    const heartbeat = setInterval(async () => {
      const stamp = now();
      const leaseUntil = new Date(Date.now() + LEASE_SECONDS * 1000).toISOString();
      try {
        await base44.entities.AutomationJob.update(job.id, {
          heartbeat_at: stamp,
          lease_until: leaseUntil,
        });
        await upsertWorker("busy", { active_job_id: job.id });
      } catch (error) {
        console.error(`[conversation-worker] heartbeat failure job=${job.id}: ${error}`);
      }
    }, HEARTBEAT_SECONDS * 1000);
    heartbeat.unref();

    const timer = setTimeout(() => {
      child.kill("SIGTERM");
      setTimeout(() => child.kill("SIGKILL"), 5000).unref();
    }, timeoutSeconds * 1000);
    timer.unref();

    child.on("error", error => {
      clearInterval(heartbeat);
      clearTimeout(timer);
      reject(error);
    });
    child.on("close", code => {
      clearInterval(heartbeat);
      clearTimeout(timer);
      if (killedForOutput) {
        reject(new Error(`conversation CLI exceeded ${MAX_OUTPUT_BYTES} bytes`));
        return;
      }
      const outText = stdout.toString("utf8").trim();
      const errText = stderr.toString("utf8").trim();
      let parsed;
      try { parsed = JSON.parse(outText); }
      catch { parsed = { ok: false, error: { type: "InvalidWorkerOutput", message: outText } }; }
      resolve({ code: code ?? 255, stdout: outText, stderr: errText, parsed });
    });
    child.stdin.end(JSON.stringify(request));
  });
}

async function execute(job) {
  if (job.job_type !== "frost_call" || !ALLOWED.has(job.operation)) return;
  if (job.protocol_version && job.protocol_version !== PROTOCOL) {
    throw new Error(`unsupported protocol ${job.protocol_version}`);
  }
  const request = normalizedRequest(job);
  const claimedAt = now();
  const leaseUntil = new Date(Date.now() + LEASE_SECONDS * 1000).toISOString();
  await base44.entities.AutomationJob.update(job.id, {
    status: "claimed",
    worker_instance_id: instanceId,
    claimed_at: claimedAt,
    heartbeat_at: claimedAt,
    lease_until: leaseUntil,
    attempt: Number(job.attempt || 0) + 1,
  });
  await audit(job, "claimed", { operation: job.operation, lease_until: leaseUntil });

  const startedAt = now();
  await base44.entities.AutomationJob.update(job.id, {
    status: "running",
    started_at: startedAt,
    heartbeat_at: startedAt,
  });
  await audit(job, "running", { operation: job.operation, conversation_id: request.conversation_id });

  const run = await runConversationCli(job, request);
  if (run.code !== 0 || run.parsed?.ok !== true) {
    const detail = run.parsed?.error?.message || run.stderr || run.stdout || `exit=${run.code}`;
    throw new Error(detail);
  }
  const result = run.parsed.result;
  const finishedAt = now();
  const isStatus = job.operation === "conversation.status";
  const postconditionStatus = isStatus ? "PASS" : "REVIEW";
  const responseText = isStatus ? "" : String(result?.response || "");
  const summary = isStatus
    ? `conversation.status ${JSON.stringify(result)}`
    : `conversation.ingest completed response_sha256=${result?.response_sha256 || sha256(responseText)}`;
  const provenance = {
    worker: VERSION,
    worker_instance_id: instanceId,
    boot_id: bootId,
    platform: "android/termux",
    protocol_version: PROTOCOL,
    model_output_validation: isStatus ? "deterministic_status" : "unverified_model_output",
  };
  await base44.entities.AutomationResult.create({
    job_id: job.id,
    worker_email: EMAIL,
    result_type: "frost_call",
    created_at_client: finishedAt,
    summary: truncate(summary, 12000),
    protocol_version: PROTOCOL,
    request_id: job.request_id || request.request_id,
    status: "success",
    result_json: JSON.stringify(result),
    payload_json: JSON.stringify(run.parsed),
    artifacts_json: "[]",
    provenance_json: JSON.stringify(provenance),
    warnings_json: isStatus ? "[]" : JSON.stringify(["AI response is not independent verification."]),
    errors_json: "[]",
    metrics_json: JSON.stringify({ steps: result?.steps || 0, tool_calls: result?.tool_calls || 0 }),
    stdout_text: truncate(run.stdout, 100000),
    stderr_text: truncate(run.stderr, 100000),
    exit_code: run.code,
    postcondition_status: postconditionStatus,
    execution_environment: "android/termux",
    started_at_client: startedAt,
    finished_at_client: finishedAt,
    worker_instance_id: instanceId,
    boot_id: bootId,
  });
  await base44.entities.AutomationJob.update(job.id, {
    status: "completed",
    finished_at: finishedAt,
    heartbeat_at: finishedAt,
    lease_until: finishedAt,
    result_summary: truncate(summary, 12000),
    postcondition_status: postconditionStatus,
    error_message: "",
  });
  await audit(job, "completed", {
    operation: job.operation,
    postcondition_status: postconditionStatus,
    response_sha256: result?.response_sha256 || null,
  });
}

async function fail(job, error) {
  const stamp = now();
  const message = truncate(error?.stack || error, 12000);
  await base44.entities.AutomationJob.update(job.id, {
    status: "failed",
    finished_at: stamp,
    heartbeat_at: stamp,
    lease_until: stamp,
    error_message: message,
    postcondition_status: "FAIL",
  }).catch(() => {});
  await audit(job, "failed", { error: message }).catch(() => {});
}

let lastHeartbeat = 0;
await upsertWorker("online");
console.log(`[conversation-worker] authenticated=${EMAIL} instance=${instanceId} poll=${POLL_SECONDS}s`);

while (true) {
  try {
    if (Date.now() - lastHeartbeat >= HEARTBEAT_SECONDS * 1000) {
      await upsertWorker("online");
      lastHeartbeat = Date.now();
    }
    const jobs = await base44.entities.AutomationJob.filter(
      { status: "queued", worker_email: EMAIL, job_type: "frost_call" }, "-priority", 20, 0
    );
    for (const job of jobs || []) {
      if (!ALLOWED.has(job.operation)) continue;
      try { await execute(job); }
      catch (error) { await fail(job, error); }
      await upsertWorker("online", { last_job_id: job.id });
    }
  } catch (error) {
    console.error(`[conversation-worker] poll error ${now()}: ${error?.stack || error}`);
    try { await upsertWorker("degraded"); } catch {}
  }
  await sleep(POLL_SECONDS * 1000);
}
