terraform {
  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 5.22.0"
    }
  }
}

# Authentication is intentionally environment-based. Set CLOUDFLARE_API_TOKEN
# before plan/apply instead of placing credentials in Terraform configuration.
provider "cloudflare" {}
