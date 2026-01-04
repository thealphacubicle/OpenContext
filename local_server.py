# run_local_server.py
"""Run OpenContext MCP server locally for testing (no Lambda needed)."""

import asyncio
import json
from pathlib import Path

import yaml
from aiohttp import web

from core.plugin_manager import PluginManager
from core.mcp_server import MCPServer

# Load config
with open("config.yaml") as f:
    config = yaml.safe_load(f)

# Global server instance
_plugin_manager = None
_mcp_server = None


async def init_server():
    """Initialize server on startup."""
    global _plugin_manager, _mcp_server

    print("🚀 Initializing OpenContext MCP Server locally...")

    # Initialize Plugin Manager
    _plugin_manager = PluginManager(config)
    await _plugin_manager.load_plugins()

    # Initialize MCP Server
    _mcp_server = MCPServer(_plugin_manager)

    print("✅ Server initialized successfully")
    print(f"Loaded plugins: {list(_plugin_manager.plugins.keys())}")
    print(f"Available tools: {len(_plugin_manager.get_all_tools())}")


async def handle_mcp_request(request):
    """Handle MCP JSON-RPC request."""
    try:
        body = await request.text()
        headers = dict(request.headers)

        # Use the same handler as Lambda
        response = await _mcp_server.handle_http_request(body, headers)

        return web.Response(
            text=response.get("body", "{}"),
            status=response.get("statusCode", 200),
            headers=response.get("headers", {}),
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


async def start_server():
    """Start local HTTP server."""
    await init_server()

    app = web.Application()
    app.router.add_post("/", handle_mcp_request)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "localhost", 8000)
    await site.start()

    print("\n" + "=" * 50)
    print("🌐 Local MCP Server running!")
    print("=" * 50)
    print(f"URL: http://localhost:8000")
    print("\nTest with:")
    print("  opencontext-client http://localhost:8000")
    print("\nPress Ctrl+C to stop")
    print("=" * 50 + "\n")

    # Keep running
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        print("\n👋 Shutting down...")
        await _plugin_manager.shutdown()


if __name__ == "__main__":
    asyncio.run(start_server())
