output "state_bucket" {
  description = "GCS bucket name — use this as the backend bucket for terraform/gcp"
  value       = google_storage_bucket.terraform_state.name
}

output "state_bucket_url" {
  description = "gs:// URL for documentation"
  value       = google_storage_bucket.terraform_state.url
}
