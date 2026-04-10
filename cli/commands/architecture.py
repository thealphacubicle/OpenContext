"""Architecture command for OpenContext CLI.

Prints a human-readable overview of the AWS infrastructure that OpenContext
deploys and how the services are wired together.
"""

from __future__ import annotations

from rich.panel import Panel
from rich.text import Text

from cli.utils import console


def architecture() -> None:
    """Show the AWS architecture and how services are wired together."""
    console.print()

    # -------------------------------------------------------------------------
    # Request flow
    # -------------------------------------------------------------------------
    flow_text = Text.assemble(
        ("Client", "bold"),
        " (Claude, MCP Inspector, curl)\n",
        ("    │\n", "dim"),
        ("    │  POST /mcp  (JSON-RPC over HTTPS)\n", "dim"),
        ("    ▼\n", "dim"),
        ("API Gateway", "bold cyan"),
        " — REST API, Regional endpoint\n",
        ("    │\n", "dim"),
        ("    │  AWS_PROXY integration (event passthrough)\n", "dim"),
        ("    ▼\n", "dim"),
        ("Lambda", "bold cyan"),
        " — ", ("server.adapters.aws_lambda.lambda_handler", "italic"), "\n",
        ("    │\n", "dim"),
        ("    │  failures (async invocations only)\n", "dim"),
        ("    ▼\n", "dim"),
        ("SQS Dead Letter Queue", "bold cyan"),
        " — captures failed invocations for inspection\n\n",
        ("Logs & traces flow separately:\n", "bold"),
        ("  Lambda  →  CloudWatch Logs   ", "dim"), "/aws/lambda/<function-name>\n",
        ("  Lambda  →  X-Ray             ", "dim"), "active tracing on all invocations\n",
        ("  API GW  →  X-Ray             ", "dim"), "stage-level tracing enabled",
    )
    console.print(
        Panel(flow_text, title="[bold]Request Flow[/bold]", border_style="cyan")
    )
    console.print()

    # -------------------------------------------------------------------------
    # API Gateway
    # -------------------------------------------------------------------------
    apigw_text = Text.assemble(
        ("Type:      ", "bold"), "REST API  (Regional endpoint)\n",
        ("Resource:  ", "bold"), "POST /mcp  +  OPTIONS /mcp (CORS preflight)\n",
        ("CORS:      ", "bold"), "OPTIONS returns mock 200 with Access-Control-Allow-* headers\n",
        ("Auth:      ", "bold"), "None — open endpoint, protected by throttling + usage plan\n\n",
        ("Throttling  (per-stage):\n", "bold"),
        ("  Burst limit   ", "dim"), "10 requests\n",
        ("  Rate limit    ", "dim"), "5 requests/second\n\n",
        ("Usage Plan  (per-day quota):\n", "bold"),
        ("  Configurable via ", "dim"),
        ("api_quota_limit", "italic"),
        (" / ", "dim"),
        ("api_burst_limit", "italic"),
        (" / ", "dim"),
        ("api_rate_limit", "italic"),
        (" Terraform variables", "dim"),
    )
    console.print(
        Panel(apigw_text, title="[bold]API Gateway[/bold]", border_style="blue")
    )
    console.print()

    # -------------------------------------------------------------------------
    # Lambda
    # -------------------------------------------------------------------------
    lambda_text = Text.assemble(
        ("Runtime:   ", "bold"), "Python 3.11\n",
        ("Handler:   ", "bold"), "server.adapters.aws_lambda.lambda_handler\n",
        ("Config:    ", "bold"),
        "config.yaml is JSON-encoded and injected as the ",
        ("OPENCONTEXT_CONFIG", "italic"),
        " environment variable at deploy time\n",
        ("Tracing:   ", "bold"), "X-Ray Active mode — all invocations traced\n",
        ("DLQ:       ", "bold"), "Failed async invocations written to SQS Dead Letter Queue\n",
        ("Sizing:    ", "bold"),
        "Memory and timeout set from config.yaml  (", ("aws.lambda_memory", "italic"),
        " / ", ("aws.lambda_timeout", "italic"), ")\n\n",
        ("IAM Role permissions:\n", "bold"),
        ("  AWSLambdaBasicExecutionRole  ", "dim"), "CloudWatch Logs write access\n",
        ("  AWSXRayDaemonWriteAccess     ", "dim"), "X-Ray segment submission\n",
        ("  Inline policy               ", "dim"), "sqs:SendMessage to the DLQ",
    )
    console.print(
        Panel(lambda_text, title="[bold]Lambda[/bold]", border_style="green")
    )
    console.print()

    # -------------------------------------------------------------------------
    # Supporting services
    # -------------------------------------------------------------------------
    supporting_text = Text.assemble(
        ("CloudWatch Logs\n", "bold underline"),
        ("  Log group:  ", "dim"), "/aws/lambda/<function-name>\n",
        ("  Retention:  ", "dim"), "14 days\n\n",
        ("SQS Dead Letter Queue\n", "bold underline"),
        ("  Name:       ", "dim"), "<function-name>-dlq\n",
        ("  Retention:  ", "dim"), "14 days  (matches log retention)\n",
        ("  Encryption: ", "dim"), "SQS-managed SSE\n",
        ("  Purpose:    ", "dim"),
        "Captures Lambda failures from async invocations so they can be\n",
        ("               ", "dim"),
        "inspected or replayed without losing the original request\n\n",
        ("Terraform State (S3 backend)\n", "bold underline"),
        ("  Bucket:     ", "dim"), "opencontext-terraform-state\n",
        ("  Key:        ", "dim"), "opencontext/terraform.tfstate\n",
        ("  Encryption: ", "dim"), "SSE enabled\n",
        ("  Workspaces: ", "dim"), "<city>-staging  /  <city>-prod",
    )
    console.print(
        Panel(
            supporting_text,
            title="[bold]CloudWatch · SQS · Terraform State[/bold]",
            border_style="yellow",
        )
    )
    console.print()

    # -------------------------------------------------------------------------
    # Custom domain (optional)
    # -------------------------------------------------------------------------
    domain_text = Text.assemble(
        "Custom domain resources are only created when ",
        ("custom_domain", "italic"),
        " is set in the Terraform variables (", ("configure[/italic]", "dim"),
        " wizard sets this).\n\n",
        ("ACM Certificate\n", "bold underline"),
        ("  Validation:  ", "dim"), "DNS (city IT creates a CNAME record)\n",
        ("  Lifecycle:   ", "dim"), "create_before_destroy — zero downtime on cert rotation\n\n",
        ("API Gateway Custom Domain\n", "bold underline"),
        ("  Type:        ", "dim"), "Regional endpoint\n",
        ("  Mapping:     ", "dim"),
        "Empty base path → existing /mcp resource (no URL change for callers)\n",
        ("  CNAME:       ", "dim"),
        "City IT points their domain at the API Gateway regional domain name\n\n",
        ("Inspect domain status:  ", "dim"),
        ("opencontext domain --env prod", "bold"),
    )
    console.print(
        Panel(
            domain_text,
            title="[bold]Custom Domain (optional)[/bold]",
            border_style="magenta",
        )
    )
    console.print()

    # -------------------------------------------------------------------------
    # Resource tagging
    # -------------------------------------------------------------------------
    tags_text = Text.assemble(
        "All resources are tagged for cost allocation and filtering:\n\n",
        ("  Project      ", "bold cyan"), "opencontext\n",
        ("  Environment  ", "bold cyan"), "staging  or  prod\n",
        ("  ManagedBy    ", "bold cyan"), "terraform\n\n",
        ("[dim]To see costs broken down by these tags, activate them in AWS Console →\n"
         "Billing → Cost allocation tags, then use Cost Explorer.[/dim]"),
    )
    console.print(
        Panel(tags_text, title="[bold]Resource Tagging[/bold]", border_style="dim")
    )
    console.print()
