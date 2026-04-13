# GCP Terraform (Cloud Functions gen2)

Deploy OpenContext to **Google Cloud Functions (2nd gen)** with Terraform. Runtime behavior matches AWS: configuration is injected as **`OPENCONTEXT_CONFIG`** (JSON), same as Lambda.

This module does **not** use the `opencontext` CLI yet — package the app, copy artifacts, then run Terraform manually (see below).

## Architecture

- **Cloud Functions gen2** (Python 3.11) — HTTP trigger; MCP endpoint is **`{function_url}/mcp`** (same path as AWS API Gateway).
- **GCS** — Source zip uploaded to a bucket; the function build reads from `gcf-deployment.zip` in this directory (or update the path in `main.tf` locals).
- **Cloud Run IAM** — `roles/run.invoker` for `allUsers` so the HTTPS URL is publicly invokable (equivalent to open API Gateway invoke in the AWS template).
- **Optional Phase 2** — [Google Cloud API Gateway](API_GATEWAY_PHASE2.md) + custom domain for API-management–style features.
- **Failure / DLQ** — AWS Lambda uses an SQS dead-letter queue for async failures. HTTP Cloud Functions gen2 does not mirror that; you can add an optional Pub/Sub topic and custom handling later if you introduce async triggers.

## Prerequisites

- GCP project, billing enabled if required by your org
- [gcloud](https://cloud.google.com/sdk/docs/install) and Application Default Credentials (`gcloud auth application-default login`)
- Terraform >= 1.0
- APIs enabled (Terraform enables common ones; you may need org approval)

## 1. Bootstrap remote state (once)

```bash
cd terraform/gcp/bootstrap
terraform init
terraform apply -var="project_id=YOUR_PROJECT_ID"
```

Use a **globally unique** bucket name if the default is taken (`-var="state_bucket_name=..."`). Align [`backend.tf`](backend.tf) or pass `-backend-config="bucket=..."` when initializing the main module.

## 2. Configure the app

- Copy `config-example.yaml` to `config.yaml` at the repo root and enable exactly one plugin (same rule as AWS).
- Optional `gcp:` block in `config.yaml` for region, `function_name`, `function_memory_mb`, `function_timeout_sec` (see `config-example.yaml`).

## 3. Build the deployment zip

Mirror the Lambda packaging idea: install dependencies and app code into a flat directory, include **`main.py`** at the **root** of the zip (re-exports `mcp_http` for Cloud Functions).

Example (from repo root, after `uv sync`):

```bash
rm -rf .deploy && mkdir .deploy
uv pip install -r requirements.txt --target .deploy --python-platform linux_x86_64 --python-version 3.11 --no-compile
cp -R core plugins server custom_plugins .deploy/ 2>/dev/null || true
mkdir -p .deploy/custom_plugins
cp main.py .deploy/
cd .deploy && zip -r ../terraform/gcp/gcf-deployment.zip . && cd ..
```

Adjust `--python-platform` if Google’s build uses a different arch; Cloud Build runs on Google’s infrastructure and installs from your zip layout.

## 4. Deploy with Terraform

```bash
cd terraform/gcp
terraform init   # add -backend-config if your state bucket name differs
terraform plan -var="project_id=YOUR_PROJECT_ID" -var="gcp_region=us-central1" -var="stage_name=staging"
terraform apply
```

Use `-var="config_file=../../config.yaml"` if you run from another working directory.

## Outputs

- `mcp_endpoint_url` — MCP JSON-RPC URL (`…/mcp`).
- `function_uri` — Base URL of the function.
- `source_bucket` — Bucket storing the uploaded zip.

## Files

| File | Purpose |
|------|---------|
| [`main.tf`](main.tf) | Config parse, GCS object, Cloud Function, public invoker |
| [`variables.tf`](variables.tf) | `project_id`, region, stage, overrides |
| [`outputs.tf`](outputs.tf) | URLs and bucket |
| [`backend.tf`](backend.tf) | GCS backend for state |
| [`versions.tf`](versions.tf) | Provider pins |
| `gcf-deployment.zip` | **You** build and refresh before `apply` (CI uses an empty placeholder for `validate` only) |

## CI

Repository CI runs `terraform fmt` / `validate` on all `terraform/*/` directories. A minimal empty `gcf-deployment.zip` must exist so `filebase64sha256` and `validate` succeed locally and in GitHub Actions.
