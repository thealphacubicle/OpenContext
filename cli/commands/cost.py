from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta, timezone

import typer
from rich.table import Table

from cli.utils import (
    console,
    get_terraform_dir,
    load_tfvars,
    select_workspace,
)

app = typer.Typer()

# AWS pricing constants
LAMBDA_PRICE_PER_1M_REQUESTS = 0.20          # USD
LAMBDA_PRICE_PER_GB_SECOND = 0.0000166667    # USD
LAMBDA_DEFAULT_MEMORY_MB = 512
APIGW_PRICE_PER_1M_REQUESTS = 3.50           # USD (REST API)


def _cloudwatch_metric(
    namespace: str,
    metric_name: str,
    dimensions: list[dict],
    start_time: str,
    end_time: str,
    period: int,
    statistic: str,
) -> float | None:
    """Fetch a single CloudWatch metric statistic. Returns the value or None."""
    dim_args = []
    for d in dimensions:
        dim_args.append(f"Name={d['Name']},Value={d['Value']}")

    try:
        result = subprocess.run(
            [
                "aws", "cloudwatch", "get-metric-statistics",
                "--namespace", namespace,
                "--metric-name", metric_name,
                "--dimensions", *dim_args,
                "--start-time", start_time,
                "--end-time", end_time,
                "--period", str(period),
                "--statistics", statistic,
                "--output", "json",
            ],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return None
        data = json.loads(result.stdout)
        datapoints = data.get("Datapoints", [])
        if not datapoints:
            return 0.0
        return datapoints[0].get(statistic, 0.0)
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError, KeyError):
        return None


def _get_api_name(terraform_dir, env: str) -> str | None:
    """Try to get the API Gateway name from terraform output or AWS CLI."""
    try:
        result = subprocess.run(
            ["terraform", "output", "-raw", "api_gateway_url"],
            cwd=terraform_dir,
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0 and result.stdout.strip():
            # URL format: https://{api-id}.execute-api.{region}.amazonaws.com/{stage}
            url = result.stdout.strip()
            api_id = url.split("//")[-1].split(".")[0]
            if api_id:
                api_result = subprocess.run(
                    ["aws", "apigateway", "get-rest-api", "--rest-api-id", api_id, "--output", "json"],
                    capture_output=True, text=True, timeout=15,
                )
                if api_result.returncode == 0:
                    api_data = json.loads(api_result.stdout)
                    return api_data.get("name")
    except Exception:
        pass
    return None


@app.callback(invoke_without_command=True)
def cost(
    ctx: typer.Context,
    env: str = typer.Option("staging", help="Environment: staging or prod"),
    days: int = typer.Option(30, "--days", help="Number of days to look back"),
) -> None:
    """Estimate AWS costs based on CloudWatch usage metrics."""
    if ctx.invoked_subcommand is not None:
        return

    terraform_dir = get_terraform_dir()

    try:
        tfvars = load_tfvars(env)
    except SystemExit:
        raise typer.Exit(1)

    lambda_name = tfvars.get("lambda_name", "")
    if not lambda_name:
        console.print(
            "[red]Could not determine Lambda function name from tfvars.[/red]\n"
            "Run [bold]opencontext configure[/bold] first."
        )
        raise typer.Exit(1)

    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days)
    start_time = start.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_time = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    period = days * 86400  # one bucket covering the full range

    console.print(f"\n[bold]Fetching CloudWatch metrics for the last {days} day(s)...[/bold]")

    # Select workspace to get terraform outputs
    with console.status("Selecting Terraform workspace..."):
        try:
            select_workspace(env, terraform_dir)
        except Exception:
            pass

    lambda_dims = [{"Name": "FunctionName", "Value": lambda_name}]

    with console.status("Fetching Lambda invocations..."):
        lambda_invocations = _cloudwatch_metric(
            namespace="AWS/Lambda",
            metric_name="Invocations",
            dimensions=lambda_dims,
            start_time=start_time,
            end_time=end_time,
            period=period,
            statistic="Sum",
        )

    with console.status("Fetching Lambda duration..."):
        lambda_avg_duration_ms = _cloudwatch_metric(
            namespace="AWS/Lambda",
            metric_name="Duration",
            dimensions=lambda_dims,
            start_time=start_time,
            end_time=end_time,
            period=period,
            statistic="Average",
        )

    with console.status("Looking up API Gateway name..."):
        api_name = _get_api_name(terraform_dir, env)

    apigw_requests = None
    if api_name:
        with console.status(f"Fetching API Gateway requests for '{api_name}'..."):
            apigw_requests = _cloudwatch_metric(
                namespace="AWS/ApiGateway",
                metric_name="Count",
                dimensions=[{"Name": "ApiName", "Value": api_name}],
                start_time=start_time,
                end_time=end_time,
                period=period,
                statistic="Sum",
            )

    # Cost calculations
    lambda_invocations = lambda_invocations or 0.0
    lambda_avg_duration_ms = lambda_avg_duration_ms or 0.0
    apigw_requests = apigw_requests or 0.0

    lambda_memory_gb = LAMBDA_DEFAULT_MEMORY_MB / 1024
    lambda_gb_seconds = lambda_invocations * (lambda_avg_duration_ms / 1000) * lambda_memory_gb

    lambda_request_cost = (lambda_invocations / 1_000_000) * LAMBDA_PRICE_PER_1M_REQUESTS
    lambda_compute_cost = lambda_gb_seconds * LAMBDA_PRICE_PER_GB_SECOND
    apigw_cost = (apigw_requests / 1_000_000) * APIGW_PRICE_PER_1M_REQUESTS
    total_cost = lambda_request_cost + lambda_compute_cost + apigw_cost

    projected_monthly = (total_cost / days * 30) if days != 30 else total_cost

    # Print table
    table = Table(
        title=f"Estimated AWS Costs — {env} — Last {days} day(s)",
        show_lines=True,
    )
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")

    table.add_row("Lambda name", lambda_name)
    table.add_row(
        f"Lambda invocations (last {days}d)",
        f"{lambda_invocations:,.0f}" if lambda_invocations is not None else "N/A",
    )
    table.add_row(
        "Lambda avg duration",
        f"{lambda_avg_duration_ms:.1f} ms" if lambda_avg_duration_ms is not None else "N/A",
    )
    table.add_row(
        f"API Gateway requests (last {days}d)",
        f"{apigw_requests:,.0f}" if api_name else "N/A (could not get API name)",
    )
    table.add_row(
        "Est. Lambda request cost",
        f"${lambda_request_cost:.4f}",
    )
    table.add_row(
        "Est. Lambda compute cost",
        f"${lambda_compute_cost:.4f}",
    )
    table.add_row(
        "Est. API Gateway cost",
        f"${apigw_cost:.4f}" if api_name else "N/A",
    )
    table.add_row(
        f"[bold]Total estimated cost ({days}d)[/bold]",
        f"[bold]${total_cost:.4f}[/bold]",
    )
    if days != 30:
        table.add_row(
            "[bold]Projected monthly cost[/bold]",
            f"[bold]${projected_monthly:.4f}[/bold]",
        )

    console.print()
    console.print(table)
    console.print()
    console.print(
        "[dim]Estimates based on AWS public pricing. "
        "Actual costs may vary. Check AWS Cost Explorer for exact figures.[/dim]"
    )
    console.print()
