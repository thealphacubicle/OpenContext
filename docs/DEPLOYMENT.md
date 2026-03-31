# Deployment Guide

Deploy OpenContext to AWS Lambda. See [Getting Started](GETTING_STARTED.md) for the quick path.

## Prerequisites

- AWS account, AWS CLI configured
- Terraform >= 1.0
- Python 3.11+

Run `opencontext authenticate` to verify all prerequisites before deploying.

## AWS Permissions

- Lambda (create, update functions)
- IAM (roles, policies)
- CloudWatch Logs
- API Gateway / Lambda Function URLs

## Deployment

### Using the CLI (recommended)

```bash
# Check prerequisites
opencontext authenticate

# Configure (creates config.yaml, .tfvars, and Terraform workspace)
opencontext configure

# Validate before deploying
opencontext validate --env staging

# Deploy
opencontext deploy --env staging
```

`opencontext deploy` packages the Lambda, runs `terraform plan`, shows a summary of changes, asks for confirmation, then applies. The API Gateway URL is printed on success.

To update after changing code or config, just run `opencontext deploy --env staging` again.

### Manual Terraform

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

The `opencontext configure` command generates the `.tfvars` file. For manual runs, ensure `config.yaml` exists in the project root and `terraform/aws/staging.tfvars` has the correct values.

## Endpoints

| Endpoint | Use Case | Auth |
|----------|----------|------|
| **API Gateway** | Production | Rate limiting, daily quota |
| **Lambda Function URL** | Testing | None |

### Get URLs

```bash
# Via CLI
opencontext status --env staging

# Via Terraform directly
cd terraform/aws
terraform output -raw api_gateway_url   # Production (includes /mcp)
terraform output -raw lambda_url        # Testing
```

### API Gateway

- **Rate limit:** 100 burst, 50 sustained req/s (configurable via Terraform variables)
- **Daily quota:** 1000 requests/day (configurable via `api_quota_limit`)
- **Stage name:** Default is `staging`; URL format: `https://...execute-api.region.amazonaws.com/staging/mcp`
- **429** when exceeded
- Use for production; Lambda URL has no auth

## Configuration

Config is passed via `OPENCONTEXT_CONFIG` env var. Use `opencontext configure` to generate `config.yaml`, or create it manually from `config-example.yaml`.

### Lambda Settings (in config.yaml)

```yaml
aws:
  region: "us-east-1"
  lambda_name: "my-mcp-server"   # Optional; defaults from server_name
  lambda_memory: 512             # 128–10240 MB
  lambda_timeout: 120            # 1–900 seconds
```

## Monitoring

- **CloudWatch Logs:** `/aws/lambda/<function-name>`, 14-day retention
- **Tail logs via CLI:** `opencontext logs --env staging`
- **Stream logs:** `opencontext logs --env staging --follow`
- **Raw AWS CLI:** `aws logs tail /aws/lambda/my-mcp-server --follow`

## Updating & Cleanup

**Update:** Change code or `config.yaml`, then run `opencontext deploy --env staging` again.

**Destroy:**
```bash
opencontext destroy --env staging
```

This runs `terraform destroy` with a confirmation prompt. You must type the environment name to confirm.

## Cost (us-east-1)

- Lambda: ~$0.20/1M requests, ~$0.0000166667/GB-second
- Function URL: Free
- Example: 100K req/month, 512 MB, 1s avg ≈ **$1/month**

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Multiple plugins | Enable only ONE in `config.yaml` |
| Lambda timeout | Increase `lambda_timeout` in `config.yaml` |
| 500 error | `opencontext logs --env staging` |
| Missing `.tfvars` | Run `opencontext configure` |
| High cost | Reduce `lambda_memory`, review usage |

## Security

- Use API Gateway for production (rate limiting, quota)
- Lambda URL is public — testing only
- Store secrets in env vars, not code
