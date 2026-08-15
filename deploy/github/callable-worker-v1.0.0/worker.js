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

function envelopeHash(value) {
  const body = {...value};
  delete body.envelope_hash;
  return sha256(Buffer.from(canonical(body), 'utf8'));
}

function verifyEnvelope(value) {
  if (!value || typeof value !== 'object' || typeof value.envelope_hash !== 'string') return false;
  return envelopeHash(value) === value.envelope_hash;
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
  if (!request || typeof request !== 'object' || Array.isArray(request)) throw new Error('request must be a JSON object');
  if (request.protocol !== PROTOCOL) throw new Error(`protocol must be ${PROTOCOL}`);

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
    request_sha256: sha256(Buffer.from(canonical(request), 'utf8')),
    response,
  };
  return {...body, envelope_hash: envelopeHash(body)};
}

function errorEnvelope(raw, request, error, provider = {}) {
  const body = {
    ok: false,
    protocol: PROTOCOL,
    provider: 'github-actions',
    provider_run_id: provider.run_id || null,
    provider_sha: provider.sha || null,
    canonical_git_sha: CANONICAL_GIT_SHA,
    source_identity_sha256: SOURCE_IDENTITY_SHA256,
    deployment_adapter_sha256: ADAPTER_SPEC_SHA256,
    request_sha256: request ? sha256(Buffer.from(canonical(request), 'utf8')) : sha256(Buffer.from(raw, 'utf8')),
    error: {type: error.name || 'Error', message: String(error.message || error)},
  };
  return {...body, envelope_hash: envelopeHash(body)};
}

function main(argv) {
  if (argv.length !== 2) throw new Error('usage: node worker.js REQUEST_JSON RESULT_JSON');
  const [inputPath, outputPath] = argv;
  const stat = fs.statSync(inputPath);
  if (stat.size > MAX_REQUEST_BYTES) throw new Error(`request exceeds ${MAX_REQUEST_BYTES} bytes`);

  const raw = fs.readFileSync(inputPath, 'utf8');
  const provider = {run_id: process.env.GITHUB_RUN_ID || null, sha: process.env.GITHUB_SHA || null};
  let request = null;
  let output;
  try {
    request = JSON.parse(raw);
    output = processRequest(request, provider);
  } catch (error) {
    output = errorEnvelope(raw, request, error, provider);
  }

  fs.mkdirSync(path.dirname(outputPath), {recursive: true});
  fs.writeFileSync(outputPath, `${JSON.stringify(output, null, 2)}\n`, {flag: 'wx'});
  process.stdout.write(`${JSON.stringify({ok: output.ok, output: outputPath, envelope_hash: output.envelope_hash})}\n`);
}

if (require.main === module) main(process.argv.slice(2));
module.exports = {PROTOCOL, MAX_REQUEST_BYTES, processRequest, handleMcp, envelopeHash, verifyEnvelope};
