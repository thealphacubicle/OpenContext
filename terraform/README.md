# Terraform Infrastructure

This directory contains Terraform configuration for deploying OpenContext to AWS Lambda.

## Prerequisites

- Terraform >= 1.0
- AWS CLI configured with appropriate credentials
- Python 3.11+

## Usage

The deployment script (`../deploy.sh`) handles Terraform execution automatically. To run Terraform manually:

```bash
# Initialize Terraform
terraform init

# Plan deployment
terraform plan \
  -var="lambda_name=my-mcp-server" \
  -var="aws_region=us-east-1" \
  -var="config_file=../config.yaml"

# Apply changes
terraform apply \
  -var="lambda_name=my-mcp-server" \
  -var="aws_region=us-east-1" \
  -var="config_file=../config.yaml"
```

## Resources Created

- AWS Lambda function (Python 3.11)
- Lambda Function URL (public HTTP endpoint)
- IAM role and policies
- CloudWatch Log Group

## Outputs

- `lambda_url`: Lambda Function URL for accessing the MCP server
- `lambda_function_name`: Name of the Lambda function
- `lambda_function_arn`: ARN of the Lambda function
- `cloudwatch_log_group`: CloudWatch Log Group name

