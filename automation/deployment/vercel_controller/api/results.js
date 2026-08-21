import { ALLOWED_CAPABILITIES, decryptSecret, getJson, setJson, verifyRecord } from '../lib/core.js';

export default async function handler(request, response) {
  if (request.method !== 'POST') {
    response.setHeader('Allow', 'POST');
    return response.status(405).json({ status: 'METHOD_NOT_ALLOWED' });
  }
  const result = request.body;
  if (!result || typeof result !== 'object') return response.status(400).json({ status: 'RESULT_REQUIRED' });

  const deviceId = result.device_id;
  const registration = typeof deviceId === 'string' ? await getJson(`frost:device:${deviceId}`) : null;
  if (!registration || registration.status === 'REVOKED') return response.status(404).json({ status: 'DEVICE_NOT_REGISTERED' });
  const secretRecord = await getJson(`frost:secret:${deviceId}`);
  if (!secretRecord) return response.status(401).json({ status: 'DEVICE_CREDENTIAL_MISSING' });
  const secret = decryptSecret(secretRecord);
  if (!verifyRecord(result, secret)) return response.status(401).json({ status: 'SIGNATURE_INVALID' });
  if (result.source_commit !== registration.source_commit) return response.status(409).json({ status: 'SOURCE_COMMIT_MISMATCH' });
  if (!ALLOWED_CAPABILITIES.has(result.capability)) return response.status(400).json({ status: 'CAPABILITY_NOT_ALLOWED' });

  const outstanding = await getJson(`frost:job:${deviceId}`);
  if (!outstanding || outstanding.task_id !== result.task_id || outstanding.capability !== result.capability) {
    const existing = await getJson(`frost:result:${result.task_id}`);
    if (existing) return response.status(200).json({ status: 'ALREADY_ACKNOWLEDGED', task_id: result.task_id });
    return response.status(409).json({ status: 'TASK_NOT_OUTSTANDING' });
  }

  await setJson(`frost:result:${result.task_id}`, result, 86400);
  await setJson(`frost:job:${deviceId}`, null, 1);
  registration.last_seen_at = new Date().toISOString();
  registration.last_evidence_hash = result.previous_evidence_hash || registration.last_evidence_hash || null;
  await setJson(`frost:device:${deviceId}`, registration);
  return response.status(200).json({ status: 'ACKNOWLEDGED', task_id: result.task_id });
}
