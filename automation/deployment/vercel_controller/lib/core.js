import crypto from 'node:crypto';
import { del as deleteBlob, get as getBlob, put as putBlob } from '@vercel/blob';

export const ALLOWED_CAPABILITIES = new Set(['diagnostic_status', 'inventory_snapshot']);

export function canonicalJson(value) {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(',')}]`;
  if (value && typeof value === 'object') {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`).join(',')}}`;
  }
  return JSON.stringify(value);
}

export function signRecord(record, secret) {
  const unsigned = Object.fromEntries(Object.entries(record).filter(([key]) => key !== 'signature'));
  return crypto.createHmac('sha256', secret).update(canonicalJson(unsigned)).digest('hex');
}

export function verifyRecord(record, secret) {
  const supplied = typeof record?.signature === 'string' ? record.signature : '';
  const expected = signRecord(record, secret);
  if (supplied.length !== expected.length) return false;
  return crypto.timingSafeEqual(Buffer.from(supplied), Buffer.from(expected));
}

export function requireAdmin(request) {
  const configured = process.env.FROST_CONTROLLER_ADMIN_SECRET;
  const supplied = request.headers['x-frost-admin-secret'];
  if (!configured || typeof supplied !== 'string') return false;
  const a = Buffer.from(configured);
  const b = Buffer.from(supplied);
  return a.length === b.length && crypto.timingSafeEqual(a, b);
}

function encryptionKey() {
  const secret = process.env.FROST_CONTROLLER_CREDENTIAL_KEY;
  if (!secret || secret.length < 32) throw new Error('CREDENTIAL_KEY_NOT_CONFIGURED');
  return crypto.createHash('sha256').update(secret).digest();
}

export function encryptSecret(secret) {
  const iv = crypto.randomBytes(12);
  const cipher = crypto.createCipheriv('aes-256-gcm', encryptionKey(), iv);
  const ciphertext = Buffer.concat([cipher.update(secret, 'utf8'), cipher.final()]);
  return {
    iv: iv.toString('base64url'),
    tag: cipher.getAuthTag().toString('base64url'),
    ciphertext: ciphertext.toString('base64url'),
  };
}

export function decryptSecret(record) {
  if (!record?.iv || !record?.tag || !record?.ciphertext) throw new Error('SECRET_RECORD_INVALID');
  const decipher = crypto.createDecipheriv(
    'aes-256-gcm',
    encryptionKey(),
    Buffer.from(record.iv, 'base64url'),
  );
  decipher.setAuthTag(Buffer.from(record.tag, 'base64url'));
  const plaintext = Buffer.concat([
    decipher.update(Buffer.from(record.ciphertext, 'base64url')),
    decipher.final(),
  ]);
  return plaintext.toString('utf8');
}

function redisConfigured() {
  return Boolean(process.env.UPSTASH_REDIS_REST_URL && process.env.UPSTASH_REDIS_REST_TOKEN);
}

function blobConfigured() {
  return Boolean(process.env.BLOB_READ_WRITE_TOKEN);
}

export function stateBackendName() {
  const requested = process.env.FROST_STATE_BACKEND?.trim().toLowerCase();
  if (requested) {
    if (!['blob', 'redis'].includes(requested)) throw new Error('STATE_BACKEND_INVALID');
    if (requested === 'blob' && !blobConfigured()) throw new Error('BLOB_NOT_CONFIGURED');
    if (requested === 'redis' && !redisConfigured()) throw new Error('REDIS_NOT_CONFIGURED');
    return requested;
  }
  if (blobConfigured()) return 'blob';
  if (redisConfigured()) return 'redis';
  throw new Error('STATE_BACKEND_NOT_CONFIGURED');
}

function redisConfig() {
  const url = process.env.UPSTASH_REDIS_REST_URL;
  const token = process.env.UPSTASH_REDIS_REST_TOKEN;
  if (!url || !token) throw new Error('REDIS_NOT_CONFIGURED');
  return { url: url.replace(/\/$/, ''), token };
}

async function redis(command, ...args) {
  const { url, token } = redisConfig();
  const response = await fetch(url, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify([command, ...args]),
    cache: 'no-store',
  });
  if (!response.ok) throw new Error(`REDIS_HTTP_${response.status}`);
  const payload = await response.json();
  if (payload.error) throw new Error(`REDIS_${payload.error}`);
  return payload.result;
}

function blobPath(key) {
  return `frost-state/${Buffer.from(key, 'utf8').toString('base64url')}.json`;
}

async function getBlobJson(key) {
  const result = await getBlob(blobPath(key), { access: 'private', useCache: false });
  if (!result || result.statusCode !== 200) return null;
  const text = await new Response(result.stream).text();
  const envelope = JSON.parse(text);
  if (!envelope || typeof envelope !== 'object' || !Object.hasOwn(envelope, 'value')) {
    throw new Error('BLOB_STATE_INVALID');
  }
  if (envelope.expires_at && Date.parse(envelope.expires_at) <= Date.now()) {
    await deleteBlob(blobPath(key));
    return null;
  }
  return envelope.value;
}

async function setBlobJson(key, value, ttlSeconds = null) {
  const pathname = blobPath(key);
  if (value === null) {
    await deleteBlob(pathname);
    return null;
  }
  const envelope = {
    value,
    expires_at: ttlSeconds == null ? null : new Date(Date.now() + ttlSeconds * 1000).toISOString(),
  };
  return putBlob(pathname, JSON.stringify(envelope), {
    access: 'private',
    addRandomSuffix: false,
    allowOverwrite: true,
    contentType: 'application/json',
    cacheControlMaxAge: 0,
  });
}

export async function getJson(key) {
  if (stateBackendName() === 'blob') return getBlobJson(key);
  const raw = await redis('GET', key);
  return raw == null ? null : JSON.parse(raw);
}

export async function setJson(key, value, ttlSeconds = null) {
  if (stateBackendName() === 'blob') return setBlobJson(key, value, ttlSeconds);
  if (value === null) return redis('DEL', key);
  const text = JSON.stringify(value);
  if (ttlSeconds == null) return redis('SET', key, text);
  return redis('SET', key, text, 'EX', String(ttlSeconds));
}

export function randomHex(bytes = 16) {
  return crypto.randomBytes(bytes).toString('hex');
}

export function sha256Hex(value) {
  return crypto.createHash('sha256').update(value).digest('hex');
}
