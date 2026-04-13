# Remote state in GCS. Create the bucket first (see bootstrap/README.md), then either:
#   terraform init -backend-config="bucket=YOUR_STATE_BUCKET"
# or set bucket below to match your bootstrap bucket and run terraform init.
terraform {
  backend "gcs" {
    bucket = "opencontext-terraform-state-gcp"
    prefix = "opencontext/gcp/terraform.tfstate"
  }
}
