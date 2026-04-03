from __future__ import annotations

import subprocess
from pathlib import Path

import questionary
import typer
import yaml
from rich.table import Table

from cli.utils import (
    console,
    friendly_exit,
    get_project_root,
    get_terraform_dir,
    run_cmd,
)

PLUGINS = ["CKAN", "Socrata", "ArcGIS"]


def _load_example_defaults(project_root: Path) -> dict:
    example = project_root / "config-example.yaml"
    if example.exists():
        with open(example) as f:
            return yaml.safe_load(f) or {}
    return {}


def _prompt_plugin_config(plugin: str, defaults: dict) -> dict:
    """Ask plugin-specific questions and return the plugin config dict."""
    plugin_key = plugin.lower()
    plugin_defaults = defaults.get("plugins", {}).get(plugin_key, {})

    cfg: dict = {"enabled": True}

    if plugin == "CKAN":
        cfg["base_url"] = (questionary.text(
            "CKAN API base URL:",
            default=plugin_defaults.get("base_url", "https://data.example.gov"),
        ).ask() or "").rstrip("/")
        cfg["portal_url"] = (questionary.text(
            "CKAN public portal URL:",
            default=plugin_defaults.get("portal_url", cfg["base_url"]),
        ).ask() or "").rstrip("/")
        cfg["city_name"] = questionary.text(
            "City name (for display):",
            default=plugin_defaults.get("city_name", "Your City"),
        ).ask()
        timeout = questionary.text(
            "HTTP timeout (seconds):",
            default=str(plugin_defaults.get("timeout", 120)),
        ).ask()
        cfg["timeout"] = int(timeout)

    elif plugin == "Socrata":
        cfg["base_url"] = (questionary.text(
            "Socrata base URL:",
            default=plugin_defaults.get("base_url", "https://data.example.gov"),
        ).ask() or "").rstrip("/")
        app_token = questionary.text(
            "Socrata app token (optional, press Enter to skip):",
            default=plugin_defaults.get("app_token", ""),
        ).ask()
        if app_token:
            cfg["app_token"] = app_token
        timeout = questionary.text(
            "HTTP timeout (seconds):",
            default=str(plugin_defaults.get("timeout", 120)),
        ).ask()
        cfg["timeout"] = int(timeout)

    elif plugin == "ArcGIS":
        cfg["portal_url"] = (questionary.text(
            "ArcGIS Hub portal URL:",
            default=plugin_defaults.get("portal_url", "https://hub.arcgis.com"),
        ).ask() or "").rstrip("/")
        cfg["city_name"] = questionary.text(
            "City name (for display):",
            default=plugin_defaults.get("city_name", "Your City"),
        ).ask()
        timeout = questionary.text(
            "HTTP timeout (seconds):",
            default=str(plugin_defaults.get("timeout", 120)),
        ).ask()
        cfg["timeout"] = int(timeout)

    # Abort if any prompt was cancelled (Ctrl+C)
    for v in cfg.values():
        if v is None:
            console.print("\n[yellow]Configuration cancelled.[/yellow]")
            raise typer.Exit(0)

    return cfg


def _write_config(project_root: Path, data: dict) -> Path:
    path = project_root / "config.yaml"
    with open(path, "w") as f:
        f.write("---\n")
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    return path


def _write_tfvars(
    terraform_dir: Path,
    env: str,
    lambda_name: str,
    region: str,
    custom_domain: str,
) -> Path:
    path = terraform_dir / f"{env}.tfvars"
    lines = [
        f'lambda_name   = "{lambda_name}"',
        f'stage_name    = "{env}"',
        f'aws_region    = "{region}"',
        'config_file   = "config.yaml"',
        f'custom_domain = "{custom_domain}"',
    ]
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    return path


@friendly_exit
def configure() -> None:
    """Interactive wizard to configure your OpenContext MCP server."""
    project_root = get_project_root()
    terraform_dir = get_terraform_dir()

    console.print("\n[bold]OpenContext Configuration Wizard[/bold]\n")

    # Step 1 — Starting point
    starting_point = questionary.select(
        "How would you like to start?",
        choices=["Use example config as template", "Start from scratch"],
    ).ask()
    if starting_point is None:
        raise typer.Exit(0)

    defaults: dict = {}
    if starting_point == "Use example config as template":
        defaults = _load_example_defaults(project_root)

    # Step 2 — Organization details
    console.print("\n[bold]Organization Details[/bold]")

    org_name = questionary.text(
        "Organization name:",
        default=defaults.get("organization", ""),
    ).ask()
    if org_name is None:
        raise typer.Exit(0)

    city_name = questionary.text("City name:").ask()
    if city_name is None:
        raise typer.Exit(0)

    env = questionary.select(
        "Environment:",
        choices=["staging", "prod"],
    ).ask()
    if env is None:
        raise typer.Exit(0)

    # Step 3 — Plugin selection
    console.print("\n[bold]Plugin Selection[/bold]")

    plugin = questionary.select(
        "Which data platform plugin?",
        choices=PLUGINS,
    ).ask()
    if plugin is None:
        raise typer.Exit(0)

    plugin_config = _prompt_plugin_config(plugin, defaults)
    plugin_key = plugin.lower()

    # Step 4 — AWS settings
    console.print("\n[bold]AWS Settings[/bold]")

    aws_defaults = defaults.get("aws", {})
    region = questionary.text(
        "AWS region:",
        default=aws_defaults.get("region", "us-east-1"),
    ).ask()
    if region is None:
        raise typer.Exit(0)

    city_slug = city_name.lower().replace(" ", "-")
    suggested_lambda = f"{city_slug}-opencontext-mcp-{env}"

    lambda_name = questionary.text(
        "Lambda function name:",
        default=suggested_lambda,
    ).ask()
    if lambda_name is None:
        raise typer.Exit(0)

    memory_str = questionary.text(
        "Lambda memory (MB):",
        default=str(aws_defaults.get("lambda_memory", 512)),
    ).ask()
    if memory_str is None:
        raise typer.Exit(0)
    lambda_memory = int(memory_str)

    timeout_str = questionary.text(
        "Lambda timeout (seconds):",
        default=str(aws_defaults.get("lambda_timeout", 120)),
    ).ask()
    if timeout_str is None:
        raise typer.Exit(0)
    lambda_timeout = int(timeout_str)

    # Step 5 — Custom domain
    console.print("\n[bold]Custom Domain[/bold]")

    use_domain = questionary.confirm(
        "Do you want a custom domain?",
        default=False,
    ).ask()
    if use_domain is None:
        raise typer.Exit(0)

    custom_domain = ""
    if use_domain:
        custom_domain = questionary.text(
            "Domain name (e.g. data-mcp.boston.gov):"
        ).ask()
        if custom_domain is None:
            raise typer.Exit(0)

    # Step 6 — Write outputs
    console.print("\n[bold]Writing configuration files...[/bold]\n")

    server_name = f"{city_name} OpenData MCP Server"
    description = f"MCP server for {city_name}'s open data portal"

    config_data = {
        "server_name": server_name,
        "description": description,
        "organization": org_name,
        "plugins": {
            plugin_key: plugin_config,
        },
        "aws": {
            "region": region,
            "lambda_name": lambda_name,
            "lambda_memory": lambda_memory,
            "lambda_timeout": lambda_timeout,
        },
        "logging": {
            "level": "INFO",
            "format": "json",
        },
    }

    config_path = _write_config(project_root, config_data)
    tfvars_path = _write_tfvars(terraform_dir, env, lambda_name, region, custom_domain)

    # Terraform workspace
    ws_name = f"{city_slug}-{env}"

    result = subprocess.run(
        ["terraform", "workspace", "list"],
        cwd=terraform_dir,
        capture_output=True,
        text=True,
        timeout=15,
    )
    existing = [w.strip().lstrip("* ") for w in result.stdout.splitlines()]

    if ws_name in existing:
        run_cmd(
            ["terraform", "workspace", "select", ws_name],
            cwd=terraform_dir,
            spinner_msg=f"Selecting workspace [bold]{ws_name}[/bold]",
        )
    else:
        run_cmd(
            ["terraform", "workspace", "new", ws_name],
            cwd=terraform_dir,
            spinner_msg=f"Creating workspace [bold]{ws_name}[/bold]",
        )

    # Terraform init if needed
    if not (terraform_dir / ".terraform").exists():
        run_cmd(
            ["terraform", "init"],
            cwd=terraform_dir,
            spinner_msg="Initializing Terraform",
        )

    # Print summary
    summary = Table(title="Configuration Summary", show_lines=True)
    summary.add_column("Setting", style="bold")
    summary.add_column("Value")

    summary.add_row("Config file", str(config_path.relative_to(project_root)))
    summary.add_row("Terraform vars", str(tfvars_path.relative_to(project_root)))
    summary.add_row("Organization", org_name)
    summary.add_row("City", city_name)
    summary.add_row("Environment", env)
    summary.add_row("Plugin", plugin)
    summary.add_row("Lambda name", lambda_name)
    summary.add_row("AWS region", region)
    summary.add_row("Lambda memory", f"{lambda_memory} MB")
    summary.add_row("Lambda timeout", f"{lambda_timeout}s")
    summary.add_row("X-Ray Tracing", "Enabled")
    summary.add_row("Dead Letter Queue", "Enabled (failures → SQS)")
    summary.add_row("Workspace", ws_name)
    summary.add_row(
        "Custom domain",
        (
            custom_domain
            if custom_domain
            else "[dim]None (no domain resources will be created)[/dim]"
        ),
    )

    console.print()
    console.print(summary)
    console.print()
    console.print("[green bold]Configuration complete![/green bold]")
    console.print("Next step: [bold]opencontext deploy --env " + env + "[/bold]")
