from __future__ import annotations

import json
import subprocess

import typer
from rich.panel import Panel
from rich.table import Table

from cli.utils import (
    console,
    ensure_config_exists,
    ensure_terraform_init,
    friendly_exit,
    get_terraform_dir,
    load_tfvars,
    select_workspace,
)

EMAIL_TEMPLATE = """\
Hi,

We're setting up a custom domain for our OpenContext MCP server. Could you
please create the following DNS CNAME records?

1. Routing record (points {domain} to our API Gateway):
   Name:  {domain}
   Type:  CNAME
   Value: {regional_domain}

2. Certificate validation record (proves we own the domain):
   Name:  {validation_name}
   Type:  CNAME
   Value: {validation_value}

Once both records are live, the SSL certificate will be issued automatically
(usually within a few minutes). Let me know if you have any questions.

Thanks!
"""


def _get_terraform_outputs(terraform_dir, keys: list[str]) -> dict[str, str]:
    """Read specific outputs from terraform state."""
    result = subprocess.run(
        ["terraform", "output", "-json"],
        cwd=terraform_dir,
        capture_output=True,
        text=True,
        timeout=15,
    )
    outputs: dict[str, str] = {}
    if result.returncode == 0 and result.stdout.strip():
        raw = json.loads(result.stdout)
        for key in keys:
            val = raw.get(key, {})
            v = val.get("value") if isinstance(val, dict) else None
            if v is not None:
                outputs[key] = str(v)
    return outputs


def _get_apigw_domain(domain: str) -> dict | None:
    """Return the API Gateway custom domain info, or None if not found."""
    result = subprocess.run(
        ["aws", "apigatewayv2", "get-domain-name", "--domain-name", domain, "--output", "json"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    if result.returncode != 0:
        return None
    return json.loads(result.stdout)


def _get_cert_for_domain(domain: str) -> dict | None:
    """Find the ACM certificate matching the given domain."""
    result = subprocess.run(
        ["aws", "acm", "list-certificates", "--output", "json"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    if result.returncode != 0:
        return None
    certs = json.loads(result.stdout).get("CertificateSummaryList", [])
    for cert in certs:
        if cert.get("DomainName") == domain:
            return cert
    return None


@friendly_exit
def domain(
    env: str = typer.Option("staging", help="Environment: staging or prod"),
) -> None:
    """Check and manage custom domain setup."""
    ensure_config_exists()
    ensure_terraform_init()

    terraform_dir = get_terraform_dir()
    tfvars = load_tfvars(env)
    custom_domain = tfvars.get("custom_domain", "")
    if not custom_domain:
        console.print(
            "[red]No custom domain configured for this environment.[/red]\n"
            "Run [bold]opencontext configure[/bold] to set one up."
        )
        raise typer.Exit(1)

    select_workspace(env, terraform_dir)

    console.print(f"\n[bold]Domain Status: {custom_domain}[/bold]\n")

    # Read terraform outputs for domain info
    with console.status("Fetching domain info from Terraform..."):
        tf_out = _get_terraform_outputs(terraform_dir, [
            "custom_domain_target",
            "acm_certificate_arn",
            "acm_validation_cname_name",
            "acm_validation_cname_value",
        ])

    # Check certificate status via AWS CLI
    with console.status("Checking ACM certificate..."):
        cert = _get_cert_for_domain(custom_domain)

    if not cert:
        console.print(
            "[red]No ACM certificate found for this domain.[/red]\n"
            f"Run [bold]opencontext deploy --env {env}[/bold] to create one."
        )
        raise typer.Exit(1)

    cert_status = cert.get("Status", "UNKNOWN")

    if cert_status == "PENDING_VALIDATION":
        _handle_pending_validation(custom_domain, env, tf_out)
    elif cert_status == "ISSUED":
        _handle_issued(custom_domain, env, tf_out)
    else:
        console.print(f"Certificate status: [yellow]{cert_status}[/yellow]")
        console.print("Check the AWS Console for more details.")


def _handle_pending_validation(
    domain: str, env: str, tf_out: dict[str, str]
) -> None:
    console.print("[yellow]Certificate status: PENDING_VALIDATION[/yellow]\n")

    regional_domain = tf_out.get("custom_domain_target", "")
    validation_name = tf_out.get("acm_validation_cname_name", "")
    validation_value = tf_out.get("acm_validation_cname_value", "")

    if regional_domain and not regional_domain.startswith("d-"):
        console.print(
            f"[yellow]Warning:[/yellow] regionalDomainName is [bold]{regional_domain}[/bold] "
            "which doesn't start with 'd-'. Verify this is the correct API Gateway domain.\n"
        )

    cname_table = Table(title="DNS Records to Create", show_lines=True)
    cname_table.add_column("Purpose", style="bold")
    cname_table.add_column("Type")
    cname_table.add_column("Name")
    cname_table.add_column("Value")

    if regional_domain:
        cname_table.add_row("Routing", "CNAME", domain, regional_domain)

    if validation_name:
        cname_table.add_row(
            "Certificate Validation", "CNAME", validation_name, validation_value
        )

    console.print(cname_table)

    email = EMAIL_TEMPLATE.format(
        domain=domain,
        regional_domain=regional_domain or "<run deploy first to get this value>",
        validation_name=validation_name or "<not available>",
        validation_value=validation_value or "<not available>",
    )
    console.print()
    console.print(Panel(email, title="Email Template for City IT", border_style="blue"))


def _handle_issued(domain: str, env: str, tf_out: dict[str, str]) -> None:
    console.print("[green]Certificate status: ISSUED[/green]\n")

    regional_domain = tf_out.get("custom_domain_target", "")
    if not regional_domain:
        console.print(
            "[yellow]API Gateway custom domain not found.[/yellow]\n"
            f"Run [bold]opencontext deploy --env {env}[/bold] to create it."
        )
        return

    console.print(f"Regional domain: {regional_domain}")

    console.print(f"\nTesting connection to https://{domain}/ ...")
    try:
        result = subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", f"https://{domain}/"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        code = result.stdout.strip()
        if code and int(code) < 500:
            console.print(f"[green]Domain is live![/green] HTTP {code}")
        else:
            console.print(
                f"[yellow]Received HTTP {code}.[/yellow] "
                "The domain may not be fully configured yet."
            )
    except Exception:
        console.print(
            "[yellow]Could not reach the domain. DNS may still be propagating.[/yellow]"
        )
