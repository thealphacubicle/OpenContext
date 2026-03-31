from __future__ import annotations

import questionary
import typer

from cli.utils import (
    console,
    ensure_config_exists,
    ensure_terraform_init,
    friendly_exit,
    get_terraform_dir,
    require_tty,
    run_cmd_stream,
    select_workspace,
    workspace_name,
)


@friendly_exit
def destroy(
    env: str = typer.Option("staging", help="Environment: staging or prod"),
) -> None:
    """Destroy all deployed resources for an environment."""
    require_tty()

    ensure_config_exists()
    ensure_terraform_init()

    terraform_dir = get_terraform_dir()
    ws = workspace_name(env)

    tfvars_file = terraform_dir / f"{env}.tfvars"
    if not tfvars_file.exists():
        console.print(
            f"[red]{env}.tfvars not found in terraform/aws/.[/red]\n"
            "Nothing to destroy — this environment has not been configured."
        )
        raise typer.Exit(1)

    select_workspace(env, terraform_dir)

    console.print(f"\n[red bold]WARNING: This will destroy ALL resources in workspace '{ws}'.[/red bold]")
    console.print(f"Environment: [bold]{env}[/bold]")
    console.print(f"Var file:    [bold]{env}.tfvars[/bold]\n")

    confirmation = questionary.text(
        f'Type "{env}" to confirm destruction:'
    ).ask()

    if confirmation is None or confirmation != env:
        console.print("[yellow]Destruction cancelled.[/yellow]")
        raise typer.Exit(0)

    console.print("\n[bold]Destroying resources...[/bold]\n")
    exit_code = run_cmd_stream(
        [
            "terraform", "destroy",
            f"-var-file={env}.tfvars",
            "-input=false",
            "-auto-approve",
        ],
        cwd=terraform_dir,
    )

    if exit_code != 0:
        console.print("[red]Terraform destroy failed.[/red]")
        raise typer.Exit(1)

    console.print("\n[green bold]All resources destroyed.[/green bold]")
