locals {
  config = yamldecode(file(var.config_file))

  gcp_cfg = try(local.config.gcp, {})

  function_name = var.function_name != "" ? var.function_name : (
    try(local.gcp_cfg.function_name, "") != "" ? local.gcp_cfg.function_name : (
      local.config.server_name != "" ? lower(replace(local.config.server_name, " ", "-")) : "opencontext-mcp-server"
    )
  )

  memory_mb     = try(local.gcp_cfg.function_memory_mb, null) != null ? local.gcp_cfg.function_memory_mb : var.function_memory_mb
  timeout_sec   = try(local.gcp_cfg.function_timeout_sec, null) != null ? local.gcp_cfg.function_timeout_sec : var.function_timeout_sec
  min_instances = try(local.gcp_cfg.min_instance_count, null) != null ? local.gcp_cfg.min_instance_count : var.min_instance_count
  max_instances = try(local.gcp_cfg.max_instance_count, null) != null ? local.gcp_cfg.max_instance_count : var.max_instance_count

  config_json = jsonencode(local.config)

  artifact_bucket = var.artifact_bucket_name != "" ? var.artifact_bucket_name : "${var.project_id}-opencontext-fn-${var.stage_name}"

  zip_path = "${path.module}/gcf-deployment.zip"
  # Include the function name in the source object so deployed artifacts are
  # easy to map back to a specific Cloud Function/environment.
  zip_object_name = "${local.function_name}-source-${filebase64sha256(local.zip_path)}.zip"
}

resource "google_project_service" "required_apis" {
  for_each = toset([
    "cloudfunctions.googleapis.com",
    "cloudbuild.googleapis.com",
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "storage.googleapis.com",
  ])

  project            = var.project_id
  service            = each.key
  disable_on_destroy = false
}

resource "google_storage_bucket" "function_source" {
  name                        = local.artifact_bucket
  location                    = var.gcp_region
  uniform_bucket_level_access = true
  force_destroy               = true

  versioning {
    enabled = true
  }

  labels = {
    project     = "opencontext"
    environment = var.stage_name
    managed_by  = "terraform"
  }

  depends_on = [google_project_service.required_apis]
}

resource "google_storage_bucket_object" "function_zip" {
  name   = local.zip_object_name
  bucket = google_storage_bucket.function_source.name
  source = local.zip_path

  depends_on = [google_storage_bucket.function_source]
}

resource "google_service_account" "function" {
  # Stable unique id (GCP: 6–30 chars, start with letter)
  account_id   = "ocfn-${substr(md5("${var.project_id}-${local.function_name}"), 0, 20)}"
  display_name = "OpenContext MCP ${local.function_name} (${var.stage_name})"
  description  = "Runtime identity for OpenContext Cloud Functions gen2"
}

resource "google_cloudfunctions2_function" "mcp" {
  name        = local.function_name
  location    = var.gcp_region
  description = "OpenContext MCP HTTP server (Cloud Functions gen2)"

  build_config {
    runtime     = "python311"
    entry_point = "mcp_http"
    source {
      storage_source {
        bucket = google_storage_bucket.function_source.name
        object = google_storage_bucket_object.function_zip.name
      }
    }
  }

  service_config {
    max_instance_count    = local.max_instances
    min_instance_count    = local.min_instances
    available_memory      = "${local.memory_mb}Mi"
    timeout_seconds       = local.timeout_sec
    service_account_email = google_service_account.function.email
    ingress_settings      = "ALLOW_ALL"
    environment_variables = {
      OPENCONTEXT_CONFIG = local.config_json
    }
    all_traffic_on_latest_revision = true
  }

  labels = {
    project     = "opencontext"
    environment = var.stage_name
    managed_by  = "terraform"
  }

  depends_on = [
    google_project_service.required_apis,
    google_service_account.function,
  ]

  lifecycle {
    ignore_changes = [
      build_config[0].source[0].storage_source[0].generation,
    ]
  }
}

# Gen2 functions run on Cloud Run — public HTTPS requires run.invoker on the service
resource "google_cloud_run_v2_service_iam_member" "public_invoker" {
  project  = var.project_id
  location = var.gcp_region
  name     = google_cloudfunctions2_function.mcp.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
