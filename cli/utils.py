from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import click
import typer
import yaml
from rich.console import Console

console = Console()


def get_project_root() -> Path:
    """Walk up from this file to find the directory containing pyproject.toml."""
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / "pyproject.toml").exists():
            return current
        current = current.parent
    console.print("[red]Could not locate project root (no pyproject.toml found).[/red]")
    raise typer.Exit(1)


def get_terraform_dir() -> Path:
    return get_project_root() / "terraform" / "aws"


def load_config() -> dict:
    """Parse config.yaml from the project root and return the dict."""
    config_path = get_project_root() / "config.yaml"
    if not config_path.exists():
        console.print(
            "[red]config.yaml not found.[/red]\n"
            "Run [bold]opencontext configure[/bold] to create one."
        )
        raise typer.Exit(1)
    with open(config_path) as f:
        return yaml.safe_load(f)


def load_tfvars(env: str) -> dict[str, str]:
    """Parse terraform/aws/{env}.tfvars into a dict of key=value pairs."""
    tfvars_path = get_terraform_dir() / f"{env}.tfvars"
    if not tfvars_path.exists():
        console.print(
            f"[red]{env}.tfvars not found in terraform/aws/.[/red]\n"
            "Run [bold]opencontext configure[/bold] to generate it."
        )
        raise typer.Exit(1)
    result: dict[str, str] = {}
    with open(tfvars_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            match = re.match(r'^(\w+)\s*=\s*"(.*)"$', line)
            if match:
                result[match.group(1)] = match.group(2)
            else:
                num_match = re.match(r"^(\w+)\s*=\s*(\d+)$", line)
                if num_match:
                    result[num_match.group(1)] = num_match.group(2)
    return result


def ensure_config_exists() -> None:
    config_path = get_project_root() / "config.yaml"
    if not config_path.exists():
        console.print(
            "[red]config.yaml not found.[/red]\n"
            "Run [bold]opencontext configure[/bold] to create one."
        )
        raise typer.Exit(1)


def ensure_terraform_init() -> None:
    tf_dir = get_terraform_dir()
    if not (tf_dir / ".terraform").exists():
        console.print(
            "[red]Terraform has not been initialized.[/red]\n"
            "Run [bold]opencontext configure[/bold] to initialize it."
        )
        raise typer.Exit(1)


def require_tty() -> None:
    """Abort if stdin is not a TTY — destructive commands require interactive approval."""
    if not sys.stdin.isatty():
        console.print(
            "[red]This command requires interactive approval and cannot be run non-interactively.[/red]"
        )
        raise typer.Exit(1)


def get_city_name() -> str:
    """Extract a lowercase, hyphen-separated city name from config.yaml for workspace naming."""
    config = load_config()
    for plugin_cfg in config.get("plugins", {}).values():
        if isinstance(plugin_cfg, dict) and plugin_cfg.get("enabled"):
            city = plugin_cfg.get("city_name", "")
            if city:
                return city.lower().replace(" ", "-")
    org = config.get("organization", "")
    if org:
        return org.lower().replace(" ", "-").replace("city-of-", "")
    return "opencontext"


def workspace_name(env: str) -> str:
    city = get_city_name()
    return f"{city}-{env}"


def select_workspace(env: str, terraform_dir: Path | None = None) -> None:
    """Select (or create) the Terraform workspace for the given environment."""
    tf_dir = terraform_dir or get_terraform_dir()
    ws = workspace_name(env)

    result = subprocess.run(
        ["terraform", "workspace", "list"],
        cwd=tf_dir,
        capture_output=True,
        text=True,
        timeout=15,
    )
    existing = [w.strip().lstrip("* ") for w in result.stdout.splitlines()]

    if ws in existing:
        run_cmd(
            ["terraform", "workspace", "select", ws],
            cwd=tf_dir,
            spinner_msg=f"Selecting workspace [bold]{ws}[/bold]",
        )
    else:
        run_cmd(
            ["terraform", "workspace", "new", ws],
            cwd=tf_dir,
            spinner_msg=f"Creating workspace [bold]{ws}[/bold]",
        )


def run_cmd(
    args: list[str],
    *,
    cwd: Path | str | None = None,
    spinner_msg: str = "Running",
    capture: bool = True,
    timeout: int | None = 300,
) -> subprocess.CompletedProcess[str]:
    """Run a subprocess with a rich spinner. On failure, print stderr and exit."""
    with console.status(spinner_msg):
        try:
            result = subprocess.run(
                args,
                cwd=cwd,
                capture_output=capture,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            console.print(
                f"[red]Command timed out after {timeout}s:[/red] {' '.join(args)}"
            )
            raise typer.Exit(1)
    if result.returncode != 0:
        console.print(f"[red]Command failed:[/red] {' '.join(args)}")
        if capture and result.stderr:
            console.print(result.stderr.strip())
        raise typer.Exit(1)
    return result


def run_cmd_stream(
    args: list[str],
    *,
    cwd: Path | str | None = None,
) -> int:
    """Stream stdout/stderr live. Returns the exit code."""
    process = subprocess.Popen(
        args,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    assert process.stdout is not None
    for line in process.stdout:
        console.print(line, end="", highlight=False)
    return process.wait()


def run_cmd_stream_capture(
    args: list[str],
    *,
    cwd: Path | str | None = None,
) -> tuple[int, str]:
    """Stream stdout/stderr live and capture it. Returns (exit_code, output)."""
    process = subprocess.Popen(
        args,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    assert process.stdout is not None
    lines: list[str] = []
    for line in process.stdout:
        console.print(line, end="", highlight=False)
        lines.append(line)
    return process.wait(), "".join(lines)


def friendly_exit(func):
    """Decorator that catches exceptions and prints a user-friendly error."""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (SystemExit, click.exceptions.Exit):
            raise
        except Exception as exc:
            console.print(f"\n[red bold]Error:[/red bold] {exc}")
            raise typer.Exit(1) from None
    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    wrapper.__module__ = func.__module__
    wrapper.__wrapped__ = func
    return wrapper
