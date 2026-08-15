resource "cloudflare_r2_bucket" "bucket" {
  account_id    = var.account_id
  name          = var.bucket_name
  location      = var.location == null ? null : lower(var.location)
  storage_class = var.storage_class
}

# R2 custom-domain attachment creates/manages the required DNS CNAME in the
# Cloudflare zone. Do not create a second cloudflare_dns_record for the same
# hostname; that would create competing ownership of one DNS record.
resource "cloudflare_r2_custom_domain" "domain" {
  account_id  = var.account_id
  bucket_name = cloudflare_r2_bucket.bucket.name
  domain      = var.custom_domain
  zone_id     = var.zone_id
  enabled     = true
  min_tls     = var.min_tls
}

# r2.dev is a separate public-development endpoint. It is explicitly managed
# here so production deployments default to disabled rather than inheriting an
# unknown dashboard setting.
resource "cloudflare_r2_managed_domain" "r2_dev" {
  account_id  = var.account_id
  bucket_name = cloudflare_r2_bucket.bucket.name
  enabled     = var.enable_r2_dev
}
