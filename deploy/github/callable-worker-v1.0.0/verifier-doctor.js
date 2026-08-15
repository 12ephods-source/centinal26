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

const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'frost-verifier-doctor-'));
try {
  const requestPath = path.join(temp, 'request.json');
  const resultPath = path.join(temp, 'result.json');
  const verificationPath = path.join(temp, 'verification.json');
  const request = {
    protocol: 'frost-call/1.0',
    kind: 'invoke',
    idempotency_key: 'verifier-doctor',
    service_id: 'frost.callable.fabric',
    operation: 'frost.diagnostics.sha256',
    arguments: {text: 'independent-verifier'},
    context: {
      caller: 'verifier-doctor',
      role: 'operator',
      approved: false,
      request_id: 'verifier-doctor',
    },
  };
  fs.writeFileSync(requestPath, `${JSON.stringify(request, null, 2)}\n`);
  processFile(requestPath, resultPath, {
    run_id: 'verifier-doctor',
    sha: gitHead(),
    ref: 'refs/heads/verifier-doctor',
  });

  const verified = verifyPaths(requestPath, resultPath, verificationPath);
  assert.strictEqual(verified.verification_status, 'VERIFIED');
  assert.strictEqual(verified.source_attestation_status, 'VERIFIED');
  assert.ok(verified.checks.includes('envelope_hash:VERIFIED'));
  assert.ok(verified.checks.includes('provider_effect_policy:READ_ONLY_VERIFIED'));
  assert.ok(verified.checks.includes('semantic_receipt:VERIFIED'));
  assert.ok(verified.checks.includes('semantic_result_hash:VERIFIED'));
  assert.ok(verified.checks.includes('source_attestation:VERIFIED_HISTORICAL_BYTES'));

  const tamperedPath = path.join(temp, 'tampered-result.json');
  const tampered = JSON.parse(fs.readFileSync(resultPath, 'utf8'));
  tampered.response.result.sha256 = '0'.repeat(64);
  fs.writeFileSync(tamperedPath, `${JSON.stringify(tampered, null, 2)}\n`);
  assert.throws(
    () => verifyPaths(requestPath, tamperedPath, path.join(temp, 'tampered-verification.json')),
    /envelope hash mismatch/,
  );

  const legacyPath = path.join(temp, 'legacy-result.json');
  const legacyVerificationPath = path.join(temp, 'legacy-verification.json');
  const legacy = JSON.parse(fs.readFileSync(resultPath, 'utf8'));
  delete legacy.source_attestation;
  delete legacy.provider_effect_policy;
  delete legacy.idempotency_key;
  delete legacy.envelope_hash;
  legacy.envelope_hash = sha256(Buffer.from(canonical(legacy), 'utf8'));
  fs.writeFileSync(legacyPath, `${JSON.stringify(legacy, null, 2)}\n`);
  const limited = verifyPaths(requestPath, legacyPath, legacyVerificationPath);
  assert.strictEqual(limited.verification_status, 'VERIFIED_LEGACY_LIMITED');
  assert.strictEqual(limited.source_attestation_status, 'UNAVAILABLE_LEGACY');
  assert.ok(limited.checks.includes('idempotency_key:UNAVAILABLE_LEGACY'));
  assert.ok(limited.checks.includes('source_attestation:UNAVAILABLE_LEGACY'));
  assert.ok(limited.checks.includes('provider_effect_policy:UNAVAILABLE_LEGACY'));

  console.log(JSON.stringify({
    ok: true,
    tests: 3,
    valid_attested_result: true,
    tamper_rejection: true,
    legacy_limited_verification: true,
  }, null, 2));
} finally {
  fs.rmSync(temp, {recursive: true, force: true});
}
