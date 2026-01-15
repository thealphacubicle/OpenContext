# Deployment Guide

Detailed guide for deploying OpenContext to AWS Lambda.

## Prerequisites

- AWS account with appropriate permissions
- AWS CLI configured
- Terraform >= 1.0 installed
- Python 3.11+ installed

## AWS Permissions Required

Your AWS credentials need permissions for:
- Lambda (create, update functions)
- IAM (create roles and policies)
- CloudWatch Logs (create log groups)
- API Gateway / Lambda Function URLs (create URLs)

## Deployment Steps

### 1. Configure AWS Credentials

```bash
aws configure
```

Or set environment variables:
```bash
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_DEFAULT_REGION=us-east-1
```

### 2. Configure Your Plugin

Edit `config.yaml`:

```yaml
server_name: "MyMCP"
plugins:
  ckan:
    enabled: true
    base_url: "https://data.yourcity.gov"
    # ... other config
aws:
  region: "us-east-1"
  lambda_memory: 512
  lambda_timeout: 120
```

**Important:** Enable exactly ONE plugin.

### 3. Run Deployment Script

```bash
./scripts/deploy.sh
```

The script will:
1. Validate configuration (ensures ONE plugin enabled)
2. Package Lambda code
3. Initialize Terraform (if needed)
4. Deploy to AWS Lambda
5. Output Lambda URL

### 4. Verify Deployment

Check AWS Console:
- Lambda function exists
- Function URL is enabled
- CloudWatch Log Group created

Test Lambda URL:
```bash
curl -X POST https://your-lambda-url.lambda-url.us-east-1.on.aws \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"ping"}'
```

## Manual Terraform Deployment

If you prefer to use Terraform directly:

```bash
cd terraform
terraform init
terraform plan \
  -var="lambda_name=my-mcp-server" \
  -var="aws_region=us-east-1" \
  -var="config_file=../config.yaml"
terraform apply
```

## Updating Deployment

To update an existing deployment:

1. Make changes to code or config
2. Run `./scripts/deploy.sh` again
3. Terraform will update the Lambda function

## Environment Variables

Configuration is passed to Lambda via `OPENCONTEXT_CONFIG` environment variable (JSON).

To update config:
1. Edit `config.yaml`
2. Run `./scripts/deploy.sh` (Terraform updates environment variable)

## Lambda Configuration

### Memory

Default: 512 MB
Range: 128 MB - 10,240 MB

Adjust in `config.yaml`:
```yaml
aws:
  lambda_memory: 1024  # Increase for heavy workloads
```

### Timeout

Default: 120 seconds
Range: 1 - 900 seconds

Adjust in `config.yaml`:
```yaml
aws:
  lambda_timeout: 300  # Increase for slow APIs
```

### Runtime

Fixed: Python 3.11

## Function URL

Lambda Function URL is created automatically with:
- Authorization: NONE (public access)
- CORS: Enabled for all origins
- Methods: POST, OPTIONS

## Monitoring

### CloudWatch Logs

Logs are automatically sent to CloudWatch:
- Log Group: `/aws/lambda/<function-name>`
- Retention: 14 days
- Format: JSON structured logs

### View Logs

```bash
aws logs tail /aws/lambda/my-mcp-server --follow
```

Or in AWS Console:
1. Go to Lambda function
2. Click "Monitor" tab
3. Click "View CloudWatch logs"

## Troubleshooting

### Deployment Fails: "Multiple Plugins Enabled"

**Solution:** Enable only ONE plugin in `config.yaml`.

### Lambda Times Out

**Solutions:**
- Increase `lambda_timeout` in config
- Check if data source API is slow
- Review CloudWatch logs for errors

### Function URL Returns 500

**Check:**
1. CloudWatch logs for errors
2. Configuration is valid JSON
3. Plugin initialization succeeded

### High Lambda Costs

**Solutions:**
- Reduce `lambda_memory` if not needed
- Enable Lambda provisioned concurrency (if needed)
- Review CloudWatch metrics for usage patterns

## Cleanup

To delete deployment:

```bash
cd terraform
terraform destroy
```

This removes:
- Lambda function
- Function URL
- IAM role
- CloudWatch Log Group

## Cost Estimation

Typical costs (us-east-1):
- Lambda: $0.20 per 1M requests
- Lambda: $0.0000166667 per GB-second
- Function URL: Free
- CloudWatch Logs: $0.50 per GB ingested

Example: 100K requests/month, 512 MB, 1s average:
- Requests: ~$0.02
- Compute: ~$0.85
- Logs: ~$0.10
- **Total: ~$1/month**

## Security Considerations

- Function URLs are public (no authentication)
- Use API keys in plugin config for data source authentication
- Store secrets in environment variables (not in code)
- Review CloudWatch logs regularly
- Consider adding authentication layer if needed

## Best Practices

1. **Test locally** before deploying
2. **Monitor CloudWatch** logs after deployment
3. **Set appropriate timeouts** based on API response times
4. **Use environment variables** for secrets
5. **Version control** your config.yaml
6. **Document** your deployment process

## Next Steps

- [Quick Start Guide](QUICKSTART.md)
- [Architecture Guide](ARCHITECTURE.md)
- [Custom Plugins Guide](CUSTOM_PLUGINS.md)

