'use strict';

const assert = require('assert');
const fs = require('fs');
const os = require('os');
const path = require('path');
const {spawnSync} = require('child_process');
const {processFile} = require('./worker');
const {canonical, sha256, verifyPaths} = require('./verifier');

function gitHead() {
  const result = spawnSync('git', ['rev-parse', 'HEAD'], {encoding: 'utf8'});
  if (result.status !== 0) throw new Error(result.stderr || 'git rev-parse failed');
  return result.stdout.trim();
}

function request(key, expiresAt) {
  return {
    protocol: 'frost-call/1.0',
    kind: 'invoke',
    idempotency_key: key,
    service_id: 'frost.callable.fabric',
    operation: 'frost.diagnostics.sha256',
    arguments: {text: key},
    context: {
      caller: 'expiry-doctor',
      role: 'operator',
      approved: false,
      request_id: key,
      expires_at: expiresAt,
    },
  };
}

function provider(runId, now) {
  return {
    run_id: runId,
    sha: gitHead(),
    ref: 'refs/heads/expiry-doctor',
    now_ms: Date.parse(now),
  };
}

const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'frost-expiry-doctor-'));
try {
  const requests = path.join(temp, 'requests');
  const results = path.join(temp, 'results');
  const verifications = path.join(temp, 'verifications');
  fs.mkdirSync(requests);
  fs.mkdirSync(results);
  fs.mkdirSync(verifications);

  const fresh = request('expiry-fresh', '2026-08-15T03:00:00Z');
  const freshPath = path.join(requests, 'fresh.json');
  const freshResult = path.join(results, 'fresh.json');
  const freshVerification = path.join(verifications, 'fresh.json');
  fs.writeFileSync(freshPath, JSON.stringify(fresh));
  processFile(freshPath, freshResult, provider('expiry-fresh-run', '2026-08-15T02:59:00Z'));
  const freshVerified = verifyPaths(freshPath, freshResult, freshVerification);
  assert.ok(freshVerified.checks.includes('request_expiry:FRESH_VERIFIED'));

  const lateDuplicatePath = path.join(requests, 'fresh-late-duplicate.json');
  const lateDuplicateResult = path.join(results, 'fresh-late-duplicate.json');
  const lateDuplicateVerification = path.join(verifications, 'fresh-late-duplicate.json');
  fs.writeFileSync(lateDuplicatePath, JSON.stringify(fresh));
  const lateDuplicate = processFile(
    lateDuplicatePath,
    lateDuplicateResult,
    provider('expiry-late-retry', '2026-08-15T03:01:00Z'),
  );
  assert.strictEqual(lateDuplicate.reused, true);
  assert.strictEqual(
    fs.readFileSync(lateDuplicateResult, 'utf8'),
    fs.readFileSync(freshResult, 'utf8'),
  );
  const lateVerified = verifyPaths(
    lateDuplicatePath,
    lateDuplicateResult,
    lateDuplicateVerification,
  );
  assert.ok(lateVerified.checks.includes('request_expiry:FRESH_VERIFIED'));

  const stale = request('expiry-stale', '2026-08-15T03:00:00Z');
  const stalePath = path.join(requests, 'stale.json');
  const staleResult = path.join(results, 'stale.json');
  const staleVerification = path.join(verifications, 'stale.json');
  fs.writeFileSync(stalePath, JSON.stringify(stale));
  processFile(stalePath, staleResult, provider('expiry-stale-run', '2026-08-15T03:01:00Z'));
  const staleEnvelope = JSON.parse(fs.readFileSync(staleResult, 'utf8'));
  assert.strictEqual(staleEnvelope.error.type, 'StaleRequest');
  const staleVerified = verifyPaths(stalePath, staleResult, staleVerification);
  assert.ok(staleVerified.checks.includes('request_expiry:EXPIRED_VERIFIED'));

  const forgedPath = path.join(results, 'stale-forged.json');
  const forged = JSON.parse(fs.readFileSync(staleResult, 'utf8'));
  forged.request_expiry.observed_at = '2026-08-15T02:59:00.000Z';
  delete forged.envelope_hash;
  forged.envelope_hash = sha256(Buffer.from(canonical(forged), 'utf8'));
  fs.writeFileSync(forgedPath, `${JSON.stringify(forged, null, 2)}\n`);
  assert.throws(
    () => verifyPaths(
      stalePath,
      forgedPath,
      path.join(verifications, 'stale-forged.json'),
    ),
    /stale request observed before expiry/,
  );

  const invalid = request('expiry-invalid', 'tomorrow');
  const invalidPath = path.join(requests, 'invalid.json');
  const invalidResult = path.join(results, 'invalid.json');
  const invalidVerification = path.join(verifications, 'invalid.json');
  fs.writeFileSync(invalidPath, JSON.stringify(invalid));
  processFile(invalidPath, invalidResult, provider('expiry-invalid-run', '2026-08-15T02:59:00Z'));
  const invalidEnvelope = JSON.parse(fs.readFileSync(invalidResult, 'utf8'));
  assert.strictEqual(invalidEnvelope.error.type, 'InvalidExpiry');
  const invalidVerified = verifyPaths(invalidPath, invalidResult, invalidVerification);
  assert.ok(invalidVerified.checks.includes('request_expiry:INVALID_REJECTED'));

  console.log(JSON.stringify({
    ok: true,
    tests: 5,
    fresh_execution: true,
    late_retry_reconciliation: true,
    stale_rejection: true,
    forged_stale_rejection: true,
    invalid_expiry_rejection: true,
  }, null, 2));
} finally {
  fs.rmSync(temp, {recursive: true, force: true});
}
