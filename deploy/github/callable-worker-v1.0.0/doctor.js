'use strict';

const assert = require('assert');
const {processRequest, verifyEnvelope} = require('./worker');
const {verifyReceipt} = require('../../vercel/callable-fabric-v1.1.0/lib/fabric');

function run(request) {
  const result = processRequest(request, {run_id: 'doctor', sha: 'doctor'});
  assert.strictEqual(verifyEnvelope(result), true);
  return result;
}

const invoke = run({
  protocol: 'frost-call/1.0',
  kind: 'invoke',
  service_id: 'frost.callable.fabric',
  operation: 'frost.diagnostics.sha256',
  arguments: {text: 'abc'},
  context: {caller: 'github-worker-doctor', role: 'operator', approved: false, request_id: 'doctor-invoke'},
});
assert.strictEqual(invoke.response.ok, true);
assert.strictEqual(invoke.response.result.sha256, 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad');
assert.strictEqual(verifyReceipt(invoke.response.receipt), true);

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

console.log(JSON.stringify({ok: true, tests: 5, provider: 'github-actions', semantic_tools_only: true, unrestricted_remote_shell: false}, null, 2));
