'use strict';

const assert = require('assert');
const fs = require('fs');
const os = require('os');
const path = require('path');
const {
  processRequest,
  processFile,
  requestIdentity,
  verifyEnvelope,
} = require('./worker');
const {
  canonical,
  sha256,
  verifyReceipt,
} = require('../../vercel/callable-fabric-v1.1.0/lib/fabric');

const WORKER_PATH = path.join(__dirname, 'worker.js');
const FABRIC_PATH = require.resolve('../../vercel/callable-fabric-v1.1.0/lib/fabric');
const WORKFLOW_PATH = path.resolve(
  __dirname,
  '../../../.github/workflows/callable-fabric-worker.yml',
);

function run(request) {
  const result = processRequest(request, {
    run_id: 'doctor',
    sha: 'doctor-sha',
    ref: 'refs/heads/doctor',
  });
  assert.strictEqual(verifyEnvelope(result), true);
  return result;
}

function assertSourceAttestation(
  result,
  expectedSha = 'doctor-sha',
  expectedRef = 'refs/heads/doctor',
) {
  const att = result.source_attestation;
  assert.strictEqual(att.schema, 'frost-source-attestation/1.0');
  assert.strictEqual(att.semantic_core.canonical_git_sha, result.canonical_git_sha);
  assert.strictEqual(
    att.semantic_core.source_identity_sha256,
    result.source_identity_sha256,
  );
  assert.strictEqual(
    att.semantic_core.deployment_adapter_sha256,
    result.deployment_adapter_sha256,
  );

  const semanticCoreFileSha256 = sha256(fs.readFileSync(FABRIC_PATH));
  const workerSourceSha256 = sha256(fs.readFileSync(WORKER_PATH));
  const workflowSourceSha256 = sha256(fs.readFileSync(WORKFLOW_PATH));
  assert.strictEqual(att.semantic_core.file_sha256, semanticCoreFileSha256);
  assert.strictEqual(att.provider_runtime.worker_source_sha256, workerSourceSha256);
  assert.strictEqual(att.provider_runtime.workflow_source_sha256, workflowSourceSha256);
  assert.strictEqual(att.provider_runtime.checked_out_sha, expectedSha);
  assert.strictEqual(att.provider_runtime.checked_out_ref, expectedRef);

  const expectedIdentity = sha256(Buffer.from(canonical({
    provider: 'github-actions',
    semantic_core_file_sha256: semanticCoreFileSha256,
    worker_source_sha256: workerSourceSha256,
    workflow_source_sha256: workflowSourceSha256,
  }), 'utf8'));
  assert.strictEqual(att.provider_code_identity_sha256, expectedIdentity);
}

const invokeRequest = {
  protocol: 'frost-call/1.0',
  kind: 'invoke',
  idempotency_key: 'doctor-sha256',
  service_id: 'frost.callable.fabric',
  operation: 'frost.diagnostics.sha256',
  arguments: {text: 'abc'},
  context: {caller: 'github-worker-doctor', role: 'operator', approved: false, request_id: 'doctor-invoke'},
};
const invoke = run(invokeRequest);
assert.strictEqual(invoke.response.ok, true);
assert.strictEqual(invoke.response.result.sha256, 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad');
assert.strictEqual(verifyReceipt(invoke.response.receipt), true);
assert.strictEqual(invoke.idempotency_key, 'doctor-sha256');
assertSourceAttestation(invoke);

const fallbackIdentity = requestIdentity({
  protocol: 'frost-call/1.0',
  kind: 'mcp',
  message: {jsonrpc: '2.0', id: 0, method: 'initialize', params: {}},
});
assert.strictEqual(fallbackIdentity.idempotency_key, fallbackIdentity.request_sha256);

const mcpInit = run({
  protocol: 'frost-call/1.0',
  kind: 'mcp',
  message: {jsonrpc: '2.0', id: 1, method: 'initialize', params: {}},
});
assert.strictEqual(mcpInit.response.result.protocolVersion, '2025-06-18');

const mcpList = run({
  protocol: 'frost-call/1.0',
  kind: 'mcp',
  message: {jsonrpc: '2.0', id: 2, method: 'tools/list', params: {}},
});
assert.strictEqual(mcpList.response.result.tools.length, 6);

const mcpCall = run({
  protocol: 'frost-call/1.0',
  kind: 'mcp',
  message: {
    jsonrpc: '2.0',
    id: 3,
    method: 'tools/call',
    params: {name: 'frost_diagnostics_echo', arguments: {text: 'connected'}},
  },
});
assert.strictEqual(mcpCall.response.result.structuredContent.result.text, 'connected');
assert.strictEqual(verifyReceipt(mcpCall.response.result.structuredContent.receipt), true);

const denied = run({
  protocol: 'frost-call/1.0',
  kind: 'invoke',
  service_id: 'frost.callable.fabric',
  operation: 'frost.diagnostics.dangerous_demo_policy_test',
  arguments: {target: 'negative-control'},
  context: {caller: 'github-worker-doctor', role: 'operator', approved: false, request_id: 'doctor-deny'},
});
assert.strictEqual(denied.response.ok, false);
assert.strictEqual(denied.response.error.type, 'DENIED');
assert.strictEqual(verifyReceipt(denied.response.receipt), true);
assertSourceAttestation(denied);

const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'frost-callable-doctor-'));
try {
  const requests = path.join(temp, 'requests');
  const results = path.join(temp, 'results');
  fs.mkdirSync(requests);
  fs.mkdirSync(results);

  const firstPath = path.join(requests, 'first.json');
  const duplicatePath = path.join(requests, 'duplicate.json');
  const conflictPath = path.join(requests, 'conflict.json');
  const firstResult = path.join(results, 'first.json');
  const duplicateResult = path.join(results, 'duplicate.json');
  const conflictResult = path.join(results, 'conflict.json');

  fs.writeFileSync(firstPath, JSON.stringify(invokeRequest));
  fs.writeFileSync(duplicatePath, JSON.stringify(invokeRequest));
  fs.writeFileSync(
    conflictPath,
    JSON.stringify({...invokeRequest, arguments: {text: 'different'}}),
  );

  const first = processFile(firstPath, firstResult, {
    run_id: 'doctor-file-1',
    sha: 'doctor-file-sha-1',
    ref: 'refs/heads/doctor',
  });
  assert.strictEqual(first.reused, false);

  const duplicate = processFile(
    duplicatePath,
    duplicateResult,
    {run_id: 'doctor-file-2', sha: 'doctor-file-sha-2', ref: 'refs/heads/doctor'},
  );
  assert.strictEqual(duplicate.reused, true);
  assert.strictEqual(fs.readFileSync(duplicateResult, 'utf8'), fs.readFileSync(firstResult, 'utf8'));

  const conflict = processFile(
    conflictPath,
    conflictResult,
    {run_id: 'doctor-file-3', sha: 'doctor-file-sha-3', ref: 'refs/heads/doctor'},
  );
  assert.strictEqual(conflict.reused, false);
  const conflictEnvelope = JSON.parse(fs.readFileSync(conflictResult, 'utf8'));
  assert.strictEqual(conflictEnvelope.ok, false);
  assert.strictEqual(conflictEnvelope.error.type, 'IdempotencyConflict');
  assert.strictEqual(verifyEnvelope(conflictEnvelope), true);
  assertSourceAttestation(
    conflictEnvelope,
    'doctor-file-sha-3',
    'refs/heads/doctor',
  );
} finally {
  fs.rmSync(temp, {recursive: true, force: true});
}

console.log(JSON.stringify({
  ok: true,
  tests: 9,
  provider: 'github-actions',
  semantic_tools_only: true,
  unrestricted_remote_shell: false,
  durable_result_idempotency: true,
  source_attestation: true,
}, null, 2));
