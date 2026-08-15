output "bucket_name" {
  description = "R2 bucket name."
  value       = cloudflare_r2_bucket.bucket.name
}

output "bucket_jurisdiction" {
  description = "R2 jurisdiction recorded by Cloudflare."
  value       = cloudflare_r2_bucket.bucket.jurisdiction
}

output "custom_domain" {
  description = "Public custom hostname connected to the R2 bucket."
  value       = local.custom_domain
}

output "custom_domain_managed_by_terraform" {
  description = "Whether this configuration owns the R2 custom-domain attachment."
  value       = var.manage_custom_domain
}

output "r2_dev_domain" {
  description = "Cloudflare-managed r2.dev hostname for the bucket."
  value       = cloudflare_r2_managed_domain.r2_dev.domain
}

output "r2_dev_enabled" {
  description = "Whether the rate-limited r2.dev development endpoint is enabled."
  value       = var.enable_r2_dev
}
