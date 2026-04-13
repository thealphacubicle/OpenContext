variable "project_id" {
  description = "GCP project ID where the state bucket will be created"
  type        = string
}

variable "gcp_region" {
  description = "Region for the state bucket (e.g. us-central1)"
  type        = string
  default     = "us-central1"
}

variable "state_bucket_name" {
  description = "Globally unique GCS bucket name for Terraform state"
  type        = string
  default     = "opencontext-terraform-state-gcp"
}
