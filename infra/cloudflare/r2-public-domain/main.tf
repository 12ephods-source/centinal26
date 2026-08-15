locals {
  custom_domain = lower(trimspace(var.custom_domain))
  jurisdiction  = lower(var.jurisdiction)
}

resource "cloudflare_r2_bucket" "bucket" {
  account_id    = var.account_id
  name          = var.bucket_name
  jurisdiction  = local.jurisdiction
  location      = var.location == null ? null : lower(var.location)
  storage_class = var.storage_class

  lifecycle {
    prevent_destroy = true
  }
}

resource "cloudflare_r2_custom_domain" "domain" {
  count = var.manage_custom_domain ? 1 : 0

  account_id   = var.account_id
  bucket_name  = cloudflare_r2_bucket.bucket.name
  domain       = local.custom_domain
  zone_id      = var.zone_id
  enabled      = true
  jurisdiction = local.jurisdiction == "default" ? null : local.jurisdiction
  min_tls      = var.min_tls
}

data "cloudflare_r2_custom_domain" "existing_domain" {
  count = var.manage_custom_domain ? 0 : 1

  account_id  = var.account_id
  bucket_name = cloudflare_r2_bucket.bucket.name
  domain      = local.custom_domain
}

resource "cloudflare_r2_managed_domain" "r2_dev" {
  account_id   = var.account_id
  bucket_name  = cloudflare_r2_bucket.bucket.name
  enabled      = var.enable_r2_dev
  jurisdiction = local.jurisdiction == "default" ? null : local.jurisdiction
}
