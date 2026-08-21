import { ALLOWED_CAPABILITIES, getJson, randomHex, requireAdmin, setJson, signRecord } from '../../lib/core.js';

export default async function handler(request, response) {
  if (request.method !== 'POST') {
    response.setHeader('Allow', 'POST');
    return response.status(405).json({ status: 'METHOD_NOT_ALLOWED' });
  }
  if (!requireAdmin(request)) return response.status(401).json({ status: 'ADMIN_AUTH_REQUIRED' });

  const { device_id: deviceId, capability, parameters = {}, ttl_seconds: ttlSeconds = 300 } = request.body || {};
  if (typeof deviceId !== 'string' || !deviceId) return response.status(400).json({ status: 'DEVICE_ID_REQUIRED' });
  if (!ALLOWED_CAPABILITIES.has(capability)) return response.status(400).json({ status: 'CAPABILITY_NOT_ALLOWED' });
  if (!Number.isInteger(ttlSeconds) || ttlSeconds <= 0 || ttlSeconds > 3600) return response.status(400).json({ status: 'TTL_INVALID' });

  const registration = await getJson(`frost:device:${deviceId}`);
  const secret = await getJson(`frost:secret:${deviceId}`);
  if (!registration || !secret?.value || registration.status === 'REVOKED') {
    return response.status(404).json({ status: 'DEVICE_NOT_REGISTERED' });
  }

  const job = {
    task_id: randomHex(16),
    target_device_id: deviceId,
    capability,
    parameters: parameters && typeof parameters === 'object' ? parameters : {},
    authorization_scope: { device_id: deviceId, capability },
    expires_at: new Date(Date.now() + ttlSeconds * 1000).toISOString(),
    nonce: randomHex(16),
    expected_source_commit: registration.source_commit,
  };
  job.signature = signRecord(job, secret.value);
  await setJson(`frost:job:${deviceId}`, job, ttlSeconds);
  return response.status(201).json({ status: 'QUEUED', job });
}
