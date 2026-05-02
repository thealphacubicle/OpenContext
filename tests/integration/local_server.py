"""Ephemeral aiohttp MCP server for CLI integration tests."""

from __future__ import annotations

import json
import time
import uuid
from typing import Any, Awaitable, Callable, Dict, Tuple

from aiohttp import web

from core.mcp_server import MCPServer
from core.plugin_manager import PluginManager


async def start_local_mcp_server(
    config: Dict[str, Any],
) -> Tuple[str, Callable[[], Awaitable[None]]]:
    """Start POST /mcp on a random port; return (base_url_without_path, shutdown_coro)."""
    plugin_manager = PluginManager(config)
    await plugin_manager.load_plugins()
    mcp_server = MCPServer(plugin_manager)

    async def handle_mcp_request(request: web.Request) -> web.StreamResponse:
        start_time = time.perf_counter()
        try:
            body = await request.text()
            headers = dict(request.headers)

            try:
                request_json = json.loads(body)
                method = request_json.get("method", "unknown")
            except (json.JSONDecodeError, AttributeError):
                method = "unknown"

            is_initialize = method == "initialize"
            session_id_to_return = None
            if is_initialize:
                session_id_to_return = str(uuid.uuid4())

            response = await mcp_server.handle_http_request(body, headers)

            response_headers = dict(response.get("headers", {}))
            if session_id_to_return:
                response_headers["Mcp-Session-Id"] = session_id_to_return

            duration_ms = (time.perf_counter() - start_time) * 1000
            _ = duration_ms

            return web.Response(
                text=response.get("body", "{}"),
                status=response.get("statusCode", 200),
                headers=response_headers,
            )
        except Exception as e:
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

    app = web.Application()
    app.router.add_post("/mcp", handle_mcp_request)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()

    host, port = runner.addresses[0]
    base_url = f"http://{host}:{port}"

    async def shutdown() -> None:
        await plugin_manager.shutdown()
        await runner.cleanup()

    return base_url, shutdown
