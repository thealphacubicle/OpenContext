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
) -> None:
    """Show deployment status for the given environment."""
    ensure_config_exists()
    ensure_terraform_init()

    terraform_dir = get_terraform_dir()
    tfvars = load_tfvars(env)
    lambda_name = tfvars.get("lambda_name", "")
    custom_domain = tfvars.get("custom_domain", "")

    select_workspace(env, terraform_dir)

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

    # Gather Lambda info
    lambda_info: dict[str, str] = {}
    if lambda_name:
        with console.status("Fetching Lambda function info..."):
            result = subprocess.run(
                [
                    "aws", "lambda", "get-function",
                    "--function-name", lambda_name,
                    "--output", "json",
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
    if custom_domain:
        with console.status("Checking certificate status..."):
            cert_status = _get_cert_status(custom_domain)

    # Build table
    table = Table(title=f"OpenContext Status — {env}", show_lines=True)
    table.add_column("Property", style="bold")
    table.add_column("Value")

    ws = workspace_name(env)
    table.add_row("Environment", env)
    table.add_row("Workspace", ws)
    table.add_row("Lambda name", lambda_name or "N/A")

    if lambda_info:
        table.add_row("Last modified", lambda_info.get("last_modified", "N/A"))
        table.add_row("Runtime", lambda_info.get("runtime", "N/A"))

    table.add_row(
        "API Gateway URL",
        str(tf_outputs.get("api_gateway_url") or "N/A"),
    )

    if custom_domain:
        table.add_row("Custom domain", custom_domain)
        table.add_row("Certificate status", cert_status or "Not found")
        regional = tf_outputs.get("custom_domain_target")
        if regional:
            table.add_row("Regional domain", str(regional))
    else:
        table.add_row("Custom domain", "Not configured")

    table.add_row(
        "CloudWatch log group",
        str(tf_outputs.get("cloudwatch_log_group") or f"/aws/lambda/{lambda_name}"),
    )

    console.print()
    console.print(table)
    console.print()
