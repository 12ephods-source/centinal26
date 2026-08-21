import { getJson } from '../lib/core.js';

export default async function handler(request, response) {
  if (request.method !== 'GET') {
    response.setHeader('Allow', 'GET');
    return response.status(405).json({ status: 'METHOD_NOT_ALLOWED' });
  }

  const deviceId = typeof request.query.device_id === 'string' ? request.query.device_id : '';
  if (!deviceId) return response.status(400).json({ status: 'DEVICE_ID_REQUIRED' });

  const registration = await getJson(`frost:device:${deviceId}`);
  if (!registration || registration.status === 'REVOKED') {
    return response.status(404).json({ status: 'DEVICE_NOT_REGISTERED' });
  }

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
