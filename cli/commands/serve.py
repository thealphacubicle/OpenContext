"""CLI command: opencontext serve — run the local dev MCP server."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from pathlib import Path

import typer
import yaml
from aiohttp import web

from cli.utils import console
from core.logging_utils import configure_json_logging
from core.mcp_server import MCPServer
from core.plugin_manager import PluginManager
from core.validators import get_logging_config

app = typer.Typer()

logger = logging.getLogger(__name__)


def _load_config(config_path: str) -> tuple[dict, Path]:
    """Load YAML config from *config_path*, raising a clear error if missing."""
    resolved = Path(config_path).resolve()
    if not resolved.exists():
        console.print(f"[red]Config file not found:[/red] {resolved}")
        raise typer.Exit(1)
    with open(resolved) as f:
        return yaml.safe_load(f), resolved


def _derive_server_name(config: dict) -> str:
    """Derive a short server name from the active plugin config."""
    if "plugins" in config:
        for plugin_name, plugin_config in config["plugins"].items():
            if not isinstance(plugin_config, dict):
                continue
            if plugin_config.get("enabled"):
                if "city_name" in plugin_config:
                    city = plugin_config["city_name"].lower().replace(" ", "-")
                    return f"{city}-opendata"
                if "organization" in plugin_config:
                    org = plugin_config["organization"].lower().replace(" ", "-")
                    return f"{org}-opendata"

    if "aws" in config and "lambda_name" in config["aws"]:
        return config["aws"]["lambda_name"].replace("-mcp", "")

    if "server_name" in config:
        return config["server_name"].lower().replace(" ", "-").replace("'", "")

    return "opencontext-mcp"


async def _run_server(config: dict, port: int) -> None:
    """Initialise the plugin manager and MCP server, then serve until Ctrl+C."""
    # Configure JSON logging with pretty output for local dev
    logging_config = get_logging_config(config)
    configure_json_logging(
        level=logging_config.get("level", "INFO"),
        pretty=True,
    )

    console.print("Initializing OpenContext MCP Server locally...")

    plugin_manager = PluginManager(config)
    await plugin_manager.load_plugins()

    mcp_server = MCPServer(plugin_manager)

    console.print("Server initialized successfully")
    console.print(f"Loaded plugins: {list(plugin_manager.plugins.keys())}")
    console.print(f"Available tools: {len(plugin_manager.get_all_tools())}")

    async def handle_mcp_request(request: web.Request) -> web.Response:
        start_time = time.perf_counter()
        try:
            body = await request.text()
            headers = dict(request.headers)

            session_id = headers.get("mcp-session-id") or headers.get("Mcp-Session-Id")

            try:
                request_json = json.loads(body)
                method = request_json.get("method", "unknown")
                tool_name = None
                tool_args = None
                if method == "tools/call":
                    params = request_json.get("params", {})
                    tool_name = params.get("name")
                    tool_args = params.get("arguments", {})
            except (json.JSONDecodeError, AttributeError):
                method = "unknown"
                tool_name = None
                tool_args = None

            logger.info(
                "Incoming MCP request",
                extra={
                    "session_id": session_id,
                    "method": method,
                    "tool_name": tool_name,
                    "tool_arguments": tool_args if tool_args else None,
                },
            )

            is_initialize = method == "initialize"
            session_id_to_return = None
            if is_initialize:
                session_id_to_return = str(uuid.uuid4())
                logger.info(
                    f"Initialize request detected, generating session ID: {session_id_to_return}"
                )

            response = await mcp_server.handle_http_request(body, headers)

            response_headers = dict(response.get("headers", {}))
            if session_id_to_return:
                response_headers["Mcp-Session-Id"] = session_id_to_return

            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.info(
                "MCP request processed",
                extra={
                    "session_id": session_id_to_return or session_id,
                    "method": method,
                    "tool_name": tool_name,
                    "duration_ms": round(duration_ms, 2),
                    "status_code": response.get("statusCode", 200),
                },
            )

            return web.Response(
                text=response.get("body", "{}"),
                status=response.get("statusCode", 200),
                headers=response_headers,
            )

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                f"Error processing MCP request: {e}",
                extra={"duration_ms": round(duration_ms, 2)},
                exc_info=True,
            )
            return web.Response(
                text=json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {"code": -32603, "message": str(e)},
                    }
                ),
                status=500,
                headers={"Content-Type": "application/json"},
            )

    aiohttp_app = web.Application()
    aiohttp_app.router.add_post("/mcp", handle_mcp_request)

    runner = web.AppRunner(aiohttp_app)
    await runner.setup()
    site = web.TCPSite(runner, "localhost", port)
    await site.start()

    server_name = _derive_server_name(config)
    base_url = f"http://localhost:{port}/mcp"

    console.print("\n" + "=" * 50)
    console.print("Local MCP Server running!")
    console.print("=" * 50)
    console.print(f"URL: {base_url}")
    console.print("\n" + "=" * 50)
    console.print("Connect via Claude Connectors")
    console.print("=" * 50)
    console.print(
        "\n1. Go to Settings -> Connectors (or Customize -> Connectors on claude.ai)"
    )
    console.print("2. Click 'Add custom connector'")
    console.print(f"3. Enter a name ({server_name}) and URL: {base_url}")
    console.print(
        "\nNote: Localhost works with Claude Desktop only (web needs a deployed URL)."
    )
    console.print("\n" + "=" * 50)
    console.print("\nTest with:")
    console.print(f"  opencontext test --url {base_url}")
    console.print(
        f"  or curl -X POST {base_url}"
        " -H 'Content-Type: application/json'"
        ' -d \'{"jsonrpc":"2.0","id":1,"method":"ping"}\''
    )
    console.print("\nPress Ctrl+C to stop")
    console.print("=" * 50 + "\n")

    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        console.print("\nShutting down...")
        await plugin_manager.shutdown()
        console.print("Server stopped.")


@app.callback(invoke_without_command=True)
def serve(
    ctx: typer.Context,
    port: int = typer.Option(8000, help="Port to listen on (default: 8000)"),
    config: str = typer.Option(
        "",
        help="Path to config.yaml. Overrides OPENCONTEXT_CONFIG env var.",
    ),
) -> None:
    """Run the OpenContext MCP server locally for development and testing."""
    if ctx.invoked_subcommand is not None:
        return

    # Resolve config path: --config flag > OPENCONTEXT_CONFIG env var > default
    config_path = config or os.environ.get("OPENCONTEXT_CONFIG", "") or "config.yaml"

    loaded_config, resolved_path = _load_config(config_path)
    console.print(f"Using config: {resolved_path}")

    asyncio.run(_run_server(loaded_config, port))
