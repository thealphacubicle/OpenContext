from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import typer
import yaml
from rich.table import Table

from cli.utils import console, get_project_root, get_terraform_dir

app = typer.Typer()

PLUGIN_REQUIRED_FIELDS: dict[str, list[str]] = {
    "ckan": ["base_url"],
    "socrata": ["base_url"],
    "arcgis": ["portal_url"],
}


def _parse_tfvars_file(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = re.match(r'^(\w+)\s*=\s*"(.*)"$', line)
            if m:
                result[m.group(1)] = m.group(2)
            else:
                nm = re.match(r"^(\w+)\s*=\s*(\d+)$", line)
                if nm:
                    result[nm.group(1)] = nm.group(2)
    return result


def run_checks(env: str) -> bool:
    """Run all validation checks. Returns True if all pass."""
    project_root = get_project_root()
    terraform_dir = get_terraform_dir()

    # (check_name, passed, detail)
    checks: list[tuple[str, bool, str]] = []

    # 1. config.yaml exists
    config_path = project_root / "config.yaml"
    config_exists = config_path.exists()
    checks.append((
        "config.yaml exists",
        config_exists,
        "Found" if config_exists else "Not found — run: opencontext configure",
    ))

    config: dict = {}
    if config_exists:
        with open(config_path) as f:
            config = yaml.safe_load(f) or {}

    # 2. Exactly one plugin enabled
    plugins = config.get("plugins", {})
    enabled_plugins = [
        name for name, cfg in plugins.items()
        if isinstance(cfg, dict) and cfg.get("enabled", False)
    ]
    if len(enabled_plugins) == 1:
        checks.append(("Exactly one plugin enabled", True, enabled_plugins[0]))
    elif len(enabled_plugins) == 0:
        checks.append(("Exactly one plugin enabled", False, "No plugins enabled in config.yaml"))
    else:
        checks.append((
            "Exactly one plugin enabled",
            False,
            f"Multiple enabled: {', '.join(enabled_plugins)}",
        ))

    # 3. Plugin config valid (required fields present)
    if len(enabled_plugins) == 1:
        plugin_name = enabled_plugins[0]
        plugin_cfg = plugins.get(plugin_name, {})
        required = PLUGIN_REQUIRED_FIELDS.get(plugin_name, [])
        missing = [f for f in required if not plugin_cfg.get(f)]
        if missing:
            checks.append(("Plugin config valid", False, f"Missing fields: {', '.join(missing)}"))
        else:
            checks.append(("Plugin config valid", True, f"{plugin_name} — required fields present"))
    else:
        checks.append(("Plugin config valid", False, "Skipped — fix plugin selection first"))

    # 4. terraform/aws/{env}.tfvars exists
    tfvars_path = terraform_dir / f"{env}.tfvars"
    tfvars_exists = tfvars_path.exists()
    checks.append((
        f"terraform/aws/{env}.tfvars exists",
        tfvars_exists,
        "Found" if tfvars_exists else "Run: opencontext configure",
    ))

    tfvars: dict[str, str] = {}
    if tfvars_exists:
        tfvars = _parse_tfvars_file(tfvars_path)

    custom_domain = tfvars.get("custom_domain", "")

    # 5. Terraform installed
    tf_installed = False
    try:
        result = subprocess.run(
            ["terraform", "--version"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            version_line = result.stdout.strip().splitlines()[0]
            checks.append(("Terraform installed", True, version_line))
            tf_installed = True
        else:
            checks.append(("Terraform installed", False, "terraform --version returned non-zero"))
    except FileNotFoundError:
        checks.append(("Terraform installed", False, "Not found — install: https://www.terraform.io/downloads"))
    except subprocess.TimeoutExpired:
        checks.append(("Terraform installed", False, "Timeout running terraform --version"))

    # 6. terraform/aws/.terraform directory exists (init has been run)
    tf_initialized = (terraform_dir / ".terraform").exists()
    checks.append((
        "Terraform initialized",
        tf_initialized,
        ".terraform directory found" if tf_initialized else "Run: opencontext configure",
    ))

    # Note: terraform validate is intentionally skipped here because it
    # references lambda-deployment.zip, which does not exist until the
    # packaging step inside `opencontext deploy`. Running validate before
    # packaging would always fail. Terraform plan (run inside deploy) catches
    # the same configuration errors after the zip has been created.

    # 7. AWS credentials valid
    try:
        result = subprocess.run(
            ["aws", "sts", "get-caller-identity", "--output", "json"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            identity = json.loads(result.stdout)
            checks.append((
                "AWS credentials valid",
                True,
                f"Account: {identity.get('Account', 'unknown')}",
            ))
        else:
            checks.append(("AWS credentials valid", False, "Run: aws configure"))
    except FileNotFoundError:
        checks.append(("AWS credentials valid", False, "AWS CLI not found"))
    except (subprocess.TimeoutExpired, json.JSONDecodeError):
        checks.append(("AWS credentials valid", False, "Run: aws configure"))

    # 8. ACM cert exists for custom domain (only if custom_domain is set)
    if custom_domain:
        try:
            result = subprocess.run(
                ["aws", "acm", "list-certificates", "--output", "json"],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0:
                certs = json.loads(result.stdout).get("CertificateSummaryList", [])
                cert = next(
                    (c for c in certs if c.get("DomainName") == custom_domain), None
                )
                if cert:
                    status = cert.get("Status", "UNKNOWN")
                    checks.append((
                        f"ACM cert exists for {custom_domain}",
                        True,
                        f"Status: {status}",
                    ))
                else:
                    checks.append((
                        f"ACM cert exists for {custom_domain}",
                        False,
                        "No certificate found — deploy first to request one",
                    ))
            else:
                checks.append((
                    f"ACM cert exists for {custom_domain}",
                    False,
                    "Could not list ACM certificates",
                ))
        except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError) as e:
            checks.append((
                f"ACM cert exists for {custom_domain}",
                False,
                f"Error: {str(e)[:60]}",
            ))

    # Print results table
    table = Table(title=f"OpenContext Validation — {env}", show_lines=True)
    table.add_column("#", style="dim", justify="right", width=3)
    table.add_column("Check", style="bold")
    table.add_column("Status", justify="center", width=10)
    table.add_column("Details")

    all_passed = True
    for i, (check_name, passed, detail) in enumerate(checks, 1):
        status_cell = "[green]✅ Pass[/green]" if passed else "[red]❌ Fail[/red]"
        if not passed:
            all_passed = False
        table.add_row(str(i), check_name, status_cell, detail)

    console.print()
    console.print(table)
    console.print()

    if all_passed:
        console.print("[green bold]✅ All checks passed — Ready to deploy[/green bold]")
    else:
        console.print("[red bold]❌ Fix the above issues before deploying[/red bold]")

    return all_passed


@app.callback(invoke_without_command=True)
def validate(
    ctx: typer.Context,
    env: str = typer.Option("staging", help="Environment: staging or prod"),
) -> None:
    """Run pre-deployment validation checks."""
    if ctx.invoked_subcommand is not None:
        return
    passed = run_checks(env)
    if not passed:
        raise typer.Exit(1)
