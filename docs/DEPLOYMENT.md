# Deployment Guide

Deploy OpenContext to AWS Lambda. See [Getting Started](GETTING_STARTED.md) for the quick path.

## Prerequisites

- AWS account, AWS CLI configured
- Terraform >= 1.0
- Python 3.11+

## AWS Permissions

- Lambda (create, update functions)
- IAM (roles, policies)
- CloudWatch Logs
- API Gateway / Lambda Function URLs

## Deployment

```bash
# Configure AWS
aws configure

# Deploy (validates config, packages, deploys)
./scripts/deploy.sh
```

### Manual Terraform

```bash
cd terraform/aws
terraform init
terraform plan -var="lambda_name=my-mcp-server" -var="aws_region=us-east-1" -var="config_file=../../config.yaml"
terraform apply
```

## Endpoints

| Endpoint | Use Case | Auth |
|----------|----------|------|
| **API Gateway** | Production | API key, rate limiting |
| **Lambda Function URL** | Testing | None |

### Get URLs

```bash
cd terraform/aws
terraform output -raw api_gateway_url   # Production
terraform output -raw lambda_url       # Testing
```

### API Gateway

- **Rate limit:** 10 burst, 5 sustained req/s; 1000/day quota
- **429** when exceeded
- Use for production; Lambda URL has no auth

## Configuration

Config is passed via `OPENCONTEXT_CONFIG` env var. Edit `config.yaml` and run `./scripts/deploy.sh` to update.

### Lambda Settings

```yaml
aws:
  region: "us-east-1"
  lambda_memory: 512    # 128–10240 MB
  lambda_timeout: 120   # 1–900 seconds
```

## Monitoring

- **CloudWatch Logs:** `/aws/lambda/<function-name>`, 14-day retention
- **Tail logs:** `aws logs tail /aws/lambda/my-mcp-server --follow`

## Updating & Cleanup

**Update:** Change code/config, run `./scripts/deploy.sh` again.

**Destroy:**
```bash
cd terraform/aws
terraform destroy
```

## Cost (us-east-1)

- Lambda: ~$0.20/1M requests, ~$0.0000166667/GB-second
- Function URL: Free
- Example: 100K req/month, 512 MB, 1s avg ≈ **$1/month**

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Multiple plugins | Enable only ONE in `config.yaml` |
| Lambda timeout | Increase `lambda_timeout` |
| 500 error | Check CloudWatch logs, validate config |
| High cost | Reduce `lambda_memory`, review usage |

## Security

- Use API Gateway for production (rate limiting, API key)
- Lambda URL is public—testing only
- Store secrets in env vars, not code
