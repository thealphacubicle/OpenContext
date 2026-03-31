from __future__ import annotations

import subprocess

import typer

from cli.utils import (
    console,
    ensure_config_exists,
    ensure_terraform_init,
    friendly_exit,
    get_terraform_dir,
    load_tfvars,
    run_cmd_stream,
    select_workspace,
)


@friendly_exit
def logs(
    env: str = typer.Option("staging", help="Environment: staging or prod"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output"),
) -> None:
    """Tail CloudWatch logs for the deployed Lambda."""
    ensure_config_exists()
    ensure_terraform_init()

    terraform_dir = get_terraform_dir()
    select_workspace(env, terraform_dir)

    # Try terraform output first
    log_group = ""
    result = subprocess.run(
        ["terraform", "output", "-raw", "cloudwatch_log_group"],
        cwd=terraform_dir,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0 and result.stdout.strip():
        log_group = result.stdout.strip()

    if not log_group:
        tfvars = load_tfvars(env)
        lambda_name = tfvars.get("lambda_name", "")
        if not lambda_name:
            console.print(
                "[red]Could not determine log group name.[/red]\n"
                "Ensure the Lambda has been deployed with [bold]opencontext deploy[/bold]."
            )
            raise typer.Exit(1)
        log_group = f"/aws/lambda/{lambda_name}"

    console.print(f"[bold]Log group:[/bold] {log_group}\n")

    cmd = ["aws", "logs", "tail", log_group]
    if follow:
        cmd.append("--follow")

    exit_code = run_cmd_stream(cmd)
    if exit_code != 0:
        console.print("[red]Failed to tail logs.[/red] Is the Lambda deployed?")
        raise typer.Exit(1)
