import { decryptSecret, getJson, setJson, verifyRecord } from '../lib/core.js';

const REQUEST_FRESHNESS_MS = 120_000;

export default async function handler(request, response) {
  if (request.method !== 'GET') {
    response.setHeader('Allow', 'GET');
    return response.status(405).json({ status: 'METHOD_NOT_ALLOWED' });
  }

  const deviceId = typeof request.query.device_id === 'string' ? request.query.device_id : '';
  if (!deviceId) return response.status(400).json({ status: 'DEVICE_ID_REQUIRED' });
  if (request.headers['x-frost-device'] !== deviceId) {
    return response.status(401).json({ status: 'DEVICE_HEADER_MISMATCH' });
  }

  const registration = await getJson(`frost:device:${deviceId}`);
  if (!registration || registration.status === 'REVOKED') {
    return response.status(404).json({ status: 'DEVICE_NOT_REGISTERED' });
  }

  const encryptedSecret = await getJson(`frost:secret:${deviceId}`);
  if (!encryptedSecret) return response.status(401).json({ status: 'DEVICE_SECRET_MISSING' });
  const secret = decryptSecret(encryptedSecret);

  const timestamp = request.headers['x-frost-request-timestamp'];
  const nonce = request.headers['x-frost-request-nonce'];
  const signature = request.headers['x-frost-request-signature'];
  if (typeof timestamp !== 'string' || typeof nonce !== 'string' || typeof signature !== 'string') {
    return response.status(401).json({ status: 'REQUEST_AUTH_REQUIRED' });
  }
  const timestampMs = Date.parse(timestamp);
  if (!Number.isFinite(timestampMs) || Math.abs(Date.now() - timestampMs) > REQUEST_FRESHNESS_MS) {
    return response.status(401).json({ status: 'REQUEST_TIMESTAMP_INVALID' });
  }
  if (!/^[0-9a-f]{32}$/i.test(nonce)) {
    return response.status(401).json({ status: 'REQUEST_NONCE_INVALID' });
  }

  const authRecord = {
    device_id: deviceId,
    method: 'GET',
    timestamp,
    nonce,
    signature,
  };
  if (!verifyRecord(authRecord, secret)) {
    return response.status(401).json({ status: 'REQUEST_SIGNATURE_INVALID' });
  }

  const nonceKey = `frost:request-nonce:${deviceId}:${nonce}`;
  if (await getJson(nonceKey)) return response.status(409).json({ status: 'REQUEST_REPLAY' });
  await setJson(nonceKey, { seen_at: new Date().toISOString() }, 180);

  const job = await getJson(`frost:job:${deviceId}`);
  if (!job) return response.status(200).json({ job: null });

  const expires = Date.parse(job.expires_at);
  if (!Number.isFinite(expires) || expires <= Date.now()) {
    return response.status(200).json({ job: null, status: 'EXPIRED_JOB_SUPPRESSED' });
  }
  if (job.target_device_id !== deviceId || job.expected_source_commit !== registration.source_commit) {
    return response.status(409).json({ status: 'JOB_BINDING_INVALID' });
  }

  return response.status(200).json({ job });
}
