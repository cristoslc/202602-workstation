variable "b2_master_key_id" {
  description = "B2 master application key ID (from SOPS)"
  type        = string
  sensitive   = true
}

variable "b2_master_key" {
  description = "B2 master application key secret (from SOPS)"
  type        = string
  sensitive   = true
}

variable "bucket_name" {
  description = "B2 bucket name for restic backups"
  type        = string
}

variable "hostname" {
  description = "Workstation hostname (used to name the scoped key)"
  type        = string
}

variable "provision_date" {
  description = "ISO date of this provision (YYYY-MM-DD), used to disambiguate keys after a wipe+reinstall"
  type        = string
}

variable "create_bucket" {
  description = "Create the B2 bucket (true for first workstation, false to look up existing)"
  type        = bool
  default     = true
}
