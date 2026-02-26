terraform {
  required_version = ">= 1.5"

  required_providers {
    b2 = {
      source  = "Backblaze/b2"
      version = "~> 0.9"
    }
  }

  # State lives per-workstation at ~/.local/share/terraform/b2-backup/
  # Passed via: terraform init -backend-config="path=..."
  backend "local" {}
}

provider "b2" {
  application_key_id = var.b2_master_key_id
  application_key    = var.b2_master_key
}

# ── Bucket (created on first workstation, imported on subsequent) ──

resource "b2_bucket" "backup" {
  count = var.create_bucket ? 1 : 0

  bucket_name = var.bucket_name
  bucket_type = "allPrivate"

  default_server_side_encryption {
    algorithm = "AES256"
    mode      = "SSE-B2"
  }

  lifecycle {
    prevent_destroy = true
  }
}

data "b2_bucket" "existing" {
  count = var.create_bucket ? 0 : 1

  bucket_name = var.bucket_name
}

locals {
  bucket_id = var.create_bucket ? b2_bucket.backup[0].bucket_id : data.b2_bucket.existing[0].bucket_id
}

# ── Per-workstation application key (scoped to bucket) ─────────────

resource "b2_application_key" "workstation" {
  key_name  = "restic-${var.hostname}"
  bucket_id = local.bucket_id

  capabilities = [
    "listBuckets",
    "listFiles",
    "readFiles",
    "writeFiles",
    "deleteFiles",
  ]
}
