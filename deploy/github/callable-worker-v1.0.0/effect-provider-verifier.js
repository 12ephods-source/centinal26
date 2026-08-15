'use strict';

const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const {spawnSync} = require('child_process');

const PROTOCOL = 'frost-effect/1.0';
const PROVIDER = 'github-actions';
const QUALIFICATION_CAPABILITY = 'github.runtime.qualification_marker.put';
const SHA40 = /^[0-9a-f]{40}$/;

function canonical(value) {
  if (value === null || typeof value !== 'object') return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`;
  return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonical(value[key])}`).join(',')}}`;
}

function sha256Buffer(value) {
  return crypto.createHash('sha256').update(value).digest('hex');
}

function sha256(value) {
  return sha256Buffer(Buffer.from(canonical(value), 'utf8'));
}

function hashBody(value, hashField) {
  const body = {...value};
  delete body[hashField];
  return sha256(body);
}

function verifyHash(value, hashField) {
  return value && typeof value[hashField] === 'string' && value[hashField] === hashBody(value, hashField);
}

function requestIdentity(request) {
  return sha256(request);
}

function providerIdempotencyKey(request) {
  return sha256Buffer(Buffer.from(`${PROVIDER}\0${request.capability}\0${request.idempotency_key}`, 'utf8'));
}

function markerPathFor(request) {
  return `runtime/effect-markers/${providerIdempotencyKey(request)}.json`;
}

function expectedMarker(request) {
  const body = {
    schema: 'frost-effect-marker/1.0',
    protocol: PROTOCOL,
    provider: PROVIDER,
    capability: request.capability,
    request_id: request.request_id,
    request_sha256: requestIdentity(request),
    provider_idempotency_key: providerIdempotencyKey(request),
    payload_sha256: sha256(request.payload),
    marker: request.payload.marker,
    value: request.payload.value,
  };
  return {...body, marker_sha256: sha256(body)};
}

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

function writeExclusiveJson(filePath, value) {
  fs.mkdirSync(path.dirname(filePath), {recursive: true});
  fs.writeFileSync(filePath, `${JSON.stringify(value, null, 2)}\n`, {flag: 'wx'});
}

function runGit(args) {
  const result = spawnSync('git', args, {
    cwd: process.cwd(),
    encoding: 'utf8',
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  if (result.error) throw result.error;
  if (result.status !== 0) {
    throw new Error(`git ${args.join(' ')} failed (${result.status}): ${(result.stderr || '').trim()}`);
  }
  return (result.stdout || '').trim();
}

function remoteAbsenceEvidence(request, remoteRef) {
  if (typeof remoteRef !== 'string' || !remoteRef.trim()) throw new Error('remote_ref is required');
  const remoteRefSha = runGit(['rev-parse', '--verify', `${remoteRef}^{commit}`]);
  if (!SHA40.test(remoteRefSha)) throw new Error('remote_ref did not resolve to a commit SHA');
  const markerPath = markerPathFor(request);
  const observed = runGit(['ls-tree', '-r', '--name-only', remoteRef, '--', markerPath]);
  const listed = observed.split('\n').filter(Boolean);
  return {
    remote_ref: remoteRef,
    remote_ref_sha: remoteRefSha,
    marker_path: markerPath,
    marker_absent: !listed.includes(markerPath),
  };
}

function remoteMarkerFromCommit(request, effectCommit) {
  if (!SHA40.test(effectCommit)) throw new Error('effect_commit must be a lowercase 40-character git SHA');
  runGit(['rev-parse', '--verify', `${effectCommit}^{commit}`]);
  const markerPath = markerPathFor(request);
  const encoded = runGit(['show', `${effectCommit}:${markerPath}`]);
  let marker;
  try {
    marker = JSON.parse(encoded);
  } catch (error) {
    throw new Error(`remote marker is not valid JSON: ${error.message}`);
  }
  return {marker, marker_path: markerPath};
}

function verificationBodyForDenied(request, result, absenceEvidence) {
  if (!verifyHash(result, 'result_sha256')) throw new Error('denial result hash verification failed');
  if (result.protocol !== PROTOCOL || result.provider !== PROVIDER || result.state !== 'DENIED') {
    throw new Error('denial result has invalid protocol/provider/state');
  }
  const requestSha256 = requestIdentity(request);
  if (result.request_sha256 !== requestSha256) throw new Error('denial request hash mismatch');
  if (!result.guardian || result.guardian.approved !== false) {
    throw new Error('denial result is not a Guardian denial');
  }
  if (result.provider_receipt !== undefined || result.marker_path !== undefined) {
    throw new Error('denied effect unexpectedly contains provider execution evidence');
  }
  const expectedPath = markerPathFor(request);
  if (!absenceEvidence || absenceEvidence.marker_path !== expectedPath) {
    throw new Error('denial absence evidence marker path mismatch');
  }
  if (!SHA40.test(absenceEvidence.remote_ref_sha || '')) {
    throw new Error('denial absence evidence lacks an immutable remote commit');
  }
  if (absenceEvidence.marker_absent !== true) {
    throw new Error('provider marker exists for denied effect');
  }
  const body = {
    schema: 'frost-effect-verification/1.0',
    protocol: PROTOCOL,
    state: 'VERIFIED',
    decision: 'DENIAL_VERIFIED',
    independent: true,
    verifier_id: 'github-actions-effect-independent-git/v2',
    request_id: request.request_id,
    request_sha256: requestSha256,
    result_sha256: result.result_sha256,
    provider: PROVIDER,
    derived_marker_path: expectedPath,
    remote_ref: absenceEvidence.remote_ref,
    remote_ref_sha: absenceEvidence.remote_ref_sha,
    postcondition: {
      provider_execution_absent: true,
      guardian_denial_present: true,
      derived_marker_absent_at_remote_ref: true,
    },
  };
  return {...body, verification_hash: sha256(body)};
}

function verificationBodyForExecuted(request, intent, result, remoteMarker, effectCommit) {
  if (!verifyHash(intent, 'intent_hash')) throw new Error('intent hash verification failed');
  if (!verifyHash(result, 'result_sha256')) throw new Error('result hash verification failed');
  if (!verifyHash(remoteMarker, 'marker_sha256')) throw new Error('remote marker hash verification failed');
  if (request.capability !== QUALIFICATION_CAPABILITY) throw new Error('request capability is not qualified');

  const requestSha256 = requestIdentity(request);
  const providerKey = providerIdempotencyKey(request);
  const expectedPath = markerPathFor(request);
  const expected = expectedMarker(request);

  if (intent.request_sha256 !== requestSha256 || result.request_sha256 !== requestSha256) {
    throw new Error('request hash binding mismatch');
  }
  if (!intent.guardian || intent.guardian.approved !== true) throw new Error('intent is not Guardian-authorized');
  if (intent.provider_idempotency_key !== providerKey) throw new Error('intent provider idempotency mismatch');
  if (intent.marker_path !== expectedPath) throw new Error('intent marker path mismatch');
  if (result.state !== 'EXECUTED') throw new Error('result is not EXECUTED');
  if (result.intent_hash !== intent.intent_hash) throw new Error('result intent hash mismatch');
  if (!result.provider_receipt || result.provider_receipt.effect_commit !== effectCommit) {
    throw new Error('provider receipt commit mismatch');
  }
  if (result.provider_receipt.provider !== PROVIDER || result.provider_receipt.branch !== 'callable-runtime') {
    throw new Error('provider receipt identity mismatch');
  }
  if (result.provider_idempotency_key !== providerKey || result.provider_receipt.marker_path !== expectedPath) {
    throw new Error('provider receipt idempotency/path mismatch');
  }
  if (result.marker_path !== expectedPath) throw new Error('result marker path mismatch');
  if (canonical(remoteMarker) !== canonical(expected)) throw new Error('remote marker content mismatch');
  if (result.marker_sha256 !== remoteMarker.marker_sha256 || result.provider_receipt.marker_sha256 !== remoteMarker.marker_sha256) {
    throw new Error('remote marker hash does not match provider receipt');
  }

  const body = {
    schema: 'frost-effect-verification/1.0',
    protocol: PROTOCOL,
    state: 'VERIFIED',
    decision: 'POSTCONDITION_VERIFIED',
    independent: true,
    verifier_id: 'github-actions-effect-independent-git/v2',
    request_id: request.request_id,
    request_sha256: requestSha256,
    intent_hash: intent.intent_hash,
    result_sha256: result.result_sha256,
    provider: PROVIDER,
    provider_idempotency_key: providerKey,
    effect_commit: effectCommit,
    marker_path: expectedPath,
    marker_sha256: remoteMarker.marker_sha256,
    postcondition: {
      remote_commit_observed: true,
      marker_exists_at_effect_commit: true,
      marker_hash_matches_receipt: true,
      request_binding_matches: true,
      provider_idempotency_rederived: true,
      marker_path_rederived: true,
      marker_content_rederived: true,
      payload_matches: true,
    },
  };
  return {...body, verification_hash: sha256(body)};
}

function writeOrVerify(filePath, expected) {
  if (fs.existsSync(filePath)) {
    const existing = readJson(filePath);
    if (!verifyHash(existing, 'verification_hash')) throw new Error('existing verification hash is invalid');
    if (canonical(existing) !== canonical(expected)) throw new Error('existing verification conflicts with expected content');
    return {reused: true, value: existing};
  }
  writeExclusiveJson(filePath, expected);
  return {reused: false, value: expected};
}

function verifyDeniedFile(requestPath, resultPath, remoteRef, verificationPath) {
  const request = readJson(requestPath);
  const result = readJson(resultPath);
  const absenceEvidence = remoteAbsenceEvidence(request, remoteRef);
  const verification = verificationBodyForDenied(request, result, absenceEvidence);
  const stored = writeOrVerify(verificationPath, verification);
  return {
    state: 'VERIFIED',
    decision: verification.decision,
    verification_path: verificationPath,
    verification_hash: verification.verification_hash,
    remote_ref_sha: absenceEvidence.remote_ref_sha,
    reused: stored.reused,
  };
}

function verifyExecutedFile(requestPath, intentPath, resultPath, effectCommit, verificationPath) {
  const request = readJson(requestPath);
  const intent = readJson(intentPath);
  const result = readJson(resultPath);
  const {marker: remoteMarker} = remoteMarkerFromCommit(request, effectCommit);
  const verification = verificationBodyForExecuted(request, intent, result, remoteMarker, effectCommit);
  const stored = writeOrVerify(verificationPath, verification);
  return {
    state: 'VERIFIED',
    decision: verification.decision,
    verification_path: verificationPath,
    verification_hash: verification.verification_hash,
    reused: stored.reused,
  };
}

function main(argv) {
  const [mode, ...args] = argv;
  let output;
  if (mode === 'denied' && args.length === 4) {
    output = verifyDeniedFile(args[0], args[1], args[2], args[3]);
  } else if (mode === 'executed' && args.length === 5) {
    output = verifyExecutedFile(args[0], args[1], args[2], args[3], args[4]);
  } else {
    throw new Error(
      'usage: effect-provider-verifier.js denied REQUEST RESULT REMOTE_REF VERIFICATION | executed REQUEST INTENT RESULT EFFECT_COMMIT VERIFICATION',
    );
  }
  process.stdout.write(`${JSON.stringify(output)}\n`);
}

if (require.main === module) main(process.argv.slice(2));
module.exports = {
  canonical,
  sha256,
  verifyHash,
  requestIdentity,
  providerIdempotencyKey,
  markerPathFor,
  expectedMarker,
  remoteAbsenceEvidence,
  remoteMarkerFromCommit,
  verificationBodyForDenied,
  verificationBodyForExecuted,
  verifyDeniedFile,
  verifyExecutedFile,
};
