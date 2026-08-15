'use strict';

const assert = require('assert');
const fs = require('fs');
const os = require('os');
const path = require('path');
const {spawnSync} = require('child_process');
const {
  APPROVED_SEMANTIC_CORE_FILE_SHA256,
  REQUIRED_SIDE_EFFECT_PROTOCOL,
  processFile,
  providerEffectDecision,
} = require('./worker');
const {canonical, sha256, verifyPaths} = require('./verifier');

function gitHead() {
  const result = spawnSync('git', ['rev-parse', 'HEAD'], {encoding: 'utf8'});
  if (result.status !== 0) throw new Error(result.stderr || 'git rev-parse failed');
  return result.stdout.trim();
}

function request(key, operation, context = {}) {
  return {
    protocol: 'frost-call/1.0',
    kind: 'invoke',
    idempotency_key: key,
    service_id: 'frost.callable.fabric',
    operation,
    arguments: operation === 'frost.diagnostics.dangerous_demo_policy_test'
      ? {target: key}
      : {text: key},
    context: {
      caller: 'effect-doctor',
      role: 'operator',
      approved: false,
      request_id: key,
      ...context,
    },
  };
}

function provider(runId) {
  return {
    run_id: runId,
    sha: gitHead(),
    ref: 'refs/heads/effect-doctor',
  };
}

const readOnlyRequest = request(
  'effect-read-only',
  'frost.diagnostics.sha256',
);
const readOnlyDecision = providerEffectDecision(readOnlyRequest);
assert.strictEqual(readOnlyDecision.allowed, true);
assert.strictEqual(readOnlyDecision.status, 'READ_ONLY');

const negativeControlRequest = request(
  'effect-negative-control',
  'frost.diagnostics.dangerous_demo_policy_test',
);
const negativeControlDecision = providerEffectDecision(negativeControlRequest);
assert.strictEqual(negativeControlDecision.allowed, true);
assert.strictEqual(negativeControlDecision.status, 'EFFECT_FREE_NEGATIVE_CONTROL');

const futureSideEffectRequest = request(
  'effect-future-side-effect',
  'frost.future.side_effect',
);
const futureSideEffectDecision = providerEffectDecision(futureSideEffectRequest);
assert.strictEqual(futureSideEffectDecision.allowed, false);
assert.strictEqual(futureSideEffectDecision.status, 'SIDE_EFFECT_PROTOCOL_REQUIRED');
assert.strictEqual(
  futureSideEffectDecision.required_protocol,
  REQUIRED_SIDE_EFFECT_PROTOCOL,
);

const driftDecision = providerEffectDecision(readOnlyRequest, {
  semantic_core_file_sha256: '0'.repeat(64),
});
assert.strictEqual(driftDecision.allowed, false);
assert.strictEqual(driftDecision.status, 'SEMANTIC_CORE_POLICY_DRIFT');
assert.strictEqual(
  driftDecision.approved_semantic_core_file_sha256,
  APPROVED_SEMANTIC_CORE_FILE_SHA256,
);

const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'frost-effect-doctor-'));
try {
  const requests = path.join(temp, 'requests');
  const results = path.join(temp, 'results');
  const verifications = path.join(temp, 'verifications');
  fs.mkdirSync(requests);
  fs.mkdirSync(results);
  fs.mkdirSync(verifications);

  const blockedPath = path.join(requests, 'blocked.json');
  const blockedResult = path.join(results, 'blocked.json');
  const blockedVerification = path.join(verifications, 'blocked.json');
  fs.writeFileSync(blockedPath, JSON.stringify(futureSideEffectRequest));
  processFile(blockedPath, blockedResult, provider('effect-blocked-run'));
  const blockedEnvelope = JSON.parse(fs.readFileSync(blockedResult, 'utf8'));
  assert.strictEqual(blockedEnvelope.ok, false);
  assert.strictEqual(blockedEnvelope.error.type, 'SideEffectProtocolRequired');
  assert.strictEqual(blockedEnvelope.response, undefined);
  const blockedVerified = verifyPaths(
    blockedPath,
    blockedResult,
    blockedVerification,
  );
  assert.ok(
    blockedVerified.checks.includes(
      'provider_effect_policy:SIDE_EFFECT_PROTOCOL_REQUIRED_VERIFIED',
    ),
  );

  const deniedPath = path.join(requests, 'negative-control-denied.json');
  const deniedResult = path.join(results, 'negative-control-denied.json');
  const deniedVerification = path.join(verifications, 'negative-control-denied.json');
  fs.writeFileSync(deniedPath, JSON.stringify(negativeControlRequest));
  processFile(deniedPath, deniedResult, provider('effect-negative-denied-run'));
  const deniedEnvelope = JSON.parse(fs.readFileSync(deniedResult, 'utf8'));
  assert.strictEqual(deniedEnvelope.ok, true);
  assert.strictEqual(deniedEnvelope.response.ok, false);
  assert.strictEqual(deniedEnvelope.response.error.type, 'DENIED');
  const deniedVerified = verifyPaths(deniedPath, deniedResult, deniedVerification);
  assert.ok(
    deniedVerified.checks.includes(
      'provider_effect_policy:EFFECT_FREE_NEGATIVE_CONTROL_VERIFIED',
    ),
  );

  const approvedNegative = request(
    'effect-negative-control-approved',
    'frost.diagnostics.dangerous_demo_policy_test',
    {role: 'admin', approved: true},
  );
  const approvedPath = path.join(requests, 'negative-control-approved.json');
  const approvedResult = path.join(results, 'negative-control-approved.json');
  const approvedVerification = path.join(verifications, 'negative-control-approved.json');
  fs.writeFileSync(approvedPath, JSON.stringify(approvedNegative));
  processFile(approvedPath, approvedResult, provider('effect-negative-approved-run'));
  const approvedEnvelope = JSON.parse(fs.readFileSync(approvedResult, 'utf8'));
  assert.strictEqual(approvedEnvelope.ok, true);
  assert.strictEqual(approvedEnvelope.response.ok, true);
  assert.strictEqual(approvedEnvelope.response.result.executed, false);
  const approvedVerified = verifyPaths(approvedPath, approvedResult, approvedVerification);
  assert.ok(
    approvedVerified.checks.includes(
      'provider_effect_policy:EFFECT_FREE_NEGATIVE_CONTROL_VERIFIED',
    ),
  );

  const readOnlyPath = path.join(requests, 'read-only.json');
  const readOnlyResult = path.join(results, 'read-only.json');
  fs.writeFileSync(readOnlyPath, JSON.stringify(readOnlyRequest));
  processFile(readOnlyPath, readOnlyResult, provider('effect-read-only-run'));
  const forgedPath = path.join(results, 'read-only-forged-policy.json');
  const forged = JSON.parse(fs.readFileSync(readOnlyResult, 'utf8'));
  forged.provider_effect_policy = {
    allowed: false,
    status: 'SIDE_EFFECT_PROTOCOL_REQUIRED',
    operation: 'frost.diagnostics.sha256',
    semantic_core_file_sha256: APPROVED_SEMANTIC_CORE_FILE_SHA256,
    required_protocol: REQUIRED_SIDE_EFFECT_PROTOCOL,
  };
  delete forged.envelope_hash;
  forged.envelope_hash = sha256(Buffer.from(canonical(forged), 'utf8'));
  fs.writeFileSync(forgedPath, `${JSON.stringify(forged, null, 2)}\n`);
  assert.throws(
    () => verifyPaths(
      readOnlyPath,
      forgedPath,
      path.join(verifications, 'read-only-forged-policy.json'),
    ),
    /provider effect policy decision mismatch/,
  );

  console.log(JSON.stringify({
    ok: true,
    tests: 8,
    read_only_allow: true,
    negative_control_pin: true,
    future_side_effect_block: true,
    semantic_core_drift_block: true,
    connected_block_envelope: true,
    guardian_negative_control: true,
    approved_negative_control_still_effect_free: true,
    forged_effect_policy_rejection: true,
  }, null, 2));
} finally {
  fs.rmSync(temp, {recursive: true, force: true});
}
