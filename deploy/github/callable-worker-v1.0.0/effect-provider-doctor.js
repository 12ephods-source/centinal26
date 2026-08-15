'use strict';

const assert = require('assert');
const fs = require('fs');
const os = require('os');
const path = require('path');
const {
  QUALIFICATION_CAPABILITY,
  prepareFile,
  executeFile,
  recordFile,
  readJson,
  markerPathFor,
  verifyHash,
} = require('./effect-provider');
const {
  verifyDeniedFile,
  verifyExecutedFile,
} = require('./effect-provider-verifier');

const future = '2099-01-01T00:00:00Z';
const sourceSha = '1'.repeat(40);

function writeJson(filePath, value) {
  fs.mkdirSync(path.dirname(filePath), {recursive: true});
  fs.writeFileSync(filePath, `${JSON.stringify(value, null, 2)}\n`);
}

function approvedRequest(overrides = {}) {
  return {
    protocol: 'frost-effect/1.0',
    request_id: 'effect-provider-doctor-001',
    capability: QUALIFICATION_CAPABILITY,
    idempotency_key: 'effect-provider-doctor-idempotency-001',
    actor: 'doctor',
    payload: {
      marker: 'github-actions-connected-qualification',
      value: 'provider-effect-doctor',
    },
    expires_at: future,
    ...overrides,
  };
}

const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'frost-effect-provider-doctor-'));
const originalCwd = process.cwd();
try {
  process.chdir(temp);
  const requestDir = path.join(temp, 'runtime', 'effect-requests');
  const intentDir = path.join(temp, 'runtime', 'effect-intents');
  const resultDir = path.join(temp, 'runtime', 'effect-results');
  const verificationDir = path.join(temp, 'runtime', 'effect-verifications');
  fs.mkdirSync(requestDir, {recursive: true});

  const request = approvedRequest();
  const requestPath = path.join(requestDir, 'approved.json');
  const intentPath = path.join(intentDir, 'approved.json');
  const denialPath = path.join(resultDir, 'approved.json');
  writeJson(requestPath, request);

  const prepared = prepareFile(requestPath, intentPath, denialPath, {
    provider_actor: 'doctor',
    checked_out_sha: sourceSha,
  });
  assert.strictEqual(prepared.approved, true);
  assert.strictEqual(prepared.marker_path, markerPathFor(request));
  const intent = readJson(intentPath);
  assert.strictEqual(intent.guardian.approved, true);
  assert.strictEqual(intent.guardian.constraints.caller_supplied_path, false);
  assert.strictEqual(intent.guardian.constraints.shell, false);
  assert.ok(verifyHash(intent, 'intent_hash'));

  const executed = executeFile(requestPath, intentPath, prepared.marker_path);
  assert.strictEqual(executed.reused, false);
  const marker = readJson(prepared.marker_path);
  assert.ok(verifyHash(marker, 'marker_sha256'));

  const effectCommit = 'a'.repeat(40);
  const resultPath = path.join(resultDir, 'approved.json');
  const recorded = recordFile(requestPath, intentPath, prepared.marker_path, effectCommit, resultPath);
  assert.strictEqual(recorded.state, 'EXECUTED');
  assert.ok(verifyHash(readJson(resultPath), 'result_sha256'));

  const remoteMarkerPath = path.join(temp, 'remote-marker.json');
  fs.copyFileSync(prepared.marker_path, remoteMarkerPath);
  const verificationPath = path.join(verificationDir, 'approved.json');
  const verified = verifyExecutedFile(
    requestPath,
    intentPath,
    resultPath,
    remoteMarkerPath,
    effectCommit,
    verificationPath,
  );
  assert.strictEqual(verified.state, 'VERIFIED');
  assert.strictEqual(verified.decision, 'POSTCONDITION_VERIFIED');
  assert.ok(verifyHash(readJson(verificationPath), 'verification_hash'));

  const replayRequestPath = path.join(requestDir, 'replay.json');
  const replayIntentPath = path.join(intentDir, 'replay.json');
  const replayDenialPath = path.join(resultDir, 'replay.json');
  writeJson(replayRequestPath, request);
  const replayPrepared = prepareFile(replayRequestPath, replayIntentPath, replayDenialPath, {
    provider_actor: 'doctor',
    checked_out_sha: sourceSha,
  });
  const replayExecuted = executeFile(replayRequestPath, replayIntentPath, replayPrepared.marker_path);
  assert.strictEqual(replayExecuted.reused, true);

  const conflict = approvedRequest({
    request_id: 'effect-provider-doctor-conflict',
    payload: {
      marker: 'github-actions-connected-qualification',
      value: 'different-value',
    },
  });
  const conflictRequestPath = path.join(requestDir, 'conflict.json');
  const conflictIntentPath = path.join(intentDir, 'conflict.json');
  writeJson(conflictRequestPath, conflict);
  const conflictPrepared = prepareFile(
    conflictRequestPath,
    conflictIntentPath,
    path.join(resultDir, 'conflict.json'),
    {provider_actor: 'doctor', checked_out_sha: sourceSha},
  );
  assert.throws(
    () => executeFile(conflictRequestPath, conflictIntentPath, conflictPrepared.marker_path),
    /idempotency key reused with different immutable request content/,
  );

  const denied = approvedRequest({
    request_id: 'effect-provider-doctor-denied',
    capability: 'github.runtime.unapproved.put',
    idempotency_key: 'effect-provider-doctor-denied-key',
  });
  const deniedRequestPath = path.join(requestDir, 'denied.json');
  const deniedIntentPath = path.join(intentDir, 'denied.json');
  const deniedResultPath = path.join(resultDir, 'denied.json');
  const deniedVerificationPath = path.join(verificationDir, 'denied.json');
  writeJson(deniedRequestPath, denied);
  const deniedPrepared = prepareFile(deniedRequestPath, deniedIntentPath, deniedResultPath, {
    provider_actor: 'doctor',
    checked_out_sha: sourceSha,
  });
  assert.strictEqual(deniedPrepared.approved, false);
  assert.strictEqual(fs.existsSync(deniedIntentPath), false);
  assert.strictEqual(readJson(deniedResultPath).state, 'DENIED');
  const deniedVerified = verifyDeniedFile(deniedRequestPath, deniedResultPath, deniedVerificationPath);
  assert.strictEqual(deniedVerified.decision, 'DENIAL_VERIFIED');

  const stalePath = path.join(requestDir, 'stale.json');
  writeJson(stalePath, approvedRequest({
    request_id: 'effect-provider-doctor-stale',
    idempotency_key: 'effect-provider-doctor-stale-key',
    expires_at: '2000-01-01T00:00:00Z',
  }));
  assert.throws(
    () => prepareFile(stalePath, path.join(intentDir, 'stale.json'), path.join(resultDir, 'stale.json')),
    /request expired/,
  );

  const selfApprovedPath = path.join(requestDir, 'self-approved.json');
  writeJson(selfApprovedPath, {...approvedRequest({
    request_id: 'effect-provider-doctor-self-approved',
    idempotency_key: 'effect-provider-doctor-self-approved-key',
  }), approved: true});
  assert.throws(
    () => prepareFile(
      selfApprovedPath,
      path.join(intentDir, 'self-approved.json'),
      path.join(resultDir, 'self-approved.json'),
    ),
    /unexpected request field: approved/,
  );

  console.log(JSON.stringify({
    ok: true,
    tests: 9,
    guardian_allowlist: true,
    caller_supplied_path_absent: true,
    shell_authority_absent: true,
    execution_intent_hash: true,
    provider_marker_effect: true,
    independent_postcondition_verification: true,
    idempotent_replay: true,
    idempotency_conflict_rejected: true,
    guardian_denial_verified: true,
    stale_request_rejected: true,
    caller_self_approval_rejected: true,
  }, null, 2));
} finally {
  process.chdir(originalCwd);
  fs.rmSync(temp, {recursive: true, force: true});
}
