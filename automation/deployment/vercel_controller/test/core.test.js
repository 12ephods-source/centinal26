import assert from 'node:assert/strict';
import test from 'node:test';

import {
  canonicalJson,
  decryptSecret,
  encryptSecret,
  signRecord,
  stateBackendName,
  verifyRecord,
} from '../lib/core.js';


test('canonicalJson is deterministic across object key order', () => {
  const left = { b: 2, a: { y: 2, x: 1 } };
  const right = { a: { x: 1, y: 2 }, b: 2 };
  assert.equal(canonicalJson(left), canonicalJson(right));
});


test('record signatures are stable and tamper evident', () => {
  const secret = 's'.repeat(32);
  const record = { task_id: 'task-1', capability: 'diagnostic_status' };
  const signed = { ...record, signature: signRecord(record, secret) };
  assert.equal(verifyRecord(signed, secret), true);
  assert.equal(verifyRecord({ ...signed, capability: 'inventory_snapshot' }, secret), false);
});


test('device credential encryption round trips under controller key', () => {
  const previous = process.env.FROST_CONTROLLER_CREDENTIAL_KEY;
  process.env.FROST_CONTROLLER_CREDENTIAL_KEY = 'k'.repeat(48);
  try {
    const encrypted = encryptSecret('device-secret-value');
    assert.notEqual(encrypted.ciphertext, 'device-secret-value');
    assert.equal(decryptSecret(encrypted), 'device-secret-value');
  } finally {
    if (previous === undefined) delete process.env.FROST_CONTROLLER_CREDENTIAL_KEY;
    else process.env.FROST_CONTROLLER_CREDENTIAL_KEY = previous;
  }
});


test('Blob is selected as first-party state backend when configured', () => {
  const priorBackend = process.env.FROST_STATE_BACKEND;
  const priorBlob = process.env.BLOB_READ_WRITE_TOKEN;
  const priorRedisUrl = process.env.UPSTASH_REDIS_REST_URL;
  const priorRedisToken = process.env.UPSTASH_REDIS_REST_TOKEN;
  delete process.env.FROST_STATE_BACKEND;
  process.env.BLOB_READ_WRITE_TOKEN = 'test-token';
  delete process.env.UPSTASH_REDIS_REST_URL;
  delete process.env.UPSTASH_REDIS_REST_TOKEN;
  try {
    assert.equal(stateBackendName(), 'blob');
  } finally {
    if (priorBackend === undefined) delete process.env.FROST_STATE_BACKEND;
    else process.env.FROST_STATE_BACKEND = priorBackend;
    if (priorBlob === undefined) delete process.env.BLOB_READ_WRITE_TOKEN;
    else process.env.BLOB_READ_WRITE_TOKEN = priorBlob;
    if (priorRedisUrl === undefined) delete process.env.UPSTASH_REDIS_REST_URL;
    else process.env.UPSTASH_REDIS_REST_URL = priorRedisUrl;
    if (priorRedisToken === undefined) delete process.env.UPSTASH_REDIS_REST_TOKEN;
    else process.env.UPSTASH_REDIS_REST_TOKEN = priorRedisToken;
  }
});
