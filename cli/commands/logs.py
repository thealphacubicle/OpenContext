from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field

import typer
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from cli.utils import (
    console,
    ensure_config_exists,
    ensure_terraform_init,
    friendly_exit,
    get_terraform_dir,
    load_tfvars,
    select_workspace,
)

# aws logs tail --format detailed line format: <timestamp> <stream> <message>
_LINE_RE = re.compile(r"^\S+\s+\S+\s+(.+)$")
_TIMESTAMP_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}T[\d:.+]+)")
_START_RE = re.compile(r"^START RequestId: (\S+)")
_END_RE = re.compile(r"^END RequestId: (\S+)")
_REPORT_RE = re.compile(r"^REPORT RequestId: (\S+)\s+Duration: ([\d.]+) ms")
_ERROR_RE = re.compile(r"\[ERROR\]|ERROR\b|Exception:|Traceback", re.IGNORECASE)


@dataclass
class Invocation:
    request_id: str
    timestamp: str = ""
    duration_ms: float | None = None
    has_error: bool = False
    lines: list[str] = field(default_factory=list)


def _extract(raw_line: str) -> tuple[str, str]:
    """Return (timestamp, message) from a raw aws logs tail line."""
    ts = _TIMESTAMP_RE.match(raw_line)
    timestamp = ts.group(1) if ts else ""
    m = _LINE_RE.match(raw_line)
    msg = m.group(1) if m else raw_line
    return timestamp, msg


def _parse_logs(raw_output: str) -> list[Invocation]:
    invocations: dict[str, Invocation] = {}
    order: list[str] = []
    current_id: str | None = None

    for raw_line in raw_output.splitlines():
        timestamp, msg = _extract(raw_line)

        if start := _START_RE.match(msg):
            rid = start.group(1)
            invocations[rid] = Invocation(request_id=rid, timestamp=timestamp)
            order.append(rid)
            current_id = rid
        elif _END_RE.match(msg):
            pass
        elif report := _REPORT_RE.match(msg):
            rid = report.group(1)
            if rid in invocations:
                invocations[rid].duration_ms = float(report.group(2))
        else:
            if current_id and current_id in invocations:
                invocations[current_id].lines.append(msg)
                if _ERROR_RE.search(msg):
                    invocations[current_id].has_error = True

    return [invocations[rid] for rid in order if rid in invocations]


def _print_summary(invocations: list[Invocation], log_group: str, since: str) -> None:
    total = len(invocations)
    errors = sum(1 for inv in invocations if inv.has_error)
    durations = [inv.duration_ms for inv in invocations if inv.duration_ms is not None]
    avg_ms = sum(durations) / len(durations) if durations else None

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(style="bold cyan", min_width=16)
    table.add_column()

    table.add_row("Log group", log_group)
    table.add_row("Time range", f"last {since}")
    table.add_row("Invocations", str(total))
    table.add_row("Errors", f"[red]{errors}[/red]" if errors else "0")
    if avg_ms is not None:
        table.add_row("Avg duration", f"{avg_ms:.1f} ms")

    console.print(table)

    if invocations and not any(inv.duration_ms for inv in invocations):
        console.print("\n[dim]Tip: run with --verbose to see full log entries.[/dim]")
    elif invocations:
        console.print("\n[dim]Tip: run with --verbose to see full log entries.[/dim]")


def _print_verbose(invocations: list[Invocation], log_group: str) -> None:
    console.print(f"[bold]Log group:[/bold] {log_group}\n")

    if not invocations:
        console.print("[dim]No invocations found.[/dim]")
        return

    for inv in invocations:
        status_markup = "[red]ERROR[/red]" if inv.has_error else "[green]OK[/green]"
        duration_str = f"{inv.duration_ms:.1f} ms" if inv.duration_ms is not None else "—"
        ts = inv.timestamp[:19].replace("T", " ") if inv.timestamp else "—"

        header = Text.assemble(
            (ts, "dim"),
            "  ",
            (f"#{inv.request_id[:8]}", "bold"),
            "  ",
            (duration_str, "cyan"),
            "  ",
        )
        header.append_text(Text.from_markup(status_markup))

        body_lines = []
        for line in inv.lines:
            if _ERROR_RE.search(line):
                body_lines.append(f"[red]{line}[/red]")
            else:
                body_lines.append(f"[dim]{line}[/dim]")

        body = "\n".join(body_lines) if body_lines else "[dim](no log output)[/dim]"
        console.print(header)
        console.print(Panel(body, border_style="dim", padding=(0, 1)))
        console.print()


def run_cmd_stream(cmd: list[str]) -> int:
    """Stream log lines with error/START highlighting."""
    process = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )
    assert process.stdout is not None
    for raw_line in process.stdout:
        raw_line = raw_line.rstrip("\n")
        _, msg = _extract(raw_line)
        if _START_RE.match(msg):
            console.print(f"\n[bold cyan]{msg}[/bold cyan]")
        elif _END_RE.match(msg) or _REPORT_RE.match(msg):
            console.print(f"[dim]{msg}[/dim]")
        elif _ERROR_RE.search(msg):
            console.print(f"[red]{msg}[/red]")
        else:
            console.print(msg, highlight=False)
    return process.wait()


@friendly_exit
def logs(
    env: str = typer.Option("staging", help="Environment: staging or prod"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show formatted log entries"),
    since: str = typer.Option("1h", "--since", help="How far back to fetch logs (e.g. 1h, 30m, 24h)"),
) -> None:
    """Show CloudWatch logs for the deployed Lambda."""
    ensure_config_exists()
    ensure_terraform_init()

    terraform_dir = get_terraform_dir()
    select_workspace(env, terraform_dir)

    log_group = ""
    result = subprocess.run(
        ["terraform", "output", "-raw", "cloudwatch_log_group"],
        cwd=terraform_dir,
        capture_output=True,
        text=True,
        timeout=15,
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

    cmd = ["aws", "logs", "tail", log_group, "--since", since, "--format", "detailed"]

    if follow:
        cmd = cmd + ["--follow"]

    if verbose is True:
        # Capture output for structured display
        with console.status("Fetching logs…"):
            result = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                timeout=30,
            )
        if result.returncode != 0:
            console.print("[red]Failed to fetch logs.[/red] Is the Lambda deployed?")
            raise typer.Exit(1)
        invocations = _parse_logs(result.stdout)
        _print_verbose(invocations, log_group)
        return

    exit_code = run_cmd_stream(cmd)
    if exit_code != 0:
        console.print("[red]Failed to tail logs.[/red] Is the Lambda deployed?")
        raise typer.Exit(1)
