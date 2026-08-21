import crypto from 'node:crypto';

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

function redisConfig() {
  const url = process.env.UPSTASH_REDIS_REST_URL;
  const token = process.env.UPSTASH_REDIS_REST_TOKEN;
  if (!url || !token) throw new Error('REDIS_NOT_CONFIGURED');
  return { url: url.replace(/\/$/, ''), token };
}

export async function redis(command, ...args) {
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

export async function getJson(key) {
  const raw = await redis('GET', key);
  return raw == null ? null : JSON.parse(raw);
}

export async function setJson(key, value, ttlSeconds = null) {
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
