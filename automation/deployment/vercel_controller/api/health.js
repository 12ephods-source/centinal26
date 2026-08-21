export default async function handler(request, response) {
  if (request.method !== 'GET') {
    response.setHeader('Allow', 'GET');
    return response.status(405).json({ status: 'METHOD_NOT_ALLOWED' });
  }

  const redisUrlConfigured = Boolean(process.env.UPSTASH_REDIS_REST_URL);
  const redisTokenConfigured = Boolean(process.env.UPSTASH_REDIS_REST_TOKEN);
  const controllerConfigured = Boolean(process.env.FROST_CONTROLLER_ADMIN_SECRET);
  const credentialKeyConfigured = Boolean(
    process.env.FROST_CONTROLLER_CREDENTIAL_KEY
      && process.env.FROST_CONTROLLER_CREDENTIAL_KEY.length >= 32,
  );
  const ready = redisUrlConfigured && redisTokenConfigured && controllerConfigured && credentialKeyConfigured;

  return response.status(ready ? 200 : 503).json({
    service: 'frost-outbound-controller',
    status: ready ? 'READY' : 'NOT_CONFIGURED',
    redis_url_configured: redisUrlConfigured,
    redis_token_configured: redisTokenConfigured,
    controller_secret_configured: controllerConfigured,
    credential_key_configured: credentialKeyConfigured,
  });
}
