---
name: debug-lambda
description: >
  Invoked when diagnosing issues with a deployed Lambda function, investigating
  CloudWatch errors, or troubleshooting MCP tool failures in a staging or production
  environment. Use when the user says "Lambda is failing", "MCP tools aren't working",
  "production errors", or "debug my deployment".
command: /debug-lambda
---

# Debug Lambda Workflow

## 1. Check deployment health
```bash
uv run opencontext status --env {env}
```
Confirms Lambda is deployed and reachable. If this fails, the issue is infrastructure — check Terraform state.

## 2. Tail logs
```bash
uv run opencontext logs --env {env}
```
Streams CloudWatch logs. Logs are JSON-structured. Key fields: `level`, `message`, `exc_info`.

CloudWatch Insights query for errors:
```
fields @timestamp, level, message, exc_info
| filter level = "ERROR"
| sort @timestamp desc
| limit 50
```

## 3. Enable verbose logging
In `config.yaml`:
```yaml
logging:
  level: "DEBUG"
```
Then redeploy: `opencontext deploy --env {env}`. This logs all request/response bodies (sensitive values are sanitized by `core/logging_utils.py`).

## 4. Common failure patterns

| Error | Cause | Fix |
|-------|-------|-----|
| `ConfigurationError: 0 or 2+ plugins` | Misconfigured `config.yaml` | Fix one-plugin rule, redeploy |
| `initialize() returned False` | `base_url` wrong or data API down | Check base_url in config; test API directly |
| `httpx.ConnectError` | Network or SSRF issue | Verify Lambda has internet access (VPC config) |
| `Task exceeded max timeout` | `lambda_timeout` too low | Increase in `config.yaml` (max 900s) |
| `Unzipped size must be smaller than...` | Lambda >250 MB | Run `opencontext validate --env {env}` |
| `ModuleNotFoundError` | Missing dep in Lambda package | Check `requirements.txt`, redeploy |

## 5. Test MCP tools directly
```bash
uv run opencontext test --url {api_gateway_url}/mcp
```
Runs the full MCP Inspector check: initialize → tools/list → tools/call for each tool.

## 6. Rollback if needed
```bash
# Re-deploy a previous known-good config
git stash  # or checkout previous config-example.yaml
uv run opencontext deploy --env {env}
```
