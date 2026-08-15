variable "account_id" {
  description = "Cloudflare account ID that owns the R2 bucket."
  type        = string

  validation {
    condition     = can(regex("^[0-9a-fA-F]{32}$", trimspace(var.account_id)))
    error_message = "account_id must be a 32-character Cloudflare account identifier."
  }
}

variable "zone_id" {
  description = "Cloudflare zone ID that owns the custom hostname."
  type        = string

  validation {
    condition     = can(regex("^[0-9a-fA-F]{32}$", trimspace(var.zone_id)))
    error_message = "zone_id must be a 32-character Cloudflare zone identifier."
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
    condition = (
      length(trimspace(var.custom_domain)) > 3 &&
      can(regex("^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$", trimspace(var.custom_domain))) &&
      !endswith(lower(trimspace(var.custom_domain)), ".r2.dev")
    )
    error_message = "custom_domain must be a valid fully qualified hostname and must not be an r2.dev hostname."
  }
}

variable "manage_custom_domain" {
  description = "True creates/manages the R2 custom-domain attachment. False requires that the attachment already exist and reads it without taking ownership."
  type        = bool
  default     = true
}

variable "jurisdiction" {
  description = "R2 data jurisdiction. Keep default unless regulatory requirements require eu or fedramp."
  type        = string
  default     = "default"

  validation {
    condition     = contains(["default", "eu", "fedramp"], lower(var.jurisdiction))
    error_message = "jurisdiction must be default, eu, or fedramp."
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
