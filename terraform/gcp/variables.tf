variable "project_id" {
  description = "GCP project ID for OpenContext deployment"
  type        = string
}

variable "gcp_region" {
  description = "GCP region (e.g. us-central1)"
  type        = string
  default     = "us-central1"
}

variable "config_file" {
  description = "Path to config.yaml (relative to this module or absolute)"
  type        = string
  default     = "../../config.yaml"
}

variable "function_name" {
  description = "Cloud Function name (empty = derive from config.yaml server_name or gcp.function_name)"
  type        = string
  default     = ""
}

variable "function_memory_mb" {
  description = "Memory for the Cloud Function (MiB)"
  type        = number
  default     = 512
}

variable "function_timeout_sec" {
  description = "Timeout in seconds (max 3600 for Cloud Functions gen2)"
  type        = number
  default     = 120
}

variable "stage_name" {
  description = "Environment label (e.g. staging, prod) — used in labels and resource names"
  type        = string
  default     = "staging"
}

variable "artifact_bucket_name" {
  description = "Optional: GCS bucket name for function source zips (empty = auto-generated from project + stage)"
  type        = string
  default     = ""
}
