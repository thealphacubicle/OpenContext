# Phase 2: Google Cloud API Gateway + custom domain

The v1 Terraform stack deploys **Cloud Functions (gen2)** with a public HTTPS URL and `POST /mcp` on that host. That matches the single HTTPS endpoint model without a separate edge product.

When you need closer parity with **AWS API Gateway** (OpenAPI-first routing, API keys, quotas, or a stable custom domain in front of managed TLS), add **[Google Cloud API Gateway](https://cloud.google.com/api-gateway/docs)** in a follow-up change.

## Why it is not in v1

- API Gateway is driven by an **OpenAPI 3** document that references your backend URL (the Cloud Run service behind gen2). The backend URL changes when you recreate the function unless you fix it with a stable hostname or separate Cloud Run service name.
- Terraform for API Gateway typically involves `google_api_gateway_api`, configs, gateways, and DNS verification for custom domains — more moving parts than the AWS REST API Gateway resources in `terraform/aws/`.

## Suggested approach

1. Deploy v1 and capture the function URL from `terraform output mcp_endpoint_url` (or `function_uri`).
2. Author an OpenAPI spec with a path `/mcp` forwarding to the Cloud Run or function backend (Google documents `x-google-backend` / backend address for your deployment type).
3. Add Terraform resources for the API config and gateway; map a **custom domain** using Google's API Gateway custom domain flow (DNS validation + managed certificate as documented for the product).
4. Optionally tighten **Cloud Functions / Cloud Run** ingress to **internal + load balancer** only if you want all traffic to flow through API Gateway.

## Related GCP docs

- [API Gateway overview](https://cloud.google.com/api-gateway/docs/about-api-gateway)
- [Cloud Functions gen2](https://cloud.google.com/functions/docs/2nd-gen/overview) (runs on Cloud Run)
