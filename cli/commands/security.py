from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path

import typer
from rich.table import Table

from cli.utils import console, get_project_root

app = typer.Typer()

# pip-audit JSON schema (--format json):
#   {"dependencies": [{"name", "version", "vulns": [{"id", "fix_versions", "aliases", "description"}]}], "fixes": [...]}
# Aliases are plain strings such as "CVE-2024-1234" or "GHSA-xxxx-xxxx-xxxx".
# pip-audit does not emit a severity field; we infer it from the ID prefix.

_SEVERITY_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
_SEVERITY_STYLE: dict[str, str] = {
    "CRITICAL": "bold red",
    "HIGH": "red",
    "MEDIUM": "yellow",
    "LOW": "cyan",
}


def _infer_severity(vuln_id: str, aliases: list[str]) -> str:
    """Infer a severity bucket from a vuln id and its aliases.

    pip-audit's JSON format does not include severity scores, so we use a
    simple heuristic: any finding with a CVE alias is treated as HIGH, and
    GHSA-only findings are treated as MEDIUM.  This mirrors the behaviour
    used by the existing CI pip-audit invocation (which flags anything found
    as a blocker regardless of severity).
    """
    all_ids = [vuln_id] + aliases
    has_cve = any(i.startswith("CVE-") for i in all_ids)
    return "HIGH" if has_cve else "MEDIUM"


def _flatten_vulns(dependencies: list[dict]) -> list[dict]:
    """Flatten the pip-audit dependency list into a flat list of finding dicts.

    Each finding dict has:
        package, installed_version, vuln_id, cve_ids, fix_versions,
        description, severity
    """
    findings: list[dict] = []
    for dep in dependencies:
        # Skipped deps have no "version" or "vulns" key.
        if "vulns" not in dep:
            continue
        package = dep.get("name", "unknown")
        version = dep.get("version", "unknown")
        for vuln in dep["vulns"]:
            vuln_id: str = vuln.get("id", "")
            aliases: list[str] = vuln.get("aliases", [])
            cve_ids = [a for a in aliases if a.startswith("CVE-")]
            fix_versions: list[str] = vuln.get("fix_versions", [])
            description: str = vuln.get("description", "")
            findings.append(
                {
                    "package": package,
                    "installed_version": version,
                    "vuln_id": vuln_id,
                    "cve_ids": cve_ids,
                    "fix_versions": fix_versions,
                    "description": description,
                    "severity": _infer_severity(vuln_id, aliases),
                }
            )
    return findings


def _run_pip_audit(project_root: Path) -> list[dict]:
    """Run pip-audit --format json and return the parsed dependency list.

    Returns the raw ``dependencies`` list from pip-audit's JSON output.
    The caller is responsible for flattening it into individual findings.

    Raises:
        FileNotFoundError: pip-audit binary not found on PATH.
        subprocess.TimeoutExpired: audit took longer than 120 s.
        json.JSONDecodeError: pip-audit output could not be parsed.
        RuntimeError: pip-audit exited with an unexpected error code.
    """
    cmd = [
        "uv",
        "run",
        "pip-audit",
        "--format",
        "json",
        "--progress-spinner",
        "off",
        "--desc",
        "--aliases",
        "--local",
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=120,
    )

    # pip-audit exits 1 when vulnerabilities are found — that is expected.
    # Anything else with no output is a genuine tool error.
    stdout = result.stdout.strip()
    if not stdout:
        stderr = result.stderr.strip()
        hint = f"\n\nOutput: {stderr}" if stderr else ""
        raise RuntimeError(
            f"pip-audit did not return any results (exit code {result.returncode}).{hint}\n\n"
            "Check that pip-audit is installed and working:\n"
            "  uv run pip-audit --format json --local"
        )

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        preview = stdout[:200] + ("..." if len(stdout) > 200 else "")
        raise RuntimeError(
            f"pip-audit returned output that could not be read.\n\nOutput: {preview}\n\n"
            "Try running [bold]pip-audit --format json[/bold] manually to diagnose."
        )
    return data.get("dependencies", [])


def _print_report(findings: list[dict]) -> None:
    """Render the security report to the terminal using Rich."""
    console.print()

    if not findings:
        console.print("[green bold]All clear — no vulnerabilities found.[/green bold]")
        console.print()
        return

    # Group by severity, preserving display order
    grouped: dict[str, list[dict]] = {s: [] for s in _SEVERITY_ORDER}
    for f in findings:
        bucket = f["severity"] if f["severity"] in grouped else "MEDIUM"
        grouped[bucket].append(f)

    for severity in _SEVERITY_ORDER:
        group = grouped[severity]
        if not group:
            continue

        style = _SEVERITY_STYLE[severity]
        table = Table(
            title=f"[{style}]{severity}[/{style}] ({len(group)})",
            show_lines=True,
        )
        table.add_column("Package", style="bold")
        table.add_column("Installed", justify="center")
        table.add_column("Fixed In", justify="center")
        table.add_column("ID")
        table.add_column("CVEs")
        table.add_column("Description")

        for f in group:
            fix_str = (
                ", ".join(f["fix_versions"]) if f["fix_versions"] else "[dim]None[/dim]"
            )
            cve_str = ", ".join(f["cve_ids"]) if f["cve_ids"] else "[dim]N/A[/dim]"
            desc = f["description"]
            if len(desc) > 120:
                desc = desc[:117] + "..."
            table.add_row(
                f["package"],
                f["installed_version"],
                fix_str,
                f["vuln_id"],
                cve_str,
                desc or "[dim]—[/dim]",
            )

        console.print(table)
        console.print()

    # Summary line
    total = len(findings)
    counts = {s: len(grouped[s]) for s in _SEVERITY_ORDER}
    count_parts = [
        f"[{_SEVERITY_STYLE[s]}]{counts[s]} {s.capitalize()}[/{_SEVERITY_STYLE[s]}]"
        for s in _SEVERITY_ORDER
        if counts[s] > 0
    ]
    noun = "vulnerability" if total == 1 else "vulnerabilities"
    console.print(f"[bold]{total} {noun} found:[/bold] " + ", ".join(count_parts))
    console.print()


def _export_report(findings: list[dict], project_root: Path) -> Path:
    """Write the findings list to a timestamped .txt file.

    Returns the path of the written file.
    """
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output_path = project_root / f"security-report-{timestamp}.txt"

    lines: list[str] = [
        "OpenContext Security Report",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "=" * 60,
        "",
    ]

    grouped: dict[str, list[dict]] = {s: [] for s in _SEVERITY_ORDER}
    for f in findings:
        bucket = f["severity"] if f["severity"] in grouped else "MEDIUM"
        grouped[bucket].append(f)

    for severity in _SEVERITY_ORDER:
        group = grouped[severity]
        if not group:
            continue
        lines.append(f"[{severity}]")
        lines.append("-" * 40)
        for f in group:
            fix_str = (
                ", ".join(f["fix_versions"]) if f["fix_versions"] else "None available"
            )
            cve_str = ", ".join(f["cve_ids"]) if f["cve_ids"] else "N/A"
            lines.append(f"  Package:   {f['package']}")
            lines.append(f"  Installed: {f['installed_version']}")
            lines.append(f"  Fixed In:  {fix_str}")
            lines.append(f"  ID:        {f['vuln_id']}")
            lines.append(f"  CVEs:      {cve_str}")
            if f["description"]:
                lines.append(f"  Desc:      {f['description']}")
            lines.append("")
        lines.append("")

    lines.append("=" * 60)
    total = len(findings)
    if total == 0:
        lines.append("Result: No vulnerabilities found.")
    else:
        counts = {s: len(grouped[s]) for s in _SEVERITY_ORDER if grouped[s]}
        count_parts = [f"{v} {k.capitalize()}" for k, v in counts.items()]
        noun = "vulnerability" if total == 1 else "vulnerabilities"
        lines.append(f"Result: {total} {noun} found: {', '.join(count_parts)}")

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path


@app.callback(invoke_without_command=True)
def security(
    ctx: typer.Context,
    export: bool = typer.Option(
        False,
        "--export/--no-export",
        help="Write the report to a file (security-report-<timestamp>.txt)",
    ),
) -> None:
    """Run a security audit of all packages and dependencies."""
    if ctx.invoked_subcommand is not None:
        return

    project_root = get_project_root()

    with console.status("Running pip-audit..."):
        try:
            dependencies = _run_pip_audit(project_root)
        except FileNotFoundError:
            console.print(
                "[red bold]Could not run the security audit.[/red bold]\n\n"
                "Make sure uv is installed and pip-audit is a project dependency:\n"
                "  [bold]uv add --dev pip-audit[/bold]"
            )
            raise typer.Exit(1)
        except subprocess.TimeoutExpired:
            console.print(
                "[red bold]Security audit timed out.[/red bold]\n\n"
                "pip-audit took longer than 120 seconds. This can happen on slow networks "
                "or when the PyPI vulnerability database is unavailable. Try again shortly."
            )
            raise typer.Exit(1)
        except RuntimeError as exc:
            console.print(f"[red bold]Security audit failed.[/red bold]\n\n{exc}")
            raise typer.Exit(1)

    findings = _flatten_vulns(dependencies)
    _print_report(findings)

    if export:
        output_path = _export_report(findings, project_root)
        console.print(f"[dim]Report saved to:[/dim] {output_path}")
        console.print()

    if findings:
        raise typer.Exit(1)
