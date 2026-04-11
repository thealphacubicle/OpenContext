---
name: deploy-aws
description: >
  Invoked when deploying OpenContext to AWS, setting up Lambda infrastructure,
  provisioning a new environment, or running opencontext deploy. Use when the
  user says "deploy", "set up AWS", "push to Lambda", "provision staging/prod",
  or "connect Claude to my deployment".
command: /deploy-aws
---

# Deploy to AWS Workflow

## Prerequisites
- `config.yaml` exists with exactly one plugin enabled
- AWS credentials configured (`aws configure` or env vars)
- `uv sync --all-extras` already run

## Steps

### 1. Validate config
```bash
opencontext validate --env {env}
```
Checks config.yaml structure + Terraform syntax. Fix any errors before proceeding.

### 2. Security scan
```bash
opencontext security
```
Run pip-audit before every deploy. Fix any HIGH/CRITICAL findings first.

### 3. First-time setup only
```bash
opencontext configure
```
Interactive: creates `terraform/aws/{env}.tfvars`, initializes Terraform workspace `{city}-{env}`.
Workspace naming: `{city}-{env}` — e.g., `chicago-staging`, `boston-prod`.

### 4. Deploy
```bash
opencontext deploy --env {env}
```
This packages the Lambda ZIP (validates <250 MB), applies Terraform, outputs the API Gateway URL.

### 5. Verify deployment
```bash
opencontext status --env {env}
opencontext test --url {api_gateway_url}/mcp
```

### 6. Connect to Claude
Copy the API Gateway URL → Claude Desktop → Settings → Connectors → Add MCP Server.

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `ConfigurationError: 0 or 2+ plugins enabled` | config.yaml misconfigured | Check one-plugin rule |
| Lambda timeout on cold start | `lambda_timeout` too low | Increase in config.yaml (max 900s) |
| Package size exceeded | Dependencies too large | Run `opencontext validate` to check size |
| Terraform state conflict | Concurrent apply or stale lock | Check S3 backend, run `terraform force-unlock` |
| `initialize()` fails in production | `base_url` wrong or API down | `opencontext logs --env {env}` → check JSON logs |

## Debugging Production
```bash
opencontext logs --env {env}              # tail CloudWatch logs
opencontext status --env {env}            # deployment health
```
Set `logging.level: "DEBUG"` in `config.yaml` and redeploy for verbose output.
Logs are JSON-structured. CloudWatch Insights query:
```
fields @timestamp, level, message | sort @timestamp desc | limit 50
```
