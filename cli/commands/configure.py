from __future__ import annotations

import os
import subprocess
from pathlib import Path

import boto3
import botocore.exceptions
import questionary
import typer
import yaml
from rich.table import Table

from cli.utils import (
    console,
    friendly_exit,
    get_project_root,
    get_terraform_dir,
    normalize_cloud,
    run_cmd,
)

PLUGINS = ["CKAN", "Socrata", "ArcGIS"]

# Bucket name must match the `backend "s3"` block in terraform/aws/main.tf.
TERRAFORM_STATE_BUCKET = "opencontext-terraform-state"
TERRAFORM_STATE_BUCKET_GCP = "opencontext-terraform-state-gcp"


def _ensure_state_bucket(bucket_name: str, region: str) -> None:
    """Check that the Terraform S3 state bucket exists; create it if not.

    Versioning and server-side encryption are enabled on newly created buckets.
    No DynamoDB table is created — the Terraform backend does not use state
    locking.
    """
    s3 = boto3.client("s3", region_name=region)

    try:
        s3.head_bucket(Bucket=bucket_name)
        console.print(
            f"[dim]Terraform state bucket [bold]{bucket_name}[/bold] already exists.[/dim]"
        )
        return
    except botocore.exceptions.ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code not in ("404", "NoSuchBucket"):
            raise

    # Bucket does not exist — create it.
    console.print(
        f"[yellow]Terraform state bucket [bold]{bucket_name}[/bold] not found. Creating...[/yellow]"
    )

    if region == "us-east-1":
        # us-east-1 does not accept a LocationConstraint.
        s3.create_bucket(Bucket=bucket_name)
    else:
        s3.create_bucket(
            Bucket=bucket_name,
            CreateBucketConfiguration={"LocationConstraint": region},
        )

    s3.put_bucket_versioning(
        Bucket=bucket_name,
        VersioningConfiguration={"Status": "Enabled"},
    )

    s3.put_bucket_encryption(
        Bucket=bucket_name,
        ServerSideEncryptionConfiguration={
            "Rules": [
                {
                    "ApplyServerSideEncryptionByDefault": {
                        "SSEAlgorithm": "AES256",
                    }
                }
            ]
        },
    )

    console.print(
        f"[green]Created S3 bucket [bold]{bucket_name}[/bold] "
        f"(region: {region}, versioning: enabled, encryption: AES256).[/green]"
    )


def _ensure_gcp_state_bucket(bucket_name: str, region: str, project_id: str) -> None:
    """Check that the Terraform GCS state bucket exists; create it if not."""
    describe_cmd = [
        "gcloud",
        "storage",
        "buckets",
        "describe",
        f"gs://{bucket_name}",
        "--project",
        project_id,
    ]
    try:
        result = subprocess.run(
            describe_cmd,
            capture_output=True,
            text=True,
            timeout=20,
        )
        if result.returncode == 0:
            console.print(
                f"[dim]Terraform state bucket [bold]{bucket_name}[/bold] already exists.[/dim]"
            )
            return
    except (FileNotFoundError, subprocess.TimeoutExpired):
        console.print(
            "[red]gcloud CLI is required to manage GCP state buckets.[/red]\n"
            "Install it, then re-run [bold]opencontext authenticate --cloud gcp[/bold]."
        )
        raise typer.Exit(1)

    console.print(
        f"[yellow]Terraform state bucket [bold]{bucket_name}[/bold] not found. Creating...[/yellow]"
    )
    run_cmd(
        [
            "gcloud",
            "storage",
            "buckets",
            "create",
            f"gs://{bucket_name}",
            "--project",
            project_id,
            "--location",
            region,
            "--uniform-bucket-level-access",
        ],
        spinner_msg="Creating GCS state bucket",
    )
    run_cmd(
        [
            "gcloud",
            "storage",
            "buckets",
            "update",
            f"gs://{bucket_name}",
            "--project",
            project_id,
            "--versioning",
        ],
        spinner_msg="Enabling GCS bucket versioning",
    )
    console.print(
        f"[green]Created GCS bucket [bold]{bucket_name}[/bold] "
        f"(region: {region}, versioning: enabled).[/green]"
    )


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
        cfg["base_url"] = (
            questionary.text(
                "CKAN API base URL:",
                default=plugin_defaults.get("base_url", "https://data.example.gov"),
            ).ask()
            or ""
        ).rstrip("/")
        cfg["portal_url"] = (
            questionary.text(
                "CKAN public portal URL:",
                default=plugin_defaults.get("portal_url", cfg["base_url"]),
            ).ask()
            or ""
        ).rstrip("/")
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
        cfg["base_url"] = (
            questionary.text(
                "Socrata base URL:",
                default=plugin_defaults.get("base_url", "https://data.example.gov"),
            ).ask()
            or ""
        ).rstrip("/")
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
        cfg["portal_url"] = (
            questionary.text(
                "ArcGIS Hub portal URL:",
                default=plugin_defaults.get("portal_url", "https://hub.arcgis.com"),
            ).ask()
            or ""
        ).rstrip("/")
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


def _write_tfvars_gcp(
    terraform_dir: Path,
    env: str,
    project_id: str,
    region: str,
    function_name: str,
    function_memory_mb: int,
    function_timeout_sec: int,
    min_instance_count: int,
    max_instance_count: int,
    artifact_bucket_name: str,
) -> Path:
    path = terraform_dir / f"{env}.tfvars"
    lines = [
        f'project_id           = "{project_id}"',
        f'gcp_region           = "{region}"',
        f'stage_name           = "{env}"',
        'config_file          = "../../config.yaml"',
        f'function_name        = "{function_name}"',
        f"function_memory_mb   = {function_memory_mb}",
        f"function_timeout_sec = {function_timeout_sec}",
        f"min_instance_count   = {min_instance_count}",
        f"max_instance_count   = {max_instance_count}",
        f'artifact_bucket_name = "{artifact_bucket_name}"',
    ]
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    return path


@friendly_exit
def configure(
    cloud: str = typer.Option("aws", "--cloud", help="Cloud provider: aws or gcp"),
    state_bucket: str | None = typer.Option(
        None,
        "--state-bucket",
        help="Terraform state bucket name override (S3 on aws, GCS on gcp)",
    ),
) -> None:
    """Interactive wizard to configure your OpenContext MCP server."""
    if not isinstance(cloud, str):
        cloud = "aws"
    cloud = normalize_cloud(cloud)
    if not isinstance(state_bucket, str) or state_bucket.strip() == "":
        state_bucket = (
            TERRAFORM_STATE_BUCKET if cloud == "aws" else TERRAFORM_STATE_BUCKET_GCP
        )

    project_root = get_project_root()
    terraform_dir = get_terraform_dir(cloud)

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

    city_slug = city_name.lower().replace(" ", "-")
    aws_defaults = defaults.get("aws", {})
    gcp_defaults = defaults.get("gcp", {})

    lambda_name = ""
    lambda_memory = 0
    lambda_timeout = 0
    custom_domain = ""

    gcp_project_id = ""
    gcp_function_name = ""
    gcp_memory_mb = 0
    gcp_timeout_sec = 0
    gcp_min_instances = 0
    gcp_max_instances = 0
    gcp_artifact_bucket_name = ""

    if cloud == "aws":
        # Step 4 — AWS settings
        console.print("\n[bold]AWS Settings[/bold]")

        region = questionary.text(
            "AWS region:",
            default=aws_defaults.get("region", "us-east-1"),
        ).ask()
        if region is None:
            raise typer.Exit(0)

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
        if use_domain:
            custom_domain = questionary.text(
                "Domain name (e.g. data-mcp.boston.gov):"
            ).ask()
            if custom_domain is None:
                raise typer.Exit(0)
    else:
        # Step 4 — GCP settings
        console.print("\n[bold]GCP Settings[/bold]")
        region = questionary.text(
            "GCP region:",
            default=gcp_defaults.get("region", "us-central1"),
        ).ask()
        if region is None:
            raise typer.Exit(0)

        gcp_project_id = questionary.text("GCP project ID:").ask()
        if gcp_project_id is None:
            raise typer.Exit(0)
        gcp_project_id = gcp_project_id.strip()
        if not gcp_project_id:
            console.print("[red]GCP project ID cannot be empty.[/red]")
            raise typer.Exit(1)

        suggested_function = f"{city_slug}-opencontext-mcp-{env}"
        gcp_function_name = questionary.text(
            "Cloud Function name:",
            default=gcp_defaults.get("function_name", suggested_function),
        ).ask()
        if gcp_function_name is None:
            raise typer.Exit(0)

        gcp_memory_str = questionary.text(
            "Function memory (MiB):",
            default=str(gcp_defaults.get("function_memory_mb", 512)),
        ).ask()
        if gcp_memory_str is None:
            raise typer.Exit(0)
        gcp_memory_mb = int(gcp_memory_str)

        gcp_timeout_str = questionary.text(
            "Function timeout (seconds):",
            default=str(gcp_defaults.get("function_timeout_sec", 120)),
        ).ask()
        if gcp_timeout_str is None:
            raise typer.Exit(0)
        gcp_timeout_sec = int(gcp_timeout_str)

        # Autoscaling controls
        gcp_min_instances_str = questionary.text(
            "Min instances (autoscaling):",
            default=str(gcp_defaults.get("min_instance_count", 0)),
        ).ask()
        if gcp_min_instances_str is None:
            raise typer.Exit(0)
        gcp_min_instances = int(gcp_min_instances_str)

        gcp_max_instances_str = questionary.text(
            "Max instances (autoscaling):",
            default=str(gcp_defaults.get("max_instance_count", 100)),
        ).ask()
        if gcp_max_instances_str is None:
            raise typer.Exit(0)
        gcp_max_instances = int(gcp_max_instances_str)

        if gcp_min_instances < 0 or gcp_max_instances < 1:
            console.print(
                "[red]Instance counts must be non-negative, with max >= 1.[/red]"
            )
            raise typer.Exit(1)
        if gcp_min_instances > gcp_max_instances:
            console.print(
                "[red]Min instances cannot be greater than max instances.[/red]"
            )
            raise typer.Exit(1)

        gcp_artifact_bucket_name = (
            questionary.text(
                "Artifact bucket name (optional, Enter for auto-generated):",
                default="",
            ).ask()
            or ""
        ).strip()

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
        "aws": {},
        "gcp": {},
        "logging": {
            "level": "INFO",
            "format": "json",
        },
    }
    if cloud == "aws":
        config_data["aws"] = {
            "region": region,
            "lambda_name": lambda_name,
            "lambda_memory": lambda_memory,
            "lambda_timeout": lambda_timeout,
        }
        config_data["gcp"] = defaults.get("gcp", {})
    else:
        config_data["gcp"] = {
            "region": region,
            "function_name": gcp_function_name,
            "function_memory_mb": gcp_memory_mb,
            "function_timeout_sec": gcp_timeout_sec,
            "min_instance_count": gcp_min_instances,
            "max_instance_count": gcp_max_instances,
        }
        config_data["aws"] = defaults.get("aws", {})

    config_path = _write_config(project_root, config_data)
    if cloud == "aws":
        tfvars_path = _write_tfvars(
            terraform_dir, env, lambda_name, region, custom_domain
        )
    else:
        tfvars_path = _write_tfvars_gcp(
            terraform_dir=terraform_dir,
            env=env,
            project_id=gcp_project_id,
            region=region,
            function_name=gcp_function_name,
            function_memory_mb=gcp_memory_mb,
            function_timeout_sec=gcp_timeout_sec,
            min_instance_count=gcp_min_instances,
            max_instance_count=gcp_max_instances,
            artifact_bucket_name=gcp_artifact_bucket_name,
        )

    # Terraform workspace
    ws_name = f"{city_slug}-{env}"

    if cloud == "aws":
        _ensure_state_bucket(state_bucket, region)
        # Always reconfigure backend so bucket/region overrides are applied
        # even when .terraform already exists.
        init_cmd = [
            "terraform",
            "init",
            "-reconfigure",
            f"-backend-config=bucket={state_bucket}",
            f"-backend-config=region={region}",
        ]
        run_cmd(
            init_cmd,
            cwd=terraform_dir,
            spinner_msg="Initializing Terraform",
        )
    else:
        _ensure_gcp_state_bucket(state_bucket, region, gcp_project_id)
        # Always reconfigure backend so bucket overrides are applied even when
        # .terraform already exists from previous runs.
        init_cmd = [
            "terraform",
            "init",
            "-reconfigure",
            f"-backend-config=bucket={state_bucket}",
        ]
        run_cmd(
            init_cmd,
            cwd=terraform_dir,
            spinner_msg="Initializing Terraform",
        )

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
    summary.add_row("Cloud provider", cloud)
    if cloud == "aws":
        summary.add_row("Lambda name", lambda_name)
        summary.add_row("AWS region", region)
        summary.add_row("Lambda memory", f"{lambda_memory} MB")
        summary.add_row("Lambda timeout", f"{lambda_timeout}s")
        summary.add_row("X-Ray Tracing", "Enabled")
        summary.add_row("Dead Letter Queue", "Enabled (failures → SQS)")
    else:
        summary.add_row("GCP project", gcp_project_id)
        summary.add_row("GCP region", region)
        summary.add_row("Function name", gcp_function_name)
        summary.add_row("Function memory", f"{gcp_memory_mb} MiB")
        summary.add_row("Function timeout", f"{gcp_timeout_sec}s")
        summary.add_row("Min instances", str(gcp_min_instances))
        summary.add_row("Max instances", str(gcp_max_instances))
        summary.add_row(
            "Artifact bucket",
            gcp_artifact_bucket_name
            if gcp_artifact_bucket_name
            else "[dim]Auto-generated by Terraform[/dim]",
        )
    summary.add_row("Workspace", ws_name)
    if cloud == "aws":
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
    command_prefix = "uv run " if os.environ.get("UV") else ""
    next_cmd = f"{command_prefix}opencontext deploy --cloud {cloud} --env {env}"
    console.print(f"Next step: [bold]{next_cmd}[/bold]")
