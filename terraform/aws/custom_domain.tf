# Custom domain resources for the prod MCP server.
# Only created when var.custom_domain is non-empty (e.g. prod workspace with a custom domain).
# DNS records are managed externally by the domain owner — no Route53 resources here.

locals {
  create_custom_domain = var.custom_domain != "" ? 1 : 0
}

# ── ACM Certificate ──────────────────────────────────────────────────────────

resource "aws_acm_certificate" "mcp_cert" {
  count             = local.create_custom_domain
  domain_name       = var.custom_domain
  validation_method = "DNS"

  tags = {
    Name        = "${local.lambda_name}-cert"
    Environment = var.stage_name
  }

  lifecycle {
    create_before_destroy = true
  }
}

# ── API Gateway Custom Domain Name ──────────────────────────────────────────

resource "aws_api_gateway_domain_name" "custom" {
  count       = local.create_custom_domain
  domain_name = var.custom_domain

  regional_certificate_arn = aws_acm_certificate.mcp_cert[0].arn

  endpoint_configuration {
    types = ["REGIONAL"]
  }
}

# ── Base Path Mapping ───────────────────────────────────────────────────────
# Empty base path so custom-domain.example.com/mcp hits the existing /mcp resource.

resource "aws_api_gateway_base_path_mapping" "custom" {
  count       = local.create_custom_domain
  domain_name = aws_api_gateway_domain_name.custom[0].domain_name
  api_id      = aws_api_gateway_rest_api.mcp_api.id
  stage_name  = aws_api_gateway_stage.prod.stage_name
}
