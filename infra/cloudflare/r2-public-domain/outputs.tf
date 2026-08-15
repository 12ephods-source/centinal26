output "bucket_name" {
  description = "Created R2 bucket name."
  value       = cloudflare_r2_bucket.bucket.name
}

output "custom_domain" {
  description = "Public custom hostname connected to the R2 bucket."
  value       = cloudflare_r2_custom_domain.domain.domain
}

output "r2_dev_domain" {
  description = "Cloudflare-managed r2.dev hostname for the bucket."
  value       = cloudflare_r2_managed_domain.r2_dev.domain
}

output "r2_dev_enabled" {
  description = "Whether the rate-limited r2.dev development endpoint is enabled."
  value       = var.enable_r2_dev
}
