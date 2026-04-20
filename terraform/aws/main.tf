terraform {
  required_version = ">= 1.0"

  backend "s3" {
    bucket  = "opencontext-terraform-state-govex-dc"
    key     = "opencontext/terraform.tfstate"
    region  = "us-east-1"
    encrypt = true
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# Read config.yaml
locals {
  config = yamldecode(file(var.config_file))

  lambda_name = var.lambda_name != "" ? var.lambda_name : (
    local.config.server_name != "" ? lower(replace(local.config.server_name, " ", "-")) : "opencontext-mcp-server"
  )

  lambda_memory  = local.config.aws.lambda_memory != null ? local.config.aws.lambda_memory : var.lambda_memory
  lambda_timeout = local.config.aws.lambda_timeout != null ? local.config.aws.lambda_timeout : var.lambda_timeout

  # Serialize config to JSON for environment variable
  config_json = jsonencode(local.config)

  common_tags = {
    Project     = "opencontext"
    Environment = var.stage_name
    ManagedBy   = "terraform"
  }
}

# IAM role for Lambda
resource "aws_iam_role" "lambda_role" {
  name = "${local.lambda_name}-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = local.common_tags
}

# Basic Lambda execution policy
resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# X-Ray tracing policy
resource "aws_iam_role_policy_attachment" "lambda_xray" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/AWSXRayDaemonWriteAccess"
}

# Lambda deployment package (created by `opencontext deploy`)
# `opencontext deploy` builds .deploy/ and lambda-deployment.zip, then copies the zip here.
locals {
  lambda_zip_path = "${path.module}/lambda-deployment.zip"
  lambda_zip_hash = filebase64sha256(local.lambda_zip_path)
}

# Lambda function
resource "aws_lambda_function" "mcp_server" {
  filename         = local.lambda_zip_path
  function_name    = local.lambda_name
  role             = aws_iam_role.lambda_role.arn
  handler          = "server.adapters.aws_lambda.lambda_handler"
  source_code_hash = local.lambda_zip_hash
  runtime          = "python3.11"
  memory_size      = local.lambda_memory
  timeout          = local.lambda_timeout

  environment {
    variables = {
      OPENCONTEXT_CONFIG = local.config_json
    }
  }

  tracing_config {
    mode = "Active"
  }

  dead_letter_config {
    target_arn = aws_sqs_queue.lambda_dlq.arn
  }

  tags = local.common_tags

  depends_on = [
    aws_iam_role_policy_attachment.lambda_basic,
    aws_iam_role_policy_attachment.lambda_xray,
    aws_iam_role_policy.lambda_dlq,
  ]
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "lambda_logs" {
  name              = "/aws/lambda/${local.lambda_name}"
  retention_in_days = 14
  tags              = local.common_tags
}

# Dead Letter Queue for failed async Lambda invocations
resource "aws_sqs_queue" "lambda_dlq" {
  name                      = "${local.lambda_name}-dlq"
  message_retention_seconds = 1209600 # 14 days — matches log retention
  sqs_managed_sse_enabled   = true
  tags                      = local.common_tags
}

# Allow Lambda to write failures to the DLQ
resource "aws_iam_role_policy" "lambda_dlq" {
  role = aws_iam_role.lambda_role.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["sqs:SendMessage"]
      Resource = aws_sqs_queue.lambda_dlq.arn
    }]
  })
}
