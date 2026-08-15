# Cloudflare R2 public bucket + custom domain

Declarative Cloudflare R2 infrastructure for Automation OS. This module creates an R2 bucket, attaches a public custom domain, lets Cloudflare manage the required DNS CNAME, and explicitly controls the separate `r2.dev` development endpoint.

## Security and execution boundary

- The custom domain is **public** when this module is applied because `cloudflare_r2_custom_domain.domain.enabled = true`.
- `r2.dev` is separately managed and defaults to **disabled** (`enable_r2_dev = false`). Cloudflare documents `r2.dev` as a rate-limited development endpoint, not a production hostname.
- Do not put the Cloudflare API token in `terraform.tfvars` or source control. The provider reads `CLOUDFLARE_API_TOKEN` from the environment.
- The custom-domain operation creates/manages the required DNS CNAME. Do not add a separate Terraform DNS record for the same hostname.
- Cloudflare recommends automatic R2 placement; `location = null` therefore remains the default. A location hint can be supplied when access geography justifies it.
- This module does not create WAF or Cloudflare Access policy. Public-vs-authenticated access policy is a separate authorization decision.

## Prerequisites

- Terraform installed.
- A Cloudflare zone in the same account as the R2 bucket.
- A Cloudflare API token with the R2 permissions required to create/manage the bucket and custom-domain settings.

## Configure

```bash
cd infra/cloudflare/r2-public-domain
cp terraform.tfvars.example terraform.tfvars
$EDITOR terraform.tfvars
export CLOUDFLARE_API_TOKEN='...'
```

Do not commit `terraform.tfvars`, `.terraform/`, plan files, or state files.

## Validate and apply

```bash
terraform init
terraform fmt -check
terraform validate
terraform plan -out=tfplan
terraform apply tfplan
```

Re-running `terraform plan`/`apply` is expected; Terraform reconciles declared state rather than requiring repeated dashboard setup.

## Variables

- `account_id` — Cloudflare account containing R2.
- `zone_id` — Cloudflare zone containing the custom hostname.
- `bucket_name` — 3-63 lowercase letters/digits/hyphens.
- `custom_domain` — fully qualified hostname, e.g. `assets.example.com`.
- `location` — optional location hint: `apac`, `eeur`, `enam`, `weur`, `wnam`, or `oc`; null uses automatic placement.
- `storage_class` — `Standard` or `InfrequentAccess`.
- `min_tls` — defaults to `1.2`.
- `enable_r2_dev` — defaults to `false`.

## Existing bucket import

If the bucket already exists, import it instead of creating a duplicate:

```bash
terraform import cloudflare_r2_bucket.bucket '<account_id>/<bucket_name>/default'
terraform plan
```

If the custom domain or managed `r2.dev` setting already exists outside Terraform, import/manage those resources according to the Cloudflare provider's current import documentation before applying. Do not delete and recreate production data merely to get it under Terraform state.

## Access-policy follow-up

This module intentionally stops at public custom-domain publication. If the desired policy is authenticated/internal access, create Cloudflare Access/WAF resources first and only then expose the R2 custom domain. Cloudflare warns that connecting a custom domain makes the bucket public by default unless an access layer has already been configured.

## Upstream references

- Cloudflare Terraform provider: https://registry.terraform.io/providers/cloudflare/cloudflare/latest
- R2 Terraform resources: https://developers.cloudflare.com/api/terraform/resources/r2/
- R2 public buckets/custom domains: https://developers.cloudflare.com/r2/buckets/public-buckets/

© 2026 Robert Frost
