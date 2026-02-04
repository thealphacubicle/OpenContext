# API Gateway REST API
resource "aws_api_gateway_rest_api" "mcp_api" {
  name        = "${local.lambda_name}-api"
  description = "API Gateway for OpenContext MCP Server"

  endpoint_configuration {
    types = ["REGIONAL"]
  }
}

# API Gateway Resource: /mcp
resource "aws_api_gateway_resource" "mcp" {
  rest_api_id = aws_api_gateway_rest_api.mcp_api.id
  parent_id   = aws_api_gateway_rest_api.mcp_api.root_resource_id
  path_part   = "mcp"
}

# API Gateway Method: POST (requires API key)
resource "aws_api_gateway_method" "mcp_post" {
  rest_api_id      = aws_api_gateway_rest_api.mcp_api.id
  resource_id      = aws_api_gateway_resource.mcp.id
  http_method      = "POST"
  authorization    = "NONE"
  api_key_required = true
}

# API Gateway Method: OPTIONS (for CORS, no API key required)
resource "aws_api_gateway_method" "mcp_options" {
  rest_api_id      = aws_api_gateway_rest_api.mcp_api.id
  resource_id      = aws_api_gateway_resource.mcp.id
  http_method      = "OPTIONS"
  authorization    = "NONE"
  api_key_required = false
}

# Lambda Integration for POST
resource "aws_api_gateway_integration" "mcp_post_integration" {
  rest_api_id = aws_api_gateway_rest_api.mcp_api.id
  resource_id = aws_api_gateway_resource.mcp.id
  http_method = aws_api_gateway_method.mcp_post.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.mcp_server.invoke_arn
}

# Lambda Integration for OPTIONS (mock response for CORS)
resource "aws_api_gateway_integration" "mcp_options_integration" {
  rest_api_id = aws_api_gateway_rest_api.mcp_api.id
  resource_id = aws_api_gateway_resource.mcp.id
  http_method = aws_api_gateway_method.mcp_options.http_method

  type = "MOCK"

  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

# Method Response for POST
resource "aws_api_gateway_method_response" "mcp_post_response_200" {
  rest_api_id = aws_api_gateway_rest_api.mcp_api.id
  resource_id = aws_api_gateway_resource.mcp.id
  http_method = aws_api_gateway_method.mcp_post.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Origin"  = true
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
  }
}

# Method Response for OPTIONS
resource "aws_api_gateway_method_response" "mcp_options_response_200" {
  rest_api_id = aws_api_gateway_rest_api.mcp_api.id
  resource_id = aws_api_gateway_resource.mcp.id
  http_method = aws_api_gateway_method.mcp_options.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Origin"  = true
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
  }
}

# Integration Response for POST
# NOTE: This is redundant because AWS_PROXY integration type bypasses integration responses.
# All headers must be returned by Lambda function, which our handler already does.
# Keeping commented for reference but not used.
# resource "aws_api_gateway_integration_response" "mcp_post_integration_response" {
#   rest_api_id = aws_api_gateway_rest_api.mcp_api.id
#   resource_id = aws_api_gateway_resource.mcp.id
#   http_method = aws_api_gateway_method.mcp_post.http_method
#   status_code = aws_api_gateway_method_response.mcp_post_response_200.status_code
#
#   response_parameters = {
#     "method.response.header.Access-Control-Allow-Origin"  = "'*'"
#     "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Api-Key'"
#     "method.response.header.Access-Control-Allow-Methods" = "'OPTIONS,POST'"
#   }
#
#   depends_on = [aws_api_gateway_integration.mcp_post_integration]
# }

# Integration Response for OPTIONS
resource "aws_api_gateway_integration_response" "mcp_options_integration_response" {
  rest_api_id = aws_api_gateway_rest_api.mcp_api.id
  resource_id = aws_api_gateway_resource.mcp.id
  http_method = aws_api_gateway_method.mcp_options.http_method
  status_code = aws_api_gateway_method_response.mcp_options_response_200.status_code

  response_parameters = {
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Api-Key'"
    "method.response.header.Access-Control-Allow-Methods" = "'OPTIONS,POST'"
  }

  response_templates = {
    "application/json" = ""
  }

  depends_on = [aws_api_gateway_integration.mcp_options_integration]
}

# Lambda Permission for API Gateway
resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.mcp_server.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.mcp_api.execution_arn}/*/*"
}

# CloudWatch Log Group for API Gateway
resource "aws_cloudwatch_log_group" "api_gateway_logs" {
  name              = "/aws/apigateway/${local.lambda_name}"
  retention_in_days = 14
}

# API Gateway Deployment
resource "aws_api_gateway_deployment" "mcp_deployment" {
  rest_api_id = aws_api_gateway_rest_api.mcp_api.id

  triggers = {
    redeployment = sha1(jsonencode([
      aws_api_gateway_resource.mcp.id,
      aws_api_gateway_method.mcp_post.id,
      aws_api_gateway_method.mcp_options.id,
      aws_api_gateway_integration.mcp_post_integration.id,
      aws_api_gateway_integration.mcp_options_integration.id,
    ]))
  }

  lifecycle {
    create_before_destroy = true
  }

  depends_on = [
    aws_api_gateway_method.mcp_post,
    aws_api_gateway_method.mcp_options,
    aws_api_gateway_integration.mcp_post_integration,
    aws_api_gateway_integration.mcp_options_integration,
    aws_api_gateway_method_response.mcp_post_response_200,
    aws_api_gateway_method_response.mcp_options_response_200,
    # aws_api_gateway_integration_response.mcp_post_integration_response,  # Removed - AWS_PROXY ignores it
    aws_api_gateway_integration_response.mcp_options_integration_response,
  ]
}

# API Gateway Stage
resource "aws_api_gateway_stage" "prod" {
  deployment_id = aws_api_gateway_deployment.mcp_deployment.id
  rest_api_id   = aws_api_gateway_rest_api.mcp_api.id
  stage_name    = "prod"

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_gateway_logs.arn
    format = jsonencode({
      requestId      = "$context.requestId"
      ip             = "$context.identity.sourceIp"
      httpMethod     = "$context.httpMethod"
      status         = "$context.status"
      responseLength = "$context.responseLength"
    })
  }

  xray_tracing_enabled = true
}

# API Key
resource "aws_api_gateway_api_key" "hult_hackathon_2024" {
  name = "hult-hackathon-2024"
}

# Usage Plan
resource "aws_api_gateway_usage_plan" "mcp_usage_plan" {
  name = "${local.lambda_name}-usage-plan"

  api_stages {
    api_id = aws_api_gateway_rest_api.mcp_api.id
    stage  = aws_api_gateway_stage.prod.stage_name
  }

  quota_settings {
    limit  = 1000
    period = "DAY"
  }

  throttle_settings {
    burst_limit = 10
    rate_limit  = 5
  }
}

# Usage Plan Key Association
resource "aws_api_gateway_usage_plan_key" "mcp_usage_plan_key" {
  key_id        = aws_api_gateway_api_key.hult_hackathon_2024.id
  key_type      = "API_KEY"
  usage_plan_id = aws_api_gateway_usage_plan.mcp_usage_plan.id
}
