'use strict';

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const PROTOCOL = 'frost-effect/1.0';
const PROVIDER = 'github-actions';
const QUALIFICATION_CAPABILITY = 'github.runtime.qualification_marker.put';
const GUARDIAN_POLICY = 'github-actions-qualification-marker/v1';
const MAX_REQUEST_BYTES = 64 * 1024;
const MAX_IDEMPOTENCY_KEY_BYTES = 256;
const MAX_MARKER_BYTES = 256;
const MAX_VALUE_BYTES = 1024;
const RFC3339_INSTANT = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?(?:Z|[+-]\d{2}:\d{2})$/;
const SHA40 = /^[0-9a-f]{40}$/;
const WORKFLOW_PATH = path.resolve(__dirname, '../../../.github/workflows/frost-effect-provider.yml');

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

function fileSha256(filePath) {
  return sha256Buffer(fs.readFileSync(filePath));
}

function hashBody(value, hashField) {
  const body = {...value};
  delete body[hashField];
  return sha256(body);
}

function verifyHash(value, hashField) {
  return value && typeof value[hashField] === 'string' && value[hashField] === hashBody(value, hashField);
}

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

function writeExclusiveJson(filePath, value) {
  fs.mkdirSync(path.dirname(filePath), {recursive: true});
  fs.writeFileSync(filePath, `${JSON.stringify(value, null, 2)}\n`, {flag: 'wx'});
}

function bytes(value) {
  return Buffer.byteLength(value, 'utf8');
}

function assertPlainObject(value, name) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error(`${name} must be a JSON object`);
  }
}

function requestIdentity(request) {
  assertPlainObject(request, 'request');
  return sha256(request);
}

function validateRequest(request, nowMs = Date.now()) {
  assertPlainObject(request, 'request');
  const allowed = new Set([
    'protocol', 'request_id', 'capability', 'idempotency_key', 'actor', 'payload', 'expires_at',
  ]);
  for (const key of Object.keys(request)) {
    if (!allowed.has(key)) throw new Error(`unexpected request field: ${key}`);
  }
  if (request.protocol !== PROTOCOL) throw new Error(`protocol must be ${PROTOCOL}`);
  for (const key of ['request_id', 'capability', 'idempotency_key', 'actor']) {
    if (typeof request[key] !== 'string' || !request[key].trim()) {
      throw new Error(`${key} must be a non-empty string`);
    }
  }
  if (bytes(request.idempotency_key) > MAX_IDEMPOTENCY_KEY_BYTES) {
    throw new Error(`idempotency_key exceeds ${MAX_IDEMPOTENCY_KEY_BYTES} bytes`);
  }
  assertPlainObject(request.payload, 'payload');
  const payloadKeys = Object.keys(request.payload).sort();
  if (canonical(payloadKeys) !== canonical(['marker', 'value'])) {
    throw new Error('payload must contain exactly marker and value');
  }
  if (typeof request.payload.marker !== 'string' || !request.payload.marker.trim()) {
    throw new Error('payload.marker must be a non-empty string');
  }
  if (typeof request.payload.value !== 'string' || !request.payload.value.trim()) {
    throw new Error('payload.value must be a non-empty string');
  }
  if (bytes(request.payload.marker) > MAX_MARKER_BYTES) {
    throw new Error(`payload.marker exceeds ${MAX_MARKER_BYTES} bytes`);
  }
  if (bytes(request.payload.value) > MAX_VALUE_BYTES) {
    throw new Error(`payload.value exceeds ${MAX_VALUE_BYTES} bytes`);
  }
  if (typeof request.expires_at !== 'string' || !RFC3339_INSTANT.test(request.expires_at)) {
    throw new Error('expires_at must be an RFC3339 timestamp with timezone');
  }
  const expiresAtMs = Date.parse(request.expires_at);
  if (!Number.isFinite(expiresAtMs)) throw new Error('expires_at is invalid');
  if (Number(nowMs) >= expiresAtMs) {
    const error = new Error(`request expired at ${request.expires_at}`);
    error.name = 'StaleEffectRequest';
    throw error;
  }
  return true;
}

function providerIdempotencyKey(request) {
  return sha256Buffer(Buffer.from(`${PROVIDER}\0${request.capability}\0${request.idempotency_key}`, 'utf8'));
}

function markerPathFor(request) {
  const key = providerIdempotencyKey(request);
  return `runtime/effect-markers/${key}.json`;
}

function sourceAttestation(checkedOutSha = null) {
  return {
    schema: 'frost-source-attestation/1.0',
    provider: PROVIDER,
    provider_source_sha256: fileSha256(__filename),
    workflow_source_sha256: fs.existsSync(WORKFLOW_PATH) ? fileSha256(WORKFLOW_PATH) : null,
    checked_out_sha: checkedOutSha || null,
  };
}

function guardianDecision(request, providerActor = null) {
  const approved = request.capability === QUALIFICATION_CAPABILITY;
  return {
    schema: 'frost-guardian-decision/1.0',
    policy: GUARDIAN_POLICY,
    approved,
    capability: request.capability,
    provider_actor: providerActor || null,
    reason: approved ? 'bounded_qualification_capability' : 'capability_not_allowlisted',
    constraints: approved ? {
      provider: PROVIDER,
      effect: 'create_immutable_qualification_marker',
      namespace: 'runtime/effect-markers/',
      caller_supplied_path: false,
      shell: false,
      network_target_selection: false,
    } : {},
  };
}

function intendedBody(request, options = {}) {
  const requestSha256 = requestIdentity(request);
  const providerKey = providerIdempotencyKey(request);
  const body = {
    schema: 'frost-effect-intent/1.0',
    protocol: PROTOCOL,
    state: 'EXECUTION_INTENT_PERSISTED',
    request_id: request.request_id,
    request_sha256: requestSha256,
    capability: request.capability,
    actor: request.actor,
    guardian: guardianDecision(request, options.provider_actor),
    provider: PROVIDER,
    provider_idempotency_key: providerKey,
    marker_path: markerPathFor(request),
    payload_sha256: sha256(request.payload),
    source_attestation: sourceAttestation(options.checked_out_sha),
  };
  return {...body, intent_hash: sha256(body)};
}

function denialBody(request, options = {}) {
  const requestSha256 = requestIdentity(request);
  const body = {
    schema: 'frost-effect-result/1.0',
    protocol: PROTOCOL,
    state: 'DENIED',
    request_id: request.request_id,
    request_sha256: requestSha256,
    capability: request.capability,
    guardian: guardianDecision(request, options.provider_actor),
    provider: PROVIDER,
    source_attestation: sourceAttestation(options.checked_out_sha),
  };
  return {...body, result_sha256: sha256(body)};
}

function ensureExistingExact(filePath, expected, hashField) {
  const existing = readJson(filePath);
  if (!verifyHash(existing, hashField)) throw new Error(`${path.basename(filePath)} has invalid ${hashField}`);
  if (canonical(existing) !== canonical(expected)) {
    const error = new Error(`${path.basename(filePath)} conflicts with immutable expected content`);
    error.name = 'ImmutableArtifactConflict';
    throw error;
  }
  return existing;
}

function prepareFile(requestPath, intentPath, denialResultPath, options = {}) {
  const stat = fs.statSync(requestPath);
  if (stat.size > MAX_REQUEST_BYTES) throw new Error(`request exceeds ${MAX_REQUEST_BYTES} bytes`);
  const request = readJson(requestPath);
  validateRequest(request, options.now_ms === undefined ? Date.now() : Number(options.now_ms));
  const guardian = guardianDecision(request, options.provider_actor);
  if (!guardian.approved) {
    const denial = denialBody(request, options);
    let reused = false;
    if (fs.existsSync(denialResultPath)) {
      ensureExistingExact(denialResultPath, denial, 'result_sha256');
      reused = true;
    } else {
      writeExclusiveJson(denialResultPath, denial);
    }
    return {approved: false, state: 'DENIED', result_path: denialResultPath, reused};
  }

  const intent = intendedBody(request, options);
  let reused = false;
  if (fs.existsSync(intentPath)) {
    ensureExistingExact(intentPath, intent, 'intent_hash');
    reused = true;
  } else {
    writeExclusiveJson(intentPath, intent);
  }
  return {
    approved: true,
    state: intent.state,
    intent_path: intentPath,
    intent_hash: intent.intent_hash,
    marker_path: intent.marker_path,
    provider_idempotency_key: intent.provider_idempotency_key,
    reused,
  };
}

function expectedMarker(request, intent) {
  if (!verifyHash(intent, 'intent_hash')) throw new Error('intent_hash verification failed');
  if (intent.request_sha256 !== requestIdentity(request)) throw new Error('intent request hash mismatch');
  if (!intent.guardian || intent.guardian.approved !== true) throw new Error('intent is not Guardian-authorized');
  if (intent.capability !== QUALIFICATION_CAPABILITY) throw new Error('intent capability is not provider-qualified');
  if (intent.provider_idempotency_key !== providerIdempotencyKey(request)) {
    throw new Error('provider idempotency key mismatch');
  }
  if (intent.marker_path !== markerPathFor(request)) throw new Error('marker path mismatch');
  const body = {
    schema: 'frost-effect-marker/1.0',
    protocol: PROTOCOL,
    provider: PROVIDER,
    capability: request.capability,
    request_id: request.request_id,
    request_sha256: requestIdentity(request),
    provider_idempotency_key: intent.provider_idempotency_key,
    payload_sha256: sha256(request.payload),
    marker: request.payload.marker,
    value: request.payload.value,
  };
  return {...body, marker_sha256: sha256(body)};
}

function executeFile(requestPath, intentPath, markerPath) {
  const request = readJson(requestPath);
  const intent = readJson(intentPath);
  const expected = expectedMarker(request, intent);
  if (markerPath !== intent.marker_path) throw new Error('requested marker output path differs from intent');
  let reused = false;
  if (fs.existsSync(markerPath)) {
    const existing = readJson(markerPath);
    if (!verifyHash(existing, 'marker_sha256')) throw new Error('existing marker hash is invalid');
    if (existing.provider_idempotency_key !== intent.provider_idempotency_key) {
      const error = new Error('provider idempotency key resolved to a different marker');
      error.name = 'IdempotencyConflict';
      throw error;
    }
    if (existing.request_sha256 !== expected.request_sha256 || canonical(existing) !== canonical(expected)) {
      const error = new Error('idempotency key reused with different immutable request content');
      error.name = 'IdempotencyConflict';
      throw error;
    }
    reused = true;
  } else {
    writeExclusiveJson(markerPath, expected);
  }
  return {
    state: 'EXECUTED_LOCAL_PENDING_PROVIDER_COMMIT',
    marker_path: markerPath,
    marker_sha256: expected.marker_sha256,
    reused,
  };
}

function resultBody(request, intent, marker, effectCommit) {
  if (!SHA40.test(effectCommit)) throw new Error('effect_commit must be a lowercase 40-character git SHA');
  const expected = expectedMarker(request, intent);
  if (!verifyHash(marker, 'marker_sha256') || canonical(marker) !== canonical(expected)) {
    throw new Error('marker does not match authorized execution intent');
  }
  const body = {
    schema: 'frost-effect-result/1.0',
    protocol: PROTOCOL,
    state: 'EXECUTED',
    request_id: request.request_id,
    request_sha256: requestIdentity(request),
    capability: request.capability,
    intent_hash: intent.intent_hash,
    provider: PROVIDER,
    provider_idempotency_key: intent.provider_idempotency_key,
    marker_path: intent.marker_path,
    marker_sha256: marker.marker_sha256,
    provider_receipt: {
      schema: 'frost-provider-receipt/1.0',
      provider: PROVIDER,
      branch: 'callable-runtime',
      effect_commit: effectCommit,
      marker_path: intent.marker_path,
      marker_sha256: marker.marker_sha256,
    },
    source_attestation: intent.source_attestation,
  };
  return {...body, result_sha256: sha256(body)};
}

function recordFile(requestPath, intentPath, markerPath, effectCommit, resultPath) {
  const request = readJson(requestPath);
  const intent = readJson(intentPath);
  const marker = readJson(markerPath);
  const result = resultBody(request, intent, marker, effectCommit);
  let reused = false;
  if (fs.existsSync(resultPath)) {
    ensureExistingExact(resultPath, result, 'result_sha256');
    reused = true;
  } else {
    writeExclusiveJson(resultPath, result);
  }
  return {state: result.state, result_path: resultPath, result_sha256: result.result_sha256, reused};
}

function main(argv) {
  const [command, ...args] = argv;
  const options = {
    provider_actor: process.env.GITHUB_ACTOR || process.env.FROST_EFFECT_PROVIDER_ACTOR || null,
    checked_out_sha: process.env.FROST_EFFECT_CHECKED_OUT_SHA || null,
    now_ms: process.env.FROST_EFFECT_NOW_MS,
  };
  let output;
  if (command === 'prepare' && args.length === 3) {
    output = prepareFile(args[0], args[1], args[2], options);
  } else if (command === 'execute' && args.length === 3) {
    output = executeFile(args[0], args[1], args[2]);
  } else if (command === 'record' && args.length === 5) {
    output = recordFile(args[0], args[1], args[2], args[3], args[4]);
  } else {
    throw new Error(
      'usage: effect-provider.js prepare REQUEST INTENT DENIAL_RESULT | execute REQUEST INTENT MARKER | record REQUEST INTENT MARKER EFFECT_COMMIT RESULT',
    );
  }
  process.stdout.write(`${JSON.stringify(output)}\n`);
}

if (require.main === module) main(process.argv.slice(2));
module.exports = {
  PROTOCOL,
  PROVIDER,
  QUALIFICATION_CAPABILITY,
  GUARDIAN_POLICY,
  canonical,
  sha256,
  hashBody,
  verifyHash,
  requestIdentity,
  validateRequest,
  providerIdempotencyKey,
  markerPathFor,
  sourceAttestation,
  guardianDecision,
  prepareFile,
  executeFile,
  resultBody,
  recordFile,
  readJson,
};
