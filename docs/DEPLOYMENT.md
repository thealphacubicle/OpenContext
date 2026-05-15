# Deployment Guide

Deploy OpenContext to **AWS** (Lambda + API Gateway) or **GCP** (Cloud Functions gen2). See [Getting Started](GETTING_STARTED.md) for the quick path. For per-command flags, see [CLI Reference](CLI.md).

## Cloud provider (`--cloud`)

Most lifecycle commands accept `--cloud aws|gcp` (default: **`aws`**).

| Command | `--cloud` support |
|---------|-------------------|
| `opencontext authenticate` | Yes |
| `opencontext configure` | Yes |
| `opencontext validate` | Yes |
| `opencontext deploy` | Yes |
| `opencontext status` | Yes |
| `opencontext logs` | Yes |
| `opencontext destroy` | Yes |

AWS-only today: `domain`, `architecture`, `cost` (CloudWatch / AWS pricing).

Terraform roots: `terraform/aws/` and `terraform/gcp/`. GCP module details: [terraform/gcp/README.md](../terraform/gcp/README.md).

## Prerequisites (all clouds)

- Terraform >= 1.0
- Python 3.11+
- Cloud CLI and credentials for the provider you choose (see below)

Run `opencontext authenticate` (add `--cloud gcp` for GCP) to verify prerequisites before deploying.

---

## AWS deployment

### Prerequisites

- AWS account, [AWS CLI](https://aws.amazon.com/cli/) configured (`aws configure` or SSO)

### AWS permissions

- Lambda (create, update functions)
- IAM (roles, policies)
- CloudWatch Logs
- API Gateway
- SQS (Dead Letter Queue for Lambda failures)
- X-Ray (tracing, via AWSXRayDaemonWriteAccess)
- ACM (only required when configuring a custom domain)

### Deploy (CLI)

```bash
opencontext authenticate
opencontext configure                    # or: opencontext configure --cloud aws
opencontext validate --env staging
opencontext deploy --env staging         # default --cloud aws
```

`opencontext deploy` packages the Lambda (`uv pip install` from `requirements.txt` into the bundle), runs `terraform plan`, shows a summary, asks for confirmation, then applies. The **API Gateway URL** (includes `/mcp`) is printed on success.

To update after changing code or config:

```bash
opencontext deploy --env staging
```

### Manual Terraform (AWS)

First-time: bootstrap the S3 backend (run once). See [terraform/bootstrap/README.md](../terraform/bootstrap/README.md):

```bash
cd terraform/bootstrap
terraform init && terraform apply
```

Then deploy:

```bash
cd terraform/aws
terraform init
terraform plan -var-file=staging.tfvars -out=tfplan
terraform apply tfplan
```

`opencontext configure` generates `terraform/aws/<env>.tfvars`. For manual runs, ensure `config.yaml` exists and the `.tfvars` file matches your environment.

### AWS endpoints

All traffic goes through the **API Gateway URL**. There is no separate no-auth endpoint.

| Endpoint | Use Case | Auth |
|----------|----------|------|
| **API Gateway** | All environments | Rate limiting, daily quota |

**Get the URL:**

```bash
opencontext status --env staging

# Or via Terraform
cd terraform/aws
terraform output -raw api_gateway_url   # Includes /mcp suffix
```

**API Gateway behavior:**

- **Throttling:** Default 10 burst / 5 sustained req/s; configurable via `api_burst_limit` and `api_rate_limit`
- **Daily quota:** Configurable via `api_quota_limit`
- **Stage name:** Default `staging`; URL format: `https://...execute-api.region.amazonaws.com/staging/mcp`
- **HTTP 429** when rate or quota is exceeded

Custom domains: `opencontext domain --env staging` (ACM + DNS). See [CLI Reference](CLI.md).

### AWS configuration (`config.yaml`)

Config is passed via the `OPENCONTEXT_CONFIG` environment variable on Lambda. Use `opencontext configure` or copy from `config-example.yaml`.

```yaml
aws:
  region: "us-east-1"
  lambda_name: "my-mcp-server"   # Optional; defaults from server_name
  lambda_memory: 512             # 128–10240 MB
  lambda_timeout: 120            # 1–900 seconds
```

### AWS monitoring

- **CloudWatch Logs:** `/aws/lambda/<function-name>`, 14-day retention
- **CLI:** `opencontext logs --env staging` (`--follow`, `--verbose`)
- **Raw:** `aws logs tail /aws/lambda/my-mcp-server --follow`

### AWS cost (us-east-1, indicative)

- Lambda: ~$0.20/1M requests, ~$0.0000166667/GB-second
- API Gateway: ~$3.50/1M requests
- Example: 100K req/month, 512 MB, 1s avg ≈ **$1/month**

Use `opencontext cost --env staging` for estimates from CloudWatch metrics.

---

## GCP deployment

### Prerequisites

- GCP project with billing enabled (if required by your org)
- [gcloud](https://cloud.google.com/sdk/docs/install) and Application Default Credentials: `gcloud auth application-default login`
- Required APIs (Terraform enables common ones; org policies may require approval)

### Deploy (CLI)

```bash
opencontext authenticate --cloud gcp
opencontext configure --cloud gcp
opencontext validate --cloud gcp --env staging
opencontext deploy --cloud gcp --env staging
```

`opencontext deploy --cloud gcp` builds `gcf-deployment.zip`, copies it into `terraform/gcp/`, runs `terraform plan` / `apply`, and prints **`mcp_endpoint_url`** (HTTPS URL ending in `/mcp`).

Day-2 operations:

```bash
opencontext status --cloud gcp --env staging
opencontext logs --cloud gcp --env staging
opencontext destroy --cloud gcp --env staging
```

### Bootstrap remote state (GCP, once)

```bash
cd terraform/gcp/bootstrap
terraform init
terraform apply -var="project_id=YOUR_PROJECT_ID"
```

Use a globally unique bucket name if the default is taken (`-var="state_bucket_name=..."`). Align `terraform/gcp/backend.tf` or pass `-backend-config="bucket=..."` when initializing the main module.

### Manual Terraform (GCP)

See [terraform/gcp/README.md](../terraform/gcp/README.md) for packaging `gcf-deployment.zip` and manual `terraform apply`.

### GCP endpoints

| Output | Description |
|--------|-------------|
| `mcp_endpoint_url` | MCP JSON-RPC URL (`…/mcp`) — use with Claude Connectors |
| `function_uri` | Base HTTPS URL of the Cloud Function |
| `source_bucket` | GCS bucket storing the deployment zip |

**Get the URL:**

```bash
opencontext status --cloud gcp --env staging

cd terraform/gcp
terraform output -raw mcp_endpoint_url
```

The function is publicly invokable via Cloud Run IAM (`allUsers` + `roles/run.invoker`), similar to open API Gateway invoke on AWS. Optional API Gateway + custom domain: [terraform/gcp/API_GATEWAY_PHASE2.md](../terraform/gcp/API_GATEWAY_PHASE2.md).

### GCP configuration (`config.yaml`)

```yaml
gcp:
  region: "us-central1"
  function_name: "your-opendata-mcp"   # Optional; defaults from server_name slug
  function_memory_mb: 512
  function_timeout_sec: 120            # Max 3600 for gen2
  min_instance_count: 0
  max_instance_count: 100
```

The configure wizard also prompts for `project_id` and optional `artifact_bucket_name` (written to `terraform/gcp/<env>.tfvars`).

### GCP monitoring

- **CLI:** `opencontext logs --cloud gcp --env staging` (`gcloud functions logs read` under the hood)
- **Console:** Cloud Logging for the Cloud Functions gen2 service

There is no AWS-style SQS DLQ on the HTTP Cloud Function path; async failure handling differs from Lambda. See [terraform/gcp/README.md](../terraform/gcp/README.md).

### GCP cost

Pricing depends on invocations, memory, CPU time, and networking. Use [Google Cloud pricing](https://cloud.google.com/functions/pricing) and billing reports for your project. There is no `opencontext cost` command for GCP yet.

---

## Shared behavior

### Configuration and plugins

- **`OPENCONTEXT_CONFIG`:** JSON config injected at deploy time (same env var name on AWS and GCP).
- **One plugin per deployment:** Exactly one `plugins.*.enabled: true` in `config.yaml`. See [Architecture](ARCHITECTURE.md).
- **Packaging:** Both clouds use `requirements.txt` with `uv pip install` targeting **Python 3.11** and **linux x86_64** wheels (`x86_64-manylinux2014`).

### Updating

Change code or `config.yaml`, then redeploy with the same `--cloud` and `--env` you used initially:

```bash
opencontext deploy --env staging
opencontext deploy --cloud gcp --env staging
```

### Destroy

```bash
opencontext destroy --env staging
opencontext destroy --cloud gcp --env staging
```

Runs `terraform destroy` after confirmation. You must type the environment name to confirm. This is irreversible.

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Multiple plugins | Enable only ONE in `config.yaml` |
| Wrong cloud / missing `.tfvars` | Run `opencontext configure` with the same `--cloud` as deploy; files live under `terraform/<cloud>/` |
| AWS Lambda timeout | Increase `lambda_timeout` in `config.yaml` |
| GCP function timeout | Increase `function_timeout_sec` in `config.yaml` |
| 500 error | `opencontext logs --env staging` (add `--cloud gcp` on GCP) |
| Validation fails (GCP) | `opencontext authenticate --cloud gcp`; check ADC and `project_id` in `.tfvars` |
| High AWS cost | Reduce `lambda_memory`, review usage; use `opencontext cost` |

## Security

- **AWS:** API Gateway rate limiting and daily quotas; optional custom domain with ACM.
- **GCP:** Public HTTPS invoke on the function URL; tighten IAM if you add API Gateway or IAP later.
- Store secrets in environment variables or secret managers, not in committed config.
