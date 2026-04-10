from __future__ import annotations

import json
import shutil
import subprocess
import sys

from rich.table import Table

from cli.utils import console, friendly_exit


def _is_available(cmd: list[str], timeout: int = 10) -> subprocess.CompletedProcess | None:
    """Run a command and return the result if successful, None otherwise."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode == 0:
            return result
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def _auto_install(package: str, installer: list[str], label: str) -> bool:
    """Attempt to auto-install a package. Returns True on success."""
    console.print(f"  [yellow]Auto-installing {label}...[/yellow]")
    try:
        result = subprocess.run(
            installer,
            capture_output=True,
            text=True,
            timeout=120,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _find_pip() -> list[str] | None:
    """Find a working pip command (pip3 or pip)."""
    for candidate in ["pip3", "pip"]:
        if shutil.which(candidate):
            return [candidate]
    return None


@friendly_exit
def authenticate() -> None:
    """Check all prerequisites and print a status table."""
    checks: list[tuple[str, bool, str]] = []

    # --- 1. Python >= 3.11 (cannot auto-install) ---
    major, minor, micro = sys.version_info[:3]
    py_version = f"{major}.{minor}.{micro}"
    if (major, minor) >= (3, 11):
        checks.append(("Python >= 3.11", True, f"Python {py_version}"))
    else:
        checks.append((
            "Python >= 3.11", False,
            f"Found {py_version}. Install 3.11+: https://www.python.org/downloads/",
        ))

    # --- 2. uv (auto-install via pip if missing) ---
    result = _is_available(["uv", "--version"])
    if result:
        checks.append(("uv", True, result.stdout.strip()))
    else:
        pip_cmd = _find_pip()
        installed = False
        if pip_cmd:
            installed = _auto_install("uv", [*pip_cmd, "install", "uv"], "uv")
            if installed:
                result = _is_available(["uv", "--version"])
                if result:
                    checks.append(("uv", True, f"{result.stdout.strip()} (auto-installed)"))
                else:
                    installed = False

        if not installed:
            checks.append((
                "uv", False,
                "Install: https://docs.astral.sh/uv/getting-started/installation/",
            ))

    uv_available = shutil.which("uv") is not None

    # --- 3. AWS CLI (auto-install via uv/pip if missing) ---
    result = _is_available(["aws", "--version"])
    if result:
        version = result.stdout.strip().split()[0] if result.stdout.strip() else "installed"
        checks.append(("AWS CLI", True, version))
    else:
        installed = False
        if uv_available:
            installed = _auto_install("awscli", ["uv", "pip", "install", "awscli"], "AWS CLI via uv")
        if not installed:
            pip_cmd = _find_pip()
            if pip_cmd:
                installed = _auto_install("awscli", [*pip_cmd, "install", "awscli"], "AWS CLI via pip")

        if installed:
            result = _is_available(["aws", "--version"])
            if result:
                version = result.stdout.strip().split()[0] if result.stdout.strip() else "installed"
                checks.append(("AWS CLI", True, f"{version} (auto-installed)"))
            else:
                installed = False

        if not installed:
            checks.append((
                "AWS CLI", False,
                "Install: https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html",
            ))

    # --- 4. AWS credentials (cannot auto-install) ---
    result = _is_available(["aws", "sts", "get-caller-identity"], timeout=15)
    if result:
        try:
            identity = json.loads(result.stdout)
            checks.append(("AWS Credentials", True, f"Account: {identity.get('Account', 'unknown')}"))
        except json.JSONDecodeError:
            checks.append(("AWS Credentials", False, "Run: aws configure"))
    else:
        checks.append(("AWS Credentials", False, "Run: aws configure"))

    # --- 5. Terraform (cannot auto-install — binary download required) ---
    result = _is_available(["terraform", "--version"])
    if result:
        version_line = result.stdout.strip().splitlines()[0] if result.stdout.strip() else "installed"
        checks.append(("Terraform", True, version_line))
    else:
        checks.append(("Terraform", False, "Install: https://www.terraform.io/downloads"))

    # --- Print results ---
    table = Table(title="OpenContext Prerequisites")
    table.add_column("Check", style="bold")
    table.add_column("Status", justify="center")
    table.add_column("Details")

    all_passed = True
    for name, passed, detail in checks:
        status = "[green]✅ Pass[/green]" if passed else "[red]❌ Fail[/red]"
        if not passed:
            all_passed = False
        table.add_row(name, status, detail)

    console.print()
    console.print(table)
    console.print()

    if all_passed:
        console.print("[green bold]All checks passed![/green bold] You're ready to go.")
    else:
        console.print("[yellow]Some checks failed.[/yellow] Fix the issues above, then re-run [bold]opencontext authenticate[/bold].")
        raise SystemExit(1)
