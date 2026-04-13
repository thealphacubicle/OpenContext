output "function_name" {
  description = "Cloud Functions gen2 function name"
  value       = google_cloudfunctions2_function.mcp.name
}

output "function_uri" {
  description = "HTTPS URL of the Cloud Function (Cloud Run–backed)"
  value       = google_cloudfunctions2_function.mcp.url
}

output "mcp_endpoint_url" {
  description = "MCP JSON-RPC endpoint (POST /mcp)"
  value       = "${google_cloudfunctions2_function.mcp.url}/mcp"
}

output "function_service_account" {
  description = "Service account email used by the function"
  value       = google_service_account.function.email
}

output "source_bucket" {
  description = "GCS bucket holding deployment zip artifacts"
  value       = google_storage_bucket.function_source.name
}

output "source_object" {
  description = "Object name of the deployed zip in the source bucket"
  value       = google_storage_bucket_object.function_zip.name
}
