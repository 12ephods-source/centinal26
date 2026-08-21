export default async function handler(request, response) {
  if (request.method !== 'GET') {
    response.setHeader('Allow', 'GET');
    return response.status(405).json({ status: 'METHOD_NOT_ALLOWED' });
  }

  const blobConfigured = Boolean(process.env.BLOB_READ_WRITE_TOKEN);
  const controllerConfigured = Boolean(process.env.FROST_CONTROLLER_ADMIN_SECRET);
  const ready = blobConfigured && controllerConfigured;

  return response.status(ready ? 200 : 503).json({
    service: 'frost-outbound-controller',
    status: ready ? 'READY' : 'NOT_CONFIGURED',
    blob_configured: blobConfigured,
    controller_secret_configured: controllerConfigured,
  });
}
