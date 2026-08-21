export default async function handler(request, response) {
  if (request.method !== 'GET') {
    response.setHeader('Allow', 'GET');
    return response.status(405).json({ status: 'METHOD_NOT_ALLOWED' });
  }

  const blobConfigured = Boolean(process.env.BLOB_READ_WRITE_TOKEN);
  const redisConfigured = Boolean(
    process.env.UPSTASH_REDIS_REST_URL && process.env.UPSTASH_REDIS_REST_TOKEN,
  );
  const requestedBackend = process.env.FROST_STATE_BACKEND?.trim().toLowerCase() || null;
  const stateConfigured = requestedBackend === 'blob'
    ? blobConfigured
    : requestedBackend === 'redis'
      ? redisConfigured
      : blobConfigured || redisConfigured;
  const controllerConfigured = Boolean(process.env.FROST_CONTROLLER_ADMIN_SECRET);
  const credentialKeyConfigured = Boolean(
    process.env.FROST_CONTROLLER_CREDENTIAL_KEY
      && process.env.FROST_CONTROLLER_CREDENTIAL_KEY.length >= 32,
  );
  const ready = stateConfigured && controllerConfigured && credentialKeyConfigured;

  return response.status(ready ? 200 : 503).json({
    service: 'frost-outbound-controller',
    status: ready ? 'READY' : 'NOT_CONFIGURED',
    state_backend_requested: requestedBackend,
    blob_configured: blobConfigured,
    redis_configured: redisConfigured,
    controller_secret_configured: controllerConfigured,
    credential_key_configured: credentialKeyConfigured,
  });
}
