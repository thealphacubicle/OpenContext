# Terraform Backend Bootstrap

Creates the S3 bucket used by the main OpenContext Terraform configuration for remote state storage.

> **Note:** For most users, `opencontext configure` automatically creates the default `opencontext-terraform-state` S3 bucket. This bootstrap module is only needed if you want a custom per-account bucket name instead of that default.

## Prerequisites

- AWS CLI configured
- Terraform >= 1.0

## Usage

Run this **once** before using the main `terraform/aws` configuration:

```bash
cd terraform/bootstrap
terraform init
terraform apply
```

This creates:

- **S3 bucket** `opencontext-terraform-state` – stores Terraform state with versioning and encryption

**Note:** The main `terraform/aws` configuration uses the S3 bucket for state. The bucket name must match the `bucket` in `terraform/aws/main.tf` backend block.

## Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `aws_region` | `us-east-1` | AWS region for backend resources |
| `state_bucket_name` | `opencontext-terraform-state` | S3 bucket name (must match `terraform/aws/main.tf`) |

## After Bootstrap

Deploy the main OpenContext stack:

```bash
cd ../aws
terraform init
terraform plan -var="config_file=config.yaml"
terraform apply
```

Or use the CLI from the project root: `opencontext deploy --env staging`
