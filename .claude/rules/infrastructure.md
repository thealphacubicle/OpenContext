---
description: Terraform and AWS infrastructure conventions for terraform/ files
globs: ["terraform/**/*.tf"]
alwaysApply: false
---

# Infrastructure Conventions

## State Backend
S3 backend: `opencontext-terraform-state` bucket, server-side encrypted. Never use local state.

## Workspace Naming
Format: `{city}-{env}` — e.g., `chicago-staging`, `boston-prod`.
Workspaces are created by `opencontext configure`. Never create them manually with `terraform workspace new`.

## Variables
Per-environment values live in `terraform/aws/{env}.tfvars` (gitignored). Use `*.tfvars.example` as the committed template. Never put real secrets in committed files.

## Lambda Config
Lambda reads all runtime config via the `OPENCONTEXT_CONFIG` environment variable (JSON blob set by Terraform from `config.yaml`). Do not hardcode config values in `.tf` files — put them in `.tfvars`.

## Editing Rules
- Never edit `terraform/aws/main.tf` directly for per-deployment tuning — use `.tfvars` overrides
- Run `terraform fmt -check -recursive && terraform validate` before any PR (matches `infra.yml` CI)
- Lambda package size limit: 250 MB. `opencontext deploy` validates this; check with `opencontext validate --env {env}` before adding large deps

## Validation Order
```bash
opencontext validate --env {env}    # config.yaml structure + Terraform syntax check
terraform fmt -check -recursive     # formatting (CI gate)
terraform validate                  # provider/resource correctness
```
