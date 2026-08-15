terraform {
  required_version = ">= 1.5.0, < 2.0.0"

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
