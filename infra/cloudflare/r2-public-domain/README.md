# Cloudflare R2 public bucket + custom domain

Declarative Cloudflare R2 infrastructure for Automation OS. This configuration creates an R2 bucket, attaches a public custom domain, lets Cloudflare own the required DNS attachment, and explicitly controls the separate `r2.dev` development endpoint.

## Current provider contract

This configuration targets Cloudflare Terraform provider `~> 5.22.0`. Current provider documentation exposes:

- `cloudflare_r2_bucket`
- `cloudflare_r2_custom_domain`
- `cloudflare_r2_managed_domain`

The custom-domain resource owns the R2 hostname attachment. Do **not** create a separate `cloudflare_dns_record` for the same hostname.

## Security and execution boundary

- The custom domain is **public** when Terraform owns/applies it because `cloudflare_r2_custom_domain.domain.enabled = true`.
- `r2.dev` is independent and defaults **disabled** (`enable_r2_dev = false`). Cloudflare documents `r2.dev` as a rate-limited development endpoint, not a production hostname.
- The bucket has `prevent_destroy = true`. Destroying the data container requires an explicit reviewed code change first.
- Do not put the Cloudflare API token in `terraform.tfvars`, backend files, or source control. The provider reads `CLOUDFLARE_API_TOKEN` from the environment.
- Cloudflare recommends automatic R2 placement; `location = null` remains the default.
- `jurisdiction` is explicit and defaults to `default`; use `eu` or `fedramp` only when required.
- This configuration does not invent WAF/Access rules. The requested surface is a public custom-domain bucket; authenticated/internal publication is a different policy and must be modeled separately.

## Prerequisites

- Terraform `>= 1.5`.
- A Cloudflare account with R2 enabled.
- A Cloudflare zone in the same account as the R2 bucket.
- A Cloudflare API token with Workers R2 Storage write permissions required by the bucket/custom-domain resources.

## Configure

```bash
cd infra/cloudflare/r2-public-domain
cp terraform.tfvars.example terraform.tfvars
$EDITOR terraform.tfvars
export CLOUDFLARE_API_TOKEN='...'
```

Do not commit `terraform.tfvars`, `.terraform/`, plan files, or state files.

## Safe execution wrapper

```bash
./run.sh validate
./run.sh plan
./run.sh apply --authorize-publication
./run.sh output
```

`apply` refuses to run without both a previously generated `tfplan` and the explicit `--authorize-publication` acknowledgement. It never accepts arbitrary shell source.

## Existing infrastructure and import boundary

The R2 bucket supports Terraform import:

```bash
terraform import cloudflare_r2_bucket.bucket '<account_id>/<bucket_name>/<jurisdiction>'
terraform plan
```

The current Cloudflare provider **does not support Terraform import** for `cloudflare_r2_custom_domain` or `cloudflare_r2_managed_domain`.

For an already attached custom domain, do not delete/recreate it just to satisfy Terraform state. Set `manage_custom_domain = false`; the configuration then verifies the attachment through a data source without claiming ownership.

## Durable Terraform state

Local state is acceptable for initial bootstrap but is not a durable automation backend. Cloudflare documents using a separate R2 bucket as Terraform's S3-compatible remote backend.

A backend cannot safely live in the same bucket it is responsible for creating. Bootstrap a **separate** state bucket first, then:

```bash
cp backend.tf.example backend.tf
cp backend.hcl.example backend.hcl
$EDITOR backend.hcl
export AWS_ACCESS_KEY_ID='bucket-scoped-r2-access-key'
export AWS_SECRET_ACCESS_KEY='bucket-scoped-r2-secret-key'
terraform init -reconfigure -backend-config=backend.hcl
```

The backend examples intentionally contain no credentials.

## CI contract

The dedicated workflow runs Terraform format/init/validate plus `bash -n run.sh`. Repository pytest also checks the publication, no-duplicate-DNS, r2.dev-default-off, prevent-destroy, jurisdiction, secret-boundary, import-boundary, and explicit-apply-authorization invariants.

CI validates source and configuration only. It does not claim infrastructure has been applied to a Cloudflare account.

## Public-access behavior

Cloudflare public buckets can be exposed independently through a custom domain and through `r2.dev`. The custom domain is the production-capable surface and is where Cloudflare features such as WAF, cache, Access, and bot controls can be attached. `r2.dev` is intended for development and remains disabled by default here.

## Upstream references

- Cloudflare Terraform provider: https://registry.terraform.io/providers/cloudflare/cloudflare/latest
- R2 Terraform resources: https://developers.cloudflare.com/api/terraform/resources/r2/
- R2 public buckets/custom domains: https://developers.cloudflare.com/r2/buckets/public-buckets/
- Remote R2 Terraform backend: https://developers.cloudflare.com/terraform/advanced-topics/remote-backend/

© 2026 Robert Frost
