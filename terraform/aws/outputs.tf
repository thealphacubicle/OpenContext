output "lambda_url" {
  description = "Lambda Function URL for MCP server (for local testing)"
  value       = aws_lambda_function_url.mcp_server_url.function_url
}

output "lambda_function_name" {
  description = "Name of the Lambda function"
  value       = aws_lambda_function.mcp_server.function_name
}

output "lambda_function_arn" {
  description = "ARN of the Lambda function"
  value       = aws_lambda_function.mcp_server.arn
}

output "cloudwatch_log_group" {
  description = "CloudWatch Log Group name"
  value       = aws_cloudwatch_log_group.lambda_logs.name
}

output "api_gateway_url" {
  description = "API Gateway URL for MCP server (production endpoint with authentication)"
  value       = "${aws_api_gateway_stage.prod.invoke_url}/mcp"
}

output "api_key_value" {
  description = "API Gateway API key value (sensitive)"
  value       = aws_api_gateway_api_key.hult_hackathon_2024.value
  sensitive   = true
}

output "api_key_id" {
  description = "API Gateway API key ID"
  value       = aws_api_gateway_api_key.hult_hackathon_2024.id
}

