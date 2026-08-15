'use strict';

const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const {spawnSync} = require('child_process');

const PROTOCOL = 'frost-call/1.0';
const VERIFICATION_SCHEMA = 'frost-independent-verification/1.0';
const MAX_FILE_BYTES = 1024 * 1024;
const RFC3339_INSTANT = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?(?:Z|[+-]\d{2}:\d{2})$/;
const WORKER_REPO_PATH = 'deploy/github/callable-worker-v1.0.0/worker.js';
const WORKFLOW_REPO_PATH = '.github/workflows/callable-fabric-worker.yml';
const FABRIC_REPO_PATH = 'deploy/vercel/callable-fabric-v1.1.0/lib/fabric.js';

function canonical(value) {
  if (value === null || typeof value !== 'object') return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`;
  return `{${Object.keys(value).sort().map((key) =>
    `${JSON.stringify(key)}:${canonical(value[key])}`).join(',')}}`;
}

function sha256(value) {
  return crypto.createHash('sha256').update(value).digest('hex');
}

function requireCondition(condition, message) {
  if (!condition) throw new Error(message);
}

function readBounded(filePath) {
  const stat = fs.statSync(filePath);
  requireCondition(stat.isFile(), `not a file: ${filePath}`);
  requireCondition(stat.size <= MAX_FILE_BYTES, `file exceeds ${MAX_FILE_BYTES} bytes: ${filePath}`);
  return fs.readFileSync(filePath);
}

function gitFileAt(commitSha, repoPath) {
  requireCondition(/^[0-9a-f]{40}$/.test(commitSha), 'provider_sha must be a 40-character lowercase git SHA');
  const result = spawnSync('git', ['show', `${commitSha}:${repoPath}`], {
    encoding: null,
    maxBuffer: MAX_FILE_BYTES + 1024,
  });
  if (result.status !== 0) {
    const error = Buffer.isBuffer(result.stderr) ? result.stderr.toString('utf8') : String(result.stderr || '');
    throw new Error(`unable to read ${repoPath} at ${commitSha}: ${error.trim()}`);
  }
  requireCondition(result.stdout.length <= MAX_FILE_BYTES, `historical file exceeds ${MAX_FILE_BYTES} bytes: ${repoPath}`);
  return result.stdout;
}

function requestIdentity(raw) {
  let request;
  try {
    request = JSON.parse(raw.toString('utf8'));
  } catch (_) {
    return {request: null, request_sha256: sha256(raw), idempotency_key: null};
  }
  requireCondition(request && typeof request === 'object' && !Array.isArray(request), 'request must be a JSON object');
  const requestSha256 = sha256(Buffer.from(canonical(request), 'utf8'));
  const candidate = request.idempotency_key ?? request.context?.idempotency_key ?? requestSha256;
  requireCondition(typeof candidate === 'string' && candidate.trim(), 'idempotency_key must be a non-empty string');
  return {
    request,
    request_sha256: requestSha256,
    idempotency_key: candidate.trim(),
  };
}

function verifyReceipt(receipt) {
  requireCondition(receipt && typeof receipt === 'object', 'receipt missing');
  requireCondition(typeof receipt.record_hash === 'string', 'receipt record_hash missing');
  const body = {...receipt};
  const expected = body.record_hash;
  delete body.record_hash;
  requireCondition(
    sha256(Buffer.from(canonical(body), 'utf8')) === expected,
    'receipt hash mismatch',
  );
}

function verifyEnvelope(result) {
  requireCondition(result && typeof result === 'object' && !Array.isArray(result), 'result must be an object');
  requireCondition(typeof result.envelope_hash === 'string', 'envelope_hash missing');
  const body = {...result};
  const expected = body.envelope_hash;
  delete body.envelope_hash;
  requireCondition(
    sha256(Buffer.from(canonical(body), 'utf8')) === expected,
    'envelope hash mismatch',
  );
}

function verifyRequestExpiry(request, result, checks) {
  const expiresAt = request?.context?.expires_at;
  if (expiresAt === undefined || expiresAt === null) {
    requireCondition(result.request_expiry === undefined, 'unexpected request_expiry metadata');
    checks.push('request_expiry:NOT_REQUESTED');
    return;
  }

  const validFormat = typeof expiresAt === 'string' && RFC3339_INSTANT.test(expiresAt);
  const expiresAtMs = validFormat ? Date.parse(expiresAt) : Number.NaN;
  if (!validFormat || !Number.isFinite(expiresAtMs)) {
    requireCondition(result.error?.type === 'InvalidExpiry', 'invalid expiry was not rejected');
    requireCondition(result.request_expiry?.status === 'INVALID', 'invalid expiry status missing');
    requireCondition(result.request_expiry?.expires_at === expiresAt, 'invalid expiry value mismatch');
    checks.push('request_expiry:INVALID_REJECTED');
    return;
  }

  requireCondition(result.request_expiry, 'request expiry evidence missing');
  requireCondition(result.request_expiry.expires_at === expiresAt, 'request expiry value mismatch');
  requireCondition(
    typeof result.request_expiry.observed_at === 'string',
    'request expiry observed_at missing',
  );
  const observedAtMs = Date.parse(result.request_expiry.observed_at);
  requireCondition(Number.isFinite(observedAtMs), 'request expiry observed_at invalid');

  if (result.error?.type === 'StaleRequest') {
    requireCondition(result.request_expiry.status === 'EXPIRED', 'stale request status must be EXPIRED');
    requireCondition(observedAtMs >= expiresAtMs, 'stale request observed before expiry');
    requireCondition(result.ok === false, 'stale request cannot be successful');
    checks.push('request_expiry:EXPIRED_VERIFIED');
    return;
  }

  requireCondition(result.request_expiry.status === 'FRESH', 'non-stale request status must be FRESH');
  requireCondition(observedAtMs < expiresAtMs, 'fresh request observed at or after expiry');
  checks.push('request_expiry:FRESH_VERIFIED');
}

function verifySourceAttestation(result, checks) {
  const attestation = result.source_attestation;
  if (!attestation) {
    checks.push('source_attestation:UNAVAILABLE_LEGACY');
    return {
      status: 'UNAVAILABLE_LEGACY',
      provider_code_identity_sha256: null,
    };
  }

  requireCondition(attestation.schema === 'frost-source-attestation/1.0', 'unsupported source attestation schema');
  requireCondition(attestation.semantic_core && attestation.provider_runtime, 'source attestation sections missing');
  requireCondition(
    attestation.semantic_core.canonical_git_sha === result.canonical_git_sha,
    'semantic canonical_git_sha mismatch',
  );
  requireCondition(
    attestation.semantic_core.source_identity_sha256 === result.source_identity_sha256,
    'semantic source identity mismatch',
  );
  requireCondition(
    attestation.semantic_core.deployment_adapter_sha256 === result.deployment_adapter_sha256,
    'semantic adapter identity mismatch',
  );
  requireCondition(
    attestation.provider_runtime.checked_out_sha === result.provider_sha,
    'provider checked_out_sha mismatch',
  );

  const semanticCoreBytes = gitFileAt(result.provider_sha, FABRIC_REPO_PATH);
  const workerBytes = gitFileAt(result.provider_sha, WORKER_REPO_PATH);
  const workflowBytes = gitFileAt(result.provider_sha, WORKFLOW_REPO_PATH);
  const semanticCoreFileSha256 = sha256(semanticCoreBytes);
  const workerSourceSha256 = sha256(workerBytes);
  const workflowSourceSha256 = sha256(workflowBytes);

  requireCondition(
    attestation.semantic_core.file_sha256 === semanticCoreFileSha256,
    'semantic core file hash mismatch',
  );
  requireCondition(
    attestation.provider_runtime.worker_source_sha256 === workerSourceSha256,
    'worker source hash mismatch',
  );
  requireCondition(
    attestation.provider_runtime.workflow_source_sha256 === workflowSourceSha256,
    'workflow source hash mismatch',
  );

  const expectedProviderCodeIdentity = sha256(Buffer.from(canonical({
    provider: 'github-actions',
    semantic_core_file_sha256: semanticCoreFileSha256,
    worker_source_sha256: workerSourceSha256,
    workflow_source_sha256: workflowSourceSha256,
  }), 'utf8'));
  requireCondition(
    attestation.provider_code_identity_sha256 === expectedProviderCodeIdentity,
    'provider code identity mismatch',
  );
  checks.push('source_attestation:VERIFIED_HISTORICAL_BYTES');
  return {
    status: 'VERIFIED',
    provider_code_identity_sha256: expectedProviderCodeIdentity,
  };
}

function verifySemanticResponse(result, checks) {
  if (!result.response) {
    checks.push('semantic_response:NOT_PRESENT');
    return;
  }
  const response = result.response;
  if (response.receipt) {
    verifyReceipt(response.receipt);
    requireCondition(
      response.receipt.canonical_git_sha === result.canonical_git_sha,
      'receipt canonical_git_sha mismatch',
    );
    requireCondition(
      response.receipt.source_identity_sha256 === result.source_identity_sha256,
      'receipt source identity mismatch',
    );
    checks.push('semantic_receipt:VERIFIED');
  }
  if (response.ok === true) {
    requireCondition(response.result !== undefined, 'successful response result missing');
    requireCondition(response.diagnostics && response.receipt, 'successful response verification fields missing');
    const resultHash = sha256(Buffer.from(canonical(response.result), 'utf8'));
    requireCondition(response.diagnostics.result_hash === resultHash, 'diagnostic result hash mismatch');
    requireCondition(response.receipt.result_hash === resultHash, 'receipt result hash mismatch');
    checks.push('semantic_result_hash:VERIFIED');
  }
}

function verifyPaths(requestPath, resultPath, verificationPath) {
  const requestRaw = readBounded(requestPath);
  const resultRaw = readBounded(resultPath);
  const identity = requestIdentity(requestRaw);
  const result = JSON.parse(resultRaw.toString('utf8'));
  const checks = [];

  requireCondition(result.protocol === PROTOCOL, `result protocol must be ${PROTOCOL}`);
  requireCondition(result.provider === 'github-actions', 'result provider must be github-actions');
  requireCondition(result.request_sha256 === identity.request_sha256, 'request SHA-256 mismatch');
  if (result.idempotency_key === null || result.idempotency_key === undefined) {
    requireCondition(!result.source_attestation, 'attested result is missing idempotency_key');
    checks.push('idempotency_key:UNAVAILABLE_LEGACY');
  } else {
    requireCondition(result.idempotency_key === identity.idempotency_key, 'idempotency key mismatch');
    checks.push('idempotency_key:VERIFIED');
  }
  checks.push('request_identity:VERIFIED');

  verifyEnvelope(result);
  checks.push('envelope_hash:VERIFIED');
  verifyRequestExpiry(identity.request, result, checks);
  verifySemanticResponse(result, checks);
  const source = verifySourceAttestation(result, checks);

  const verificationStatus = source.status === 'VERIFIED'
    ? 'VERIFIED'
    : 'VERIFIED_LEGACY_LIMITED';
  const body = {
    schema: VERIFICATION_SCHEMA,
    verifier: 'github-callable-independent-verifier',
    verification_status: verificationStatus,
    request_sha256: result.request_sha256,
    result_file_sha256: sha256(resultRaw),
    result_envelope_hash: result.envelope_hash,
    source_attestation_status: source.status,
    provider_code_identity_sha256: source.provider_code_identity_sha256,
    verifier_source_sha256: sha256(fs.readFileSync(__filename)),
    checks,
  };
  const verification = {
    ...body,
    verification_hash: sha256(Buffer.from(canonical(body), 'utf8')),
  };
  fs.mkdirSync(path.dirname(verificationPath), {recursive: true});
  fs.writeFileSync(verificationPath, `${JSON.stringify(verification, null, 2)}\n`, {flag: 'wx'});
  return verification;
}

function main(argv) {
  if (argv.length !== 3) {
    throw new Error('usage: node verifier.js REQUEST_JSON RESULT_JSON VERIFICATION_JSON');
  }
  const verification = verifyPaths(argv[0], argv[1], argv[2]);
  process.stdout.write(`${JSON.stringify({
    ok: true,
    verification_status: verification.verification_status,
    verification_hash: verification.verification_hash,
  })}\n`);
}

if (require.main === module) main(process.argv.slice(2));
module.exports = {
  PROTOCOL,
  VERIFICATION_SCHEMA,
  canonical,
  sha256,
  verifyPaths,
};
