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

Lambda Function URL is created automatically for local testing:
- Authorization: NONE (public access - no authentication)
- CORS: Enabled for all origins
- Methods: POST, OPTIONS

**Note:** For production use, prefer the API Gateway endpoint with API key authentication (see "API Gateway Authentication" section below).

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

## API Gateway Authentication

OpenContext deploys with both a Lambda Function URL (for local testing) and an API Gateway endpoint (for production with authentication).

### Retrieving API Key

After deployment, get your API key:

```bash
cd terraform
terraform output -raw api_key_value
```

Get your API Gateway URL:

```bash
terraform output -raw api_gateway_url
```

### Testing API Gateway

Test with a valid API key:

```bash
curl -X POST https://your-api-gateway-url.execute-api.us-east-1.amazonaws.com/prod/mcp \
  -H "x-api-key: your-api-key-here" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"ping"}'
```

Test without API key (should return 403):

```bash
curl -X POST https://your-api-gateway-url.execute-api.us-east-1.amazonaws.com/prod/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"ping"}'
```

Expected response: `{"message": "Forbidden"}` with status 403.

### Creating Additional API Keys

To create additional API keys via AWS CLI:

```bash
# Create new API key
API_KEY_ID=$(aws apigateway create-api-key \
  --name "my-api-key" \
  --enabled \
  --query 'id' \
  --output text)

# Get the API key value (only shown once)
aws apigateway get-api-key \
  --api-key $API_KEY_ID \
  --include-value \
  --query 'value' \
  --output text

# Associate with usage plan
USAGE_PLAN_ID=$(aws apigateway get-usage-plans \
  --query "items[?name=='your-lambda-name-usage-plan'].id" \
  --output text)

aws apigateway create-usage-plan-key \
  --usage-plan-id $USAGE_PLAN_ID \
  --key-type API_KEY \
  --key-id $API_KEY_ID
```

### Rate Limiting

API Gateway enforces:
- **Quota**: 1000 requests per day per API key
- **Throttle**: 10 burst requests, 5 sustained requests per second

When rate limits are exceeded, API Gateway returns `429 Too Many Requests`.

### Rollback Procedure

If API Gateway has issues, you can temporarily use the Lambda Function URL directly:

1. Get Lambda Function URL:
   ```bash
   terraform output -raw lambda_url
   ```

2. Update your client configuration to use the Lambda URL instead of API Gateway URL

3. Note: Lambda Function URL has no authentication or rate limiting - use only for testing

## Security Considerations

- **API Gateway** - Production endpoint with API key authentication and rate limiting
- **Lambda Function URL** - Public endpoint (no authentication) - use only for local testing
- Use API keys in plugin config for data source authentication
- Store secrets in environment variables (not in code)
- Review CloudWatch logs regularly
- Rotate API keys periodically

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

