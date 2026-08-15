'use strict';

const fs = require('fs');
const path = require('path');
const {
  SERVICE_ID,
  VERSION,
  CANONICAL_GIT_SHA,
  SOURCE_IDENTITY_SHA256,
  ADAPTER_SPEC_SHA256,
  MCP_PROTOCOL_VERSION,
  canonical,
  sha256,
  invoke,
  mcpTools,
  mcpCall,
} = require('../../vercel/callable-fabric-v1.1.0/lib/fabric');

const PROTOCOL = 'frost-call/1.0';
const MAX_REQUEST_BYTES = 64 * 1024;
const MAX_IDEMPOTENCY_KEY_BYTES = 256;
const FABRIC_SOURCE_PATH = require.resolve('../../vercel/callable-fabric-v1.1.0/lib/fabric');
const WORKFLOW_SOURCE_PATH = path.resolve(
  __dirname,
  '../../../.github/workflows/callable-fabric-worker.yml',
);

function envelopeHash(value) {
  const body = {...value};
  delete body.envelope_hash;
  return sha256(Buffer.from(canonical(body), 'utf8'));
}

function verifyEnvelope(value) {
  if (!value || typeof value !== 'object' || typeof value.envelope_hash !== 'string') return false;
  return envelopeHash(value) === value.envelope_hash;
}

function fileSha256(filePath) {
  return sha256(fs.readFileSync(filePath));
}

function sourceAttestation(provider = {}) {
  const semanticCoreFileSha256 = fileSha256(FABRIC_SOURCE_PATH);
  const workerSourceSha256 = fileSha256(__filename);
  const workflowSourceSha256 = fileSha256(WORKFLOW_SOURCE_PATH);
  const providerCodeIdentity = {
    provider: 'github-actions',
    semantic_core_file_sha256: semanticCoreFileSha256,
    worker_source_sha256: workerSourceSha256,
    workflow_source_sha256: workflowSourceSha256,
  };
  return {
    schema: 'frost-source-attestation/1.0',
    semantic_core: {
      canonical_git_sha: CANONICAL_GIT_SHA,
      source_identity_sha256: SOURCE_IDENTITY_SHA256,
      deployment_adapter_sha256: ADAPTER_SPEC_SHA256,
      file_sha256: semanticCoreFileSha256,
    },
    provider_runtime: {
      provider: 'github-actions',
      worker_source_sha256: workerSourceSha256,
      workflow_source_sha256: workflowSourceSha256,
      checked_out_sha: provider.sha || null,
      checked_out_ref: provider.ref || null,
    },
    provider_code_identity_sha256: sha256(
      Buffer.from(canonical(providerCodeIdentity), 'utf8'),
    ),
  };
}

function requestIdentity(request) {
  if (!request || typeof request !== 'object' || Array.isArray(request)) {
    throw new Error('request must be a JSON object');
  }
  const request_sha256 = sha256(Buffer.from(canonical(request), 'utf8'));
  const candidate = request.idempotency_key ?? request.context?.idempotency_key ?? request_sha256;
  if (typeof candidate !== 'string' || !candidate.trim()) {
    throw new Error('idempotency_key must be a non-empty string');
  }
  const idempotency_key = candidate.trim();
  if (Buffer.byteLength(idempotency_key, 'utf8') > MAX_IDEMPOTENCY_KEY_BYTES) {
    throw new Error(`idempotency_key exceeds ${MAX_IDEMPOTENCY_KEY_BYTES} bytes`);
  }
  return {request_sha256, idempotency_key};
}

function handleMcp(message = {}) {
  const id = message.id ?? null;
  if (message.method === 'initialize') {
    return {
      jsonrpc: '2.0',
      id,
      result: {
        protocolVersion: MCP_PROTOCOL_VERSION,
        capabilities: {tools: {listChanged: false}},
        serverInfo: {name: 'frost-callable-fabric', version: VERSION},
      },
    };
  }
  if (message.method === 'tools/list') {
    return {jsonrpc: '2.0', id, result: {tools: mcpTools()}};
  }
  if (message.method === 'tools/call') {
    const params = message.params || {};
    const result = mcpCall(params.name, params.arguments || {}, params._meta || {});
    if (!result) return {jsonrpc: '2.0', id, error: {code: -32602, message: 'unknown tool'}};
    return {
      jsonrpc: '2.0',
      id,
      result: {
        content: [{type: 'text', text: JSON.stringify(result)}],
        isError: !result.ok,
        structuredContent: result,
      },
    };
  }
  return {jsonrpc: '2.0', id, error: {code: -32601, message: `method not found: ${message.method}`}};
}

function processRequest(request, provider = {}) {
  if (!request || typeof request !== 'object' || Array.isArray(request)) {
    throw new Error('request must be a JSON object');
  }
  if (request.protocol !== PROTOCOL) throw new Error(`protocol must be ${PROTOCOL}`);

  const identity = requestIdentity(request);
  const kind = request.kind || 'invoke';
  let response;
  if (kind === 'invoke') {
    if (typeof request.operation !== 'string' || !request.operation) throw new Error('operation is required');
    response = invoke(
      request.service_id || SERVICE_ID,
      request.operation,
      request.arguments || {},
      request.context || {},
    );
  } else if (kind === 'mcp') {
    response = handleMcp(request.message || {});
  } else {
    throw new Error(`unsupported request kind: ${kind}`);
  }

  const body = {
    ok: true,
    protocol: PROTOCOL,
    provider: 'github-actions',
    provider_run_id: provider.run_id || null,
    provider_sha: provider.sha || null,
    canonical_git_sha: CANONICAL_GIT_SHA,
    source_identity_sha256: SOURCE_IDENTITY_SHA256,
    deployment_adapter_sha256: ADAPTER_SPEC_SHA256,
    source_attestation: sourceAttestation(provider),
    request_sha256: identity.request_sha256,
    idempotency_key: identity.idempotency_key,
    response,
  };
  return {...body, envelope_hash: envelopeHash(body)};
}

function errorEnvelope(raw, request, error, provider = {}, extra = {}) {
  let identity = null;
  try {
    if (request) identity = requestIdentity(request);
  } catch (_) {
    identity = null;
  }
  const body = {
    ok: false,
    protocol: PROTOCOL,
    provider: 'github-actions',
    provider_run_id: provider.run_id || null,
    provider_sha: provider.sha || null,
    canonical_git_sha: CANONICAL_GIT_SHA,
    source_identity_sha256: SOURCE_IDENTITY_SHA256,
    deployment_adapter_sha256: ADAPTER_SPEC_SHA256,
    source_attestation: sourceAttestation(provider),
    request_sha256: identity?.request_sha256 || sha256(Buffer.from(raw, 'utf8')),
    idempotency_key: identity?.idempotency_key || null,
    error: {type: error.name || 'Error', message: String(error.message || error)},
    ...extra,
  };
  return {...body, envelope_hash: envelopeHash(body)};
}

function priorResult(resultsDir, identity, outputPath) {
  if (!fs.existsSync(resultsDir)) return null;
  for (const name of fs.readdirSync(resultsDir).filter((x) => x.endsWith('.json')).sort()) {
    const candidatePath = path.join(resultsDir, name);
    if (path.resolve(candidatePath) === path.resolve(outputPath)) continue;
    let value;
    try {
      value = JSON.parse(fs.readFileSync(candidatePath, 'utf8'));
    } catch (_) {
      continue;
    }
    if (!verifyEnvelope(value)) continue;
    if (value.protocol !== PROTOCOL || value.provider !== 'github-actions') continue;
    if (value.idempotency_key !== identity.idempotency_key) continue;
    return {path: candidatePath, value};
  }
  return null;
}

function processFile(inputPath, outputPath, provider = {}) {
  const stat = fs.statSync(inputPath);
  if (stat.size > MAX_REQUEST_BYTES) throw new Error(`request exceeds ${MAX_REQUEST_BYTES} bytes`);

  const raw = fs.readFileSync(inputPath, 'utf8');
  let request = null;
  let output;
  let reused = false;
  let reconciledFrom = null;

  try {
    request = JSON.parse(raw);
    const identity = requestIdentity(request);
    const prior = priorResult(path.dirname(outputPath), identity, outputPath);
    if (prior && prior.value.request_sha256 === identity.request_sha256) {
      fs.mkdirSync(path.dirname(outputPath), {recursive: true});
      fs.copyFileSync(prior.path, outputPath, fs.constants.COPYFILE_EXCL);
      output = prior.value;
      reused = true;
      reconciledFrom = path.basename(prior.path);
    } else if (prior) {
      const conflict = new Error('idempotency_key reused with different request content');
      conflict.name = 'IdempotencyConflict';
      output = errorEnvelope(raw, request, conflict, provider, {
        existing_request_sha256: prior.value.request_sha256,
        existing_result_file: path.basename(prior.path),
      });
    } else {
      output = processRequest(request, provider);
    }
  } catch (error) {
    output = errorEnvelope(raw, request, error, provider);
  }

  fs.mkdirSync(path.dirname(outputPath), {recursive: true});
  if (!reused) {
    fs.writeFileSync(outputPath, `${JSON.stringify(output, null, 2)}\n`, {flag: 'wx'});
  }
  return {
    ok: output.ok,
    output: outputPath,
    envelope_hash: output.envelope_hash,
    reused,
    reconciled_from: reconciledFrom,
  };
}

function main(argv) {
  if (argv.length !== 2) throw new Error('usage: node worker.js REQUEST_JSON RESULT_JSON');
  const [inputPath, outputPath] = argv;
  const result = processFile(inputPath, outputPath, {
    run_id: process.env.GITHUB_RUN_ID || null,
    sha: process.env.GITHUB_SHA || null,
    ref: process.env.GITHUB_REF || null,
  });
  process.stdout.write(`${JSON.stringify(result)}\n`);
}

if (require.main === module) main(process.argv.slice(2));
module.exports = {
  PROTOCOL,
  MAX_REQUEST_BYTES,
  MAX_IDEMPOTENCY_KEY_BYTES,
  processRequest,
  processFile,
  requestIdentity,
  sourceAttestation,
  handleMcp,
  envelopeHash,
  verifyEnvelope,
};
