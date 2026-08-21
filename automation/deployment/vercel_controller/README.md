# Frost outbound controller — Vercel target

This directory is a self-contained Vercel Functions deployment target for the outbound Android/Termux worker.

Required environment variables:

- `UPSTASH_REDIS_REST_URL`
- `UPSTASH_REDIS_REST_TOKEN`
- `FROST_CONTROLLER_ADMIN_SECRET` — high-entropy admin API secret
- `FROST_CONTROLLER_CREDENTIAL_KEY` — at least 32 characters; derives AES-256-GCM key for per-device credential encryption at rest

Deploy with this directory as the Vercel project root. Direct device credentials are never stored in source control. The provisioning endpoint accepts a one-time token issued by the admin endpoint, records only a credential fingerprint in device metadata, and stores the credential encrypted with AES-256-GCM.

Endpoints:

- `GET /api/health` — fail-closed configuration health
- `POST /api/admin/provision-token` — admin-only one-time bootstrap token
- `POST /api/provision` — one-time device credential registration, remains `PENDING_COMMISSIONING`
- `POST /api/admin/enqueue` — admin-only bounded capability queueing
- `GET /api/jobs?device_id=...` — device job retrieval
- `POST /api/results` — signed result verification and acknowledgement

Only `diagnostic_status` and `inventory_snapshot` are accepted capabilities. There is no arbitrary shell or controller-supplied executable text.

Deployment does not change the physical evidence boundary: registration remains pending until the existing Centinal26 controller validates the real Android enrollment bundle and heartbeat.

Current platform limitation: the connected Vercel account has team `ETE` but no project, and the exposed deployment wrapper cannot create/link a project in this session. Repository code is therefore deployment-ready but must not be reported as live until a Vercel project and Upstash integration are actually materialized and the health endpoint returns `READY`.
