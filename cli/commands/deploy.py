from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from zipfile import ZipFile

import questionary
import typer
from rich.table import Table

from cli.commands.validate import run_checks as _run_validate_checks
from cli.utils import (
    console,
    ensure_config_exists,
    ensure_terraform_init,
    friendly_exit,
    get_project_root,
    get_terraform_dir,
    load_config,
    load_tfvars,
    require_tty,
    run_cmd,
    run_cmd_stream,
    run_cmd_stream_capture,
    select_workspace,
)


def _validate_single_plugin(config: dict) -> str:
    """Ensure exactly one plugin is enabled. Returns the plugin name."""
    plugins = config.get("plugins", {})
    enabled = [
        name
        for name, cfg in plugins.items()
        if isinstance(cfg, dict) and cfg.get("enabled", False)
    ]
    if len(enabled) == 0:
        console.print(
            "[red]No plugins enabled in config.yaml.[/red]\n"
            "Enable exactly ONE plugin, then try again."
        )
        raise typer.Exit(1)
    if len(enabled) > 1:
        console.print(
            f"[red]Multiple plugins enabled: {', '.join(enabled)}[/red]\n"
            "OpenContext enforces: One Fork = One MCP Server.\n"
            "Disable all but one plugin in config.yaml."
        )
        raise typer.Exit(1)
    return enabled[0]


def _package_lambda(project_root: Path) -> Path:
    """Build .deploy/ directory and create lambda-deployment.zip."""
    deploy_dir = project_root / ".deploy"

    if deploy_dir.exists():
        shutil.rmtree(deploy_dir)
    deploy_dir.mkdir()

    # Install dependencies
    req_file = project_root / "requirements.txt"
    if req_file.exists():
        run_cmd(
            [
                "uv", "pip", "install",
                "-r", str(req_file),
                "--target", str(deploy_dir),
                "--python-platform", "x86_64-manylinux2014",
                "--python-version", "3.11",
                "--no-compile",
            ],
            cwd=project_root,
            spinner_msg="Installing dependencies into .deploy/",
        )

    # Copy source directories
    for src_dir in ["core", "plugins", "server"]:
        src = project_root / src_dir
        dst = deploy_dir / src_dir
        if src.exists():
            shutil.copytree(src, dst, dirs_exist_ok=True)

    custom_plugins = project_root / "custom_plugins"
    custom_dst = deploy_dir / "custom_plugins"
    if custom_plugins.exists():
        shutil.copytree(custom_plugins, custom_dst, dirs_exist_ok=True)
    else:
        custom_dst.mkdir(exist_ok=True)

    # Create zip
    zip_path = project_root / "lambda-deployment.zip"
    with ZipFile(zip_path, "w") as zf:
        for root, _dirs, files in os.walk(deploy_dir):
            for file in files:
                file_path = Path(root) / file
                arcname = file_path.relative_to(deploy_dir)
                zf.write(file_path, arcname)

    return zip_path


def _parse_plan_summary(output: str) -> tuple[int, int, int]:
    """Extract add/change/destroy counts from terraform plan output."""
    match = re.search(
        r"(\d+) to add, (\d+) to change, (\d+) to destroy", output
    )
    if match:
        return int(match.group(1)), int(match.group(2)), int(match.group(3))
    return 0, 0, 0


@friendly_exit
def deploy(
    env: str = typer.Option("staging", help="Environment: staging or prod"),
) -> None:
    """Package and deploy the MCP server to AWS Lambda."""
    require_tty()

    # Validate configuration before doing any work
    console.print("\n[bold]Validating configuration before deploy...[/bold]")
    if not _run_validate_checks(env):
        console.print(
            "\n[red bold]Validation failed.[/red bold] "
            "Fix the issues above before redeploying."
        )
        raise typer.Exit(1)

    project_root = get_project_root()
    terraform_dir = get_terraform_dir()

    ensure_config_exists()
    ensure_terraform_init()

    config = load_config()
    plugin_name = _validate_single_plugin(config)
    console.print(f"[green]Plugin:[/green] {plugin_name}")

    # Package
    console.print("\n[bold]Packaging Lambda deployment...[/bold]")
    zip_path = _package_lambda(project_root)
    console.print(f"[green]Created:[/green] {zip_path.name}")

    # Copy artifacts to terraform directory
    shutil.copy2(zip_path, terraform_dir / "lambda-deployment.zip")
    shutil.copy2(project_root / "config.yaml", terraform_dir / "config.yaml")

    # Select workspace
    select_workspace(env, terraform_dir)

    # Terraform plan
    tfvars_file = terraform_dir / f"{env}.tfvars"
    if not tfvars_file.exists():
        console.print(
            f"[red]{env}.tfvars not found.[/red]\n"
            "Run [bold]opencontext configure[/bold] to generate it."
        )
        raise typer.Exit(1)

    console.print("\n[bold]Planning Terraform changes...[/bold]\n")
    plan_exit_code, plan_output = run_cmd_stream_capture(
        [
            "terraform", "plan",
            f"-var-file={env}.tfvars",
            "-out=tfplan",
            "-input=false",
        ],
        cwd=terraform_dir,
    )
    if plan_exit_code != 0:
        console.print("[red]Terraform plan failed.[/red]")
        raise typer.Exit(1)

    add, change, destroy = _parse_plan_summary(plan_output)
    plan_table = Table(title="Planned Changes")
    plan_table.add_column("Action", style="bold")
    plan_table.add_column("Count", justify="right")
    plan_table.add_row("[green]Add[/green]", str(add))
    plan_table.add_row("[yellow]Change[/yellow]", str(change))
    plan_table.add_row("[red]Destroy[/red]", str(destroy))
    console.print()
    console.print(plan_table)
    console.print()

    # Mandatory confirmation
    proceed = questionary.confirm(
        "Proceed with deployment?", default=False
    ).ask()
    if not proceed:
        tfplan = terraform_dir / "tfplan"
        if tfplan.exists():
            tfplan.unlink()
        console.print("[yellow]Deployment cancelled.[/yellow]")
        raise typer.Exit(0)

    # Terraform apply
    console.print("\n[bold]Applying Terraform changes...[/bold]\n")
    exit_code = run_cmd_stream(
        ["terraform", "apply", "-input=false", "tfplan"],
        cwd=terraform_dir,
    )
    if exit_code != 0:
        console.print("[red]Terraform apply failed.[/red]")
        raise typer.Exit(1)

    # Clean up plan file
    tfplan = terraform_dir / "tfplan"
    if tfplan.exists():
        tfplan.unlink()

    # Retrieve all outputs at once
    console.print("\n[bold]Deployment Outputs[/bold]")

    outputs: dict[str, str | None] = {}
    with console.status("Fetching Terraform outputs..."):
        result = subprocess.run(
            ["terraform", "output", "-json"],
            cwd=terraform_dir,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            raw = json.loads(result.stdout)
            for key, val in raw.items():
                outputs[key] = val.get("value")

    output_table = Table(show_lines=True)
    output_table.add_column("Resource", style="bold")
    output_table.add_column("Value")

    api_gw = outputs.get("api_gateway_url")
    log_group = outputs.get("cloudwatch_log_group")

    if api_gw:
        output_table.add_row("API Gateway URL", str(api_gw))
    if log_group:
        output_table.add_row("CloudWatch Log Group", str(log_group))

    # Custom domain outputs (populated when custom_domain != "")
    tfvars = load_tfvars(env)
    custom_domain = tfvars.get("custom_domain", "")
    if custom_domain:
        regional = outputs.get("custom_domain_target")
        outputs.get("acm_certificate_arn")
        val_name = outputs.get("acm_validation_cname_name")
        val_value = outputs.get("acm_validation_cname_value")

        output_table.add_row("Custom Domain", custom_domain)
        if regional:
            output_table.add_row("Regional Domain (CNAME target)", str(regional))
            if not str(regional).startswith("d-"):
                console.print(
                    "[yellow]Warning: regionalDomainName doesn't start with 'd-' — "
                    "verify this is the correct value.[/yellow]"
                )
        if val_name:
            output_table.add_row("ACM Validation CNAME Name", str(val_name))
        if val_value:
            output_table.add_row("ACM Validation CNAME Value", str(val_value))

    console.print()
    console.print(output_table)

    # Print cert status if custom domain is configured
    if custom_domain:
        _print_cert_status(custom_domain, env)

    console.print("\n[green bold]Deployment complete![/green bold]")
    if api_gw:
        console.print(
            "\nConnect via Claude Connectors:\n"
            "  1. Go to Settings → Connectors\n"
            "  2. Click 'Add custom connector'\n"
            f"  3. Enter URL: {api_gw}"
        )

    console.print(
        "\n[dim]To enable cost filtering in AWS Cost Explorer, activate the Project, "
        "Environment, and ManagedBy tags at: "
        "AWS Console \u2192 Billing \u2192 Cost allocation tags[/dim]"
    )


def _print_cert_status(domain: str, env: str) -> None:
    """Check ACM certificate status and print next steps."""
    try:
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
                    cert_status = cert.get("Status", "UNKNOWN")
                    console.print(f"\nCertificate status: [bold]{cert_status}[/bold]")
                    if cert_status == "PENDING_VALIDATION":
                        console.print(
                            f"Run [bold]opencontext domain --env {env}[/bold] "
                            "to see DNS records for your IT team."
                        )
                    elif cert_status == "ISSUED":
                        console.print("[green]Certificate is active.[/green]")
                    return
        console.print(
            f"\nRun [bold]opencontext domain --env {env}[/bold] to check domain status."
        )
    except Exception:
        pass
