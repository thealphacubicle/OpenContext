variable "lambda_name" {
  description = "Name of the Lambda function"
  type        = string
  default     = "opencontext-mcp-server"
}

variable "aws_region" {
  description = "AWS region for deployment"
  type        = string
  default     = "us-east-1"
}

variable "config_file" {
  description = "Path to config.yaml file"
  type        = string
  default     = "../config.yaml"
}

variable "lambda_memory" {
  description = "Lambda memory in MB"
  type        = number
  default     = 512
}

variable "lambda_timeout" {
  description = "Lambda timeout in seconds"
  type        = number
  default     = 120
}

