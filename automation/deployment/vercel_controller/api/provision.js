import { encryptSecret, getJson, setJson, sha256Hex } from '../lib/core.js';

export default async function handler(request, response) {
  if (request.method !== 'POST') {
    response.setHeader('Allow', 'POST');
    return response.status(405).json({ status: 'METHOD_NOT_ALLOWED' });
  }

  const {
    provisioning_token: token,
    device_id: deviceId,
    source_commit: sourceCommit,
    enrollment_digest: enrollmentDigest,
    credential,
  } = request.body || {};

  if (typeof token !== 'string' || token.length < 32) return response.status(400).json({ status: 'TOKEN_INVALID' });
  if (typeof deviceId !== 'string' || !deviceId) return response.status(400).json({ status: 'DEVICE_ID_REQUIRED' });
  if (typeof sourceCommit !== 'string' || !/^[0-9a-f]{40}$/i.test(sourceCommit)) return response.status(400).json({ status: 'SOURCE_COMMIT_INVALID' });
  if (typeof enrollmentDigest !== 'string' || !/^[0-9a-f]{64}$/i.test(enrollmentDigest)) return response.status(400).json({ status: 'ENROLLMENT_DIGEST_INVALID' });
  if (typeof credential !== 'string' || Buffer.byteLength(credential) < 32) return response.status(400).json({ status: 'CREDENTIAL_INVALID' });

  const tokenKey = `frost:provision:${sha256Hex(token)}`;
  const issued = await getJson(tokenKey);
  if (!issued || issued.status !== 'ISSUED') return response.status(401).json({ status: 'TOKEN_NOT_ISSUED' });
  if (Date.parse(issued.expires_at) <= Date.now()) return response.status(401).json({ status: 'TOKEN_EXPIRED' });
  if (issued.expected_source_commit !== sourceCommit.toLowerCase()) return response.status(409).json({ status: 'SOURCE_COMMIT_MISMATCH' });

  const existing = await getJson(`frost:device:${deviceId}`);
  const credentialFingerprint = sha256Hex(credential);
  if (existing && (
    existing.source_commit !== sourceCommit.toLowerCase()
    || existing.enrollment_digest !== enrollmentDigest.toLowerCase()
    || existing.credential_fingerprint !== credentialFingerprint
  )) {
    return response.status(409).json({ status: 'DEVICE_IDENTITY_CONFLICT' });
  }

  await setJson(`frost:secret:${deviceId}`, encryptSecret(credential));
  await setJson(`frost:device:${deviceId}`, {
    device_id: deviceId,
    source_commit: sourceCommit.toLowerCase(),
    enrollment_digest: enrollmentDigest.toLowerCase(),
    credential_fingerprint: credentialFingerprint,
    status: 'PENDING_COMMISSIONING',
    registered_at: existing?.registered_at || new Date().toISOString(),
    last_seen_at: null,
    last_evidence_hash: null,
  });
  issued.status = 'CONSUMED';
  issued.consumed_at = new Date().toISOString();
  issued.consumed_device_id = deviceId;
  await setJson(tokenKey, issued, 3600);

  return response.status(201).json({
    status: 'REGISTERED_PENDING_PHYSICAL_VERIFICATION',
    device_id: deviceId,
    credential_fingerprint: credentialFingerprint,
  });
}
