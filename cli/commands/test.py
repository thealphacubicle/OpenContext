from __future__ import annotations

import json
import subprocess
import time
from typing import Any

import httpx
import typer
from rich.table import Table

from cli.utils import (
    console,
    get_terraform_dir,
    load_tfvars,
    select_workspace,
)

app = typer.Typer()

MCP_PATH = "/mcp"


def _get_api_url(env: str) -> str | None:
    """Get the API Gateway URL from terraform output."""
    terraform_dir = get_terraform_dir()
    try:
        select_workspace(env, terraform_dir)
        result = subprocess.run(
            ["terraform", "output", "-raw", "api_gateway_url"],
            cwd=terraform_dir,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().rstrip("/")
    except Exception:
        pass
    return None


def _get_custom_domain_url(env: str) -> str | None:
    """Return the custom domain URL if set and cert is ISSUED."""
    try:
        tfvars = load_tfvars(env)
        custom_domain = tfvars.get("custom_domain", "")
        if not custom_domain:
            return None

        result = subprocess.run(
            ["aws", "acm", "list-certificates", "--output", "json"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            certs = json.loads(result.stdout).get("CertificateSummaryList", [])
            for cert in certs:
                if cert.get("DomainName") == custom_domain and cert.get("Status") == "ISSUED":
                    return f"https://{custom_domain}"
    except Exception:
        pass
    return None


def _post_mcp(client: httpx.Client, base_url: str, payload: dict) -> tuple[bool, float, Any]:
    """Send a JSON-RPC POST to /mcp. Returns (success, elapsed_ms, response_body)."""
    start = time.monotonic()
    try:
        response = client.post(
            f"{base_url}{MCP_PATH}",
            json=payload,
            timeout=15.0,
        )
        elapsed_ms = (time.monotonic() - start) * 1000
        try:
            body = response.json()
        except Exception:
            body = response.text
        return response.status_code < 500, elapsed_ms, body
    except httpx.TimeoutException:
        elapsed_ms = (time.monotonic() - start) * 1000
        return False, elapsed_ms, "Timeout"
    except Exception as e:
        elapsed_ms = (time.monotonic() - start) * 1000
        return False, elapsed_ms, str(e)


def _run_tests(base_url: str) -> tuple[int, int]:
    """Run all MCP endpoint tests against base_url. Returns (passed, total)."""
    console.print(f"\n[bold]Testing:[/bold] {base_url}\n")

    results: list[tuple[str, bool, float, str]] = []

    with httpx.Client() as client:
        # 1. Ping
        ok, ms, body = _post_mcp(client, base_url, {
            "jsonrpc": "2.0", "id": 1, "method": "ping",
        })
        results.append(("Ping", ok, ms, _summarize(body)))

        # 2. Initialize
        ok, ms, body = _post_mcp(client, base_url, {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "opencontext-cli", "version": "1.0.0"},
            },
        })
        results.append(("Initialize", ok, ms, _summarize(body)))

        # 3. List tools
        ok, ms, body = _post_mcp(client, base_url, {
            "jsonrpc": "2.0", "id": 3, "method": "tools/list",
        })
        results.append(("List tools", ok, ms, _summarize(body)))

        # 4. Call first available tool with minimal args
        first_tool: str | None = None
        if ok and isinstance(body, dict):
            tools_list = body.get("result", {})
            if isinstance(tools_list, dict):
                tools_list = tools_list.get("tools", [])
            if isinstance(tools_list, list) and tools_list:
                first_tool = tools_list[0].get("name") if isinstance(tools_list[0], dict) else None

        if first_tool:
            ok, ms, body = _post_mcp(client, base_url, {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {"name": first_tool, "arguments": {}},
            })
            # Accept either a result or a validation error (not a 500-level failure)
            results.append((f"Call tool: {first_tool}", ok, ms, _summarize(body)))
        else:
            results.append(("Call first tool", False, 0.0, "No tools returned from list"))

    table = Table(show_lines=True)
    table.add_column("Test", style="bold")
    table.add_column("Status", justify="center", width=10)
    table.add_column("Time (ms)", justify="right", width=10)
    table.add_column("Response")

    passed = 0
    for test_name, ok, ms, summary in results:
        status_cell = "[green]✅ Pass[/green]" if ok else "[red]❌ Fail[/red]"
        if ok:
            passed += 1
        table.add_row(
            test_name,
            status_cell,
            f"{ms:.0f}",
            summary,
        )

    console.print(table)

    total = len(results)
    color = "green" if passed == total else "red"
    console.print(f"\n[{color}]Results: {passed}/{total} passed[/{color}]")
    return passed, total


def _summarize(body: Any) -> str:
    """Produce a short summary of the response body."""
    if isinstance(body, str):
        return body[:80]
    if isinstance(body, dict):
        if "error" in body:
            err = body["error"]
            msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
            return f"error: {msg[:60]}"
        if "result" in body:
            result = body["result"]
            if isinstance(result, dict):
                keys = list(result.keys())
                return f"result keys: {keys[:4]}"
            return f"result: {str(result)[:60]}"
    return str(body)[:80]


@app.callback(invoke_without_command=True)
def test(
    ctx: typer.Context,
    env: str = typer.Option("staging", help="Environment: staging or prod"),
    url: str = typer.Option(None, "--url", help="Override URL to test against"),
) -> None:
    """Test the deployed MCP server endpoints."""
    if ctx.invoked_subcommand is not None:
        return

    total_passed = 0
    total_tests = 0
    exit_ok = True

    if url:
        base_url = url.rstrip("/")
        passed, total = _run_tests(base_url)
        total_passed += passed
        total_tests += total
        if passed < total:
            exit_ok = False
    else:
        with console.status("Fetching deployment URL from Terraform..."):
            base_url = _get_api_url(env)

        if not base_url:
            console.print(
                "[red]Could not retrieve API Gateway URL from Terraform output.[/red]\n"
                "Ensure the Lambda has been deployed with [bold]opencontext deploy[/bold]."
            )
            raise typer.Exit(1)

        passed, total = _run_tests(base_url)
        total_passed += passed
        total_tests += total
        if passed < total:
            exit_ok = False

        # Also test custom domain if cert is ISSUED
        with console.status("Checking for custom domain..."):
            custom_url = _get_custom_domain_url(env)

        if custom_url:
            console.print(f"\n[bold]Also testing custom domain:[/bold] {custom_url}")
            passed2, total2 = _run_tests(custom_url)
            total_passed += passed2
            total_tests += total2
            if passed2 < total2:
                exit_ok = False

    if not exit_ok:
        raise typer.Exit(1)
