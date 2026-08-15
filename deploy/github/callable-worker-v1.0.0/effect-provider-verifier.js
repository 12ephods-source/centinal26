'use strict';

const fs = require('fs');
const path = require('path');
const {
  PROTOCOL,
  PROVIDER,
  QUALIFICATION_CAPABILITY,
  canonical,
  sha256,
  verifyHash,
  requestIdentity,
  readJson,
} = require('./effect-provider');

function writeExclusiveJson(filePath, value) {
  fs.mkdirSync(path.dirname(filePath), {recursive: true});
  fs.writeFileSync(filePath, `${JSON.stringify(value, null, 2)}\n`, {flag: 'wx'});
}

function verificationBodyForDenied(request, result) {
  if (!verifyHash(result, 'result_sha256')) throw new Error('denial result hash verification failed');
  if (result.protocol !== PROTOCOL || result.provider !== PROVIDER || result.state !== 'DENIED') {
    throw new Error('denial result has invalid protocol/provider/state');
  }
  if (result.request_sha256 !== requestIdentity(request)) throw new Error('denial request hash mismatch');
  if (!result.guardian || result.guardian.approved !== false) {
    throw new Error('denial result is not a Guardian denial');
  }
  if (result.provider_receipt !== undefined || result.marker_path !== undefined) {
    throw new Error('denied effect unexpectedly contains provider execution evidence');
  }
  const body = {
    schema: 'frost-effect-verification/1.0',
    protocol: PROTOCOL,
    state: 'VERIFIED',
    decision: 'DENIAL_VERIFIED',
    independent: true,
    verifier_id: 'github-actions-effect-readback/v1',
    request_id: request.request_id,
    request_sha256: requestIdentity(request),
    result_sha256: result.result_sha256,
    postcondition: {
      provider_execution_absent: true,
      guardian_denial_present: true,
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
  if (intent.request_sha256 !== requestSha256 || result.request_sha256 !== requestSha256) {
    throw new Error('request hash binding mismatch');
  }
  if (!intent.guardian || intent.guardian.approved !== true) throw new Error('intent is not Guardian-authorized');
  if (result.state !== 'EXECUTED') throw new Error('result is not EXECUTED');
  if (result.intent_hash !== intent.intent_hash) throw new Error('result intent hash mismatch');
  if (!result.provider_receipt || result.provider_receipt.effect_commit !== effectCommit) {
    throw new Error('provider receipt commit mismatch');
  }
  if (result.marker_path !== intent.marker_path || result.provider_receipt.marker_path !== intent.marker_path) {
    throw new Error('marker path binding mismatch');
  }
  if (result.marker_sha256 !== remoteMarker.marker_sha256 || result.provider_receipt.marker_sha256 !== remoteMarker.marker_sha256) {
    throw new Error('remote marker hash does not match provider receipt');
  }
  if (remoteMarker.request_sha256 !== requestSha256) throw new Error('remote marker request hash mismatch');
  if (remoteMarker.provider_idempotency_key !== intent.provider_idempotency_key) {
    throw new Error('remote marker provider idempotency mismatch');
  }
  if (remoteMarker.marker !== request.payload.marker || remoteMarker.value !== request.payload.value) {
    throw new Error('remote marker postcondition mismatch');
  }

  const body = {
    schema: 'frost-effect-verification/1.0',
    protocol: PROTOCOL,
    state: 'VERIFIED',
    decision: 'POSTCONDITION_VERIFIED',
    independent: true,
    verifier_id: 'github-actions-effect-readback/v1',
    request_id: request.request_id,
    request_sha256: requestSha256,
    intent_hash: intent.intent_hash,
    result_sha256: result.result_sha256,
    provider: PROVIDER,
    provider_idempotency_key: intent.provider_idempotency_key,
    effect_commit: effectCommit,
    marker_path: intent.marker_path,
    marker_sha256: remoteMarker.marker_sha256,
    postcondition: {
      remote_commit_observed: true,
      marker_exists_at_effect_commit: true,
      marker_hash_matches_receipt: true,
      request_binding_matches: true,
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

function verifyDeniedFile(requestPath, resultPath, verificationPath) {
  const request = readJson(requestPath);
  const result = readJson(resultPath);
  const verification = verificationBodyForDenied(request, result);
  const stored = writeOrVerify(verificationPath, verification);
  return {state: 'VERIFIED', decision: verification.decision, verification_path: verificationPath, verification_hash: verification.verification_hash, reused: stored.reused};
}

function verifyExecutedFile(requestPath, intentPath, resultPath, remoteMarkerPath, effectCommit, verificationPath) {
  const request = readJson(requestPath);
  const intent = readJson(intentPath);
  const result = readJson(resultPath);
  const remoteMarker = readJson(remoteMarkerPath);
  const verification = verificationBodyForExecuted(request, intent, result, remoteMarker, effectCommit);
  const stored = writeOrVerify(verificationPath, verification);
  return {state: 'VERIFIED', decision: verification.decision, verification_path: verificationPath, verification_hash: verification.verification_hash, reused: stored.reused};
}

function main(argv) {
  const [mode, ...args] = argv;
  let output;
  if (mode === 'denied' && args.length === 3) {
    output = verifyDeniedFile(args[0], args[1], args[2]);
  } else if (mode === 'executed' && args.length === 6) {
    output = verifyExecutedFile(args[0], args[1], args[2], args[3], args[4], args[5]);
  } else {
    throw new Error(
      'usage: effect-provider-verifier.js denied REQUEST RESULT VERIFICATION | executed REQUEST INTENT RESULT REMOTE_MARKER EFFECT_COMMIT VERIFICATION',
    );
  }
  process.stdout.write(`${JSON.stringify(output)}\n`);
}

if (require.main === module) main(process.argv.slice(2));
module.exports = {
  verificationBodyForDenied,
  verificationBodyForExecuted,
  verifyDeniedFile,
  verifyExecutedFile,
};
