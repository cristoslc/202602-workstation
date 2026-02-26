output "bucket_name" {
  description = "B2 bucket name"
  value       = var.bucket_name
}

output "application_key_id" {
  description = "Bucket-scoped application key ID for this workstation"
  value       = b2_application_key.workstation.application_key_id
  sensitive   = true
}

output "application_key" {
  description = "Bucket-scoped application key secret for this workstation"
  value       = b2_application_key.workstation.application_key
  sensitive   = true
}
