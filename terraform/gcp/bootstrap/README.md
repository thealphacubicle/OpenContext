# GCP Terraform state bootstrap

Creates a **versioned GCS bucket** for remote Terraform state used by [`../`](../README.md).

## Prerequisites

- [gcloud](https://cloud.google.com/sdk/docs/install) authenticated (`gcloud auth application-default login` and `gcloud config set project YOUR_PROJECT`)
- Terraform >= 1.0
- A GCP project and permission to create GCS buckets

## Usage

```bash
cd terraform/gcp/bootstrap
terraform init
terraform apply -var="project_id=YOUR_PROJECT_ID"
```

The default bucket name is `opencontext-terraform-state-gcp`. It must be **globally unique**; if the name is taken, set:

```bash
terraform apply -var="project_id=YOUR_PROJECT_ID" -var="state_bucket_name=your-org-opencontext-tfstate"
```

Then update the `bucket` in [`../backend.tf`](../backend.tf) to match, or run `terraform init` in `terraform/gcp` with:

```bash
cd ../
terraform init -backend-config="bucket=your-org-opencontext-tfstate"
```
