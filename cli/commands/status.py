from __future__ import annotations

import json
import subprocess

import typer
from rich.table import Table

from cli.utils import (
    console,
    ensure_config_exists,
    ensure_terraform_init,
    friendly_exit,
    get_terraform_dir,
    load_tfvars,
    normalize_cloud,
    select_workspace,
    workspace_name,
)


def _get_cert_status(domain: str) -> str:
    """Get the ACM certificate status for a domain via AWS CLI."""
    result = subprocess.run(
        ["aws", "acm", "list-certificates", "--output", "json"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    if result.returncode == 0:
        certs = json.loads(result.stdout).get("CertificateSummaryList", [])
        for cert in certs:
            if cert.get("DomainName") == domain:
                return cert.get("Status", "UNKNOWN")
    return ""


@friendly_exit
def status(
    env: str = typer.Option("staging", help="Environment: staging or prod"),
    cloud: str = typer.Option("aws", "--cloud", help="Cloud provider: aws or gcp"),
) -> None:
    """Show deployment status for the given environment."""
    if not isinstance(cloud, str):
        cloud = "aws"
    cloud = normalize_cloud(cloud)
    ensure_config_exists()
    ensure_terraform_init(cloud)

    terraform_dir = get_terraform_dir(cloud)
    tfvars = load_tfvars(env, cloud=cloud)
    lambda_name = tfvars.get("lambda_name", "")
    function_name = tfvars.get("function_name", "")
    custom_domain = tfvars.get("custom_domain", "")

    select_workspace(env, terraform_dir, cloud=cloud)

    # Gather terraform outputs
    tf_outputs: dict[str, str | None] = {}
    with console.status("Fetching Terraform outputs..."):
        result = subprocess.run(
            ["terraform", "output", "-json"],
            cwd=terraform_dir,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0 and result.stdout.strip():
            raw = json.loads(result.stdout)
            for key, val in raw.items():
                tf_outputs[key] = val.get("value")

    # Gather Lambda / Function info
    lambda_info: dict[str, str] = {}
    if cloud == "aws" and lambda_name:
        with console.status("Fetching Lambda function info..."):
            result = subprocess.run(
                [
                    "aws",
                    "lambda",
                    "get-function",
                    "--function-name",
                    lambda_name,
                    "--output",
                    "json",
                ],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                config = data.get("Configuration", {})
                lambda_info["last_modified"] = config.get("LastModified", "N/A")
                lambda_info["runtime"] = config.get("Runtime", "N/A")

    # Gather cert status via AWS CLI if custom domain is set
    cert_status = ""
    if cloud == "aws" and custom_domain:
        with console.status("Checking certificate status..."):
            cert_status = _get_cert_status(custom_domain)

    # Build table
    table = Table(title=f"OpenContext Status — {env}", show_lines=True)
    table.add_column("Property", style="bold")
    table.add_column("Value")

    ws = workspace_name(env)
    table.add_row("Environment", env)
    table.add_row("Workspace", ws)
    table.add_row("Cloud", cloud)
    if cloud == "aws":
        table.add_row("Lambda name", lambda_name or "N/A")
    else:
        table.add_row(
            "Function name",
            function_name or str(tf_outputs.get("function_name") or "N/A"),
        )

    if lambda_info:
        table.add_row("Last modified", lambda_info.get("last_modified", "N/A"))
        table.add_row("Runtime", lambda_info.get("runtime", "N/A"))

    if cloud == "aws":
        table.add_row(
            "API Gateway URL",
            str(tf_outputs.get("api_gateway_url") or "N/A"),
        )
    else:
        table.add_row("Function URL", str(tf_outputs.get("function_uri") or "N/A"))
        table.add_row(
            "MCP Endpoint URL", str(tf_outputs.get("mcp_endpoint_url") or "N/A")
        )

    if cloud == "aws" and custom_domain:
        table.add_row("Custom domain", custom_domain)
        table.add_row("Certificate status", cert_status or "Not found")
        regional = tf_outputs.get("custom_domain_target")
        if regional:
            table.add_row("Regional domain", str(regional))
    elif cloud == "aws":
        table.add_row("Custom domain", "Not configured")

    if cloud == "aws":
        table.add_row(
            "CloudWatch log group",
            str(tf_outputs.get("cloudwatch_log_group") or f"/aws/lambda/{lambda_name}"),
        )
    else:
        table.add_row("Artifact bucket", str(tf_outputs.get("source_bucket") or "N/A"))

    console.print()
    console.print(table)
    console.print()
