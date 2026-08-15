variable "account_id" {
  description = "Cloudflare account ID that owns the R2 bucket."
  type        = string

  validation {
    condition     = length(trimspace(var.account_id)) > 0
    error_message = "account_id must not be empty."
  }
}

variable "zone_id" {
  description = "Cloudflare zone ID that owns the custom hostname."
  type        = string

  validation {
    condition     = length(trimspace(var.zone_id)) > 0
    error_message = "zone_id must not be empty."
  }
}

variable "bucket_name" {
  description = "R2 bucket name."
  type        = string

  validation {
    condition = (
      length(var.bucket_name) >= 3 &&
      length(var.bucket_name) <= 63 &&
      can(regex("^[a-z0-9][a-z0-9-]*[a-z0-9]$", var.bucket_name))
    )
    error_message = "bucket_name must be 3-63 lowercase letters, digits, or hyphens and may not begin or end with a hyphen."
  }
}

variable "custom_domain" {
  description = "Fully qualified hostname to connect to the R2 bucket, for example assets.example.com."
  type        = string

  validation {
    condition     = length(trimspace(var.custom_domain)) > 3 && strcontains(var.custom_domain, ".")
    error_message = "custom_domain must be a fully qualified hostname."
  }
}

variable "location" {
  description = "Optional R2 location hint. Null uses Cloudflare automatic placement (recommended)."
  type        = string
  default     = null
  nullable    = true

  validation {
    condition = var.location == null || contains(
      ["apac", "eeur", "enam", "weur", "wnam", "oc"],
      lower(var.location),
    )
    error_message = "location must be one of apac, eeur, enam, weur, wnam, oc, or null."
  }
}

variable "storage_class" {
  description = "Default storage class for new R2 objects."
  type        = string
  default     = "Standard"

  validation {
    condition     = contains(["Standard", "InfrequentAccess"], var.storage_class)
    error_message = "storage_class must be Standard or InfrequentAccess."
  }
}

variable "min_tls" {
  description = "Minimum TLS version accepted by the R2 custom domain."
  type        = string
  default     = "1.2"

  validation {
    condition     = contains(["1.0", "1.1", "1.2", "1.3"], var.min_tls)
    error_message = "min_tls must be 1.0, 1.1, 1.2, or 1.3."
  }
}

variable "enable_r2_dev" {
  description = "Whether to expose the bucket through Cloudflare's rate-limited r2.dev development hostname. Keep false for production."
  type        = bool
  default     = false
}
