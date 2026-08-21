import { randomHex, requireAdmin, setJson, sha256Hex } from '../../lib/core.js';

export default async function handler(request, response) {
  if (request.method !== 'POST') {
    response.setHeader('Allow', 'POST');
    return response.status(405).json({ status: 'METHOD_NOT_ALLOWED' });
  }
  if (!requireAdmin(request)) return response.status(401).json({ status: 'ADMIN_AUTH_REQUIRED' });

  const { expected_source_commit: sourceCommit, ttl_seconds: ttlSeconds = 900 } = request.body || {};
  if (typeof sourceCommit !== 'string' || !/^[0-9a-f]{40}$/i.test(sourceCommit)) {
    return response.status(400).json({ status: 'SOURCE_COMMIT_INVALID' });
  }
  if (!Number.isInteger(ttlSeconds) || ttlSeconds <= 0 || ttlSeconds > 3600) {
    return response.status(400).json({ status: 'TTL_INVALID' });
  }

  const token = randomHex(32);
  const tokenHash = sha256Hex(token);
  await setJson(`frost:provision:${tokenHash}`, {
    expected_source_commit: sourceCommit.toLowerCase(),
    created_at: new Date().toISOString(),
    expires_at: new Date(Date.now() + ttlSeconds * 1000).toISOString(),
    status: 'ISSUED',
  }, ttlSeconds);

  return response.status(201).json({
    status: 'ISSUED',
    token,
    expires_at: new Date(Date.now() + ttlSeconds * 1000).toISOString(),
  });
}
