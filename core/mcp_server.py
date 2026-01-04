"""MCP Server implementation for OpenContext.

Handles MCP JSON-RPC protocol and integrates with Plugin Manager.
"""

import json
import logging
from typing import Any, Dict, Optional

from core.plugin_manager import PluginManager

logger = logging.getLogger(__name__)


class MCPServer:
    """MCP Server that handles JSON-RPC requests and routes to Plugin Manager."""

    def __init__(self, plugin_manager: PluginManager) -> None:
        """Initialize MCP Server with Plugin Manager.

        Args:
            plugin_manager: Initialized Plugin Manager instance
        """
        self.plugin_manager = plugin_manager

    async def handle_request(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Handle a single MCP JSON-RPC request.

        Args:
            request: JSON-RPC request dictionary

        Returns:
            JSON-RPC response dictionary, or None for notifications
        """
        request_id = request.get("id")
        method = request.get("method")
        params = request.get("params", {})

        # Check if this is a notification (no id field)
        is_notification = request_id is None

        try:
            if method == "initialize":
                result = await self._handle_initialize(params)
            elif method == "tools/list":
                result = await self._handle_tools_list()
            elif method == "tools/call":
                result = await self._handle_tools_call(params)
            elif method == "ping":
                result = {"status": "ok"}
            elif method == "notifications/initialized":
                # MCP notification - no response needed
                return None
            else:
                # For notifications with unknown methods, silently ignore
                if is_notification:
                    logger.warning(f"Ignoring unknown notification method: {method}")
                    return None
                raise ValueError(f"Unknown method: {method}")

            # Don't send response for notifications
            if is_notification:
                return None

            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": result,
            }

        except Exception as e:
            logger.error(f"Error handling request {method}: {e}", exc_info=True)
            # Don't send error response for notifications
            if is_notification:
                return None
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32603,
                    "message": "Internal error",
                    "data": str(e),
                },
            }

    async def _handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle initialize request.

        Args:
            params: Initialize parameters

        Returns:
            Initialize response
        """
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {},
            },
            "serverInfo": {
                "name": "opencontext",
                "version": "1.0.0",
            },
        }

    async def _handle_tools_list(self) -> Dict[str, Any]:
        """Handle tools/list request.

        Returns:
            List of available tools
        """
        tools = self.plugin_manager.get_all_tools()
        return {"tools": tools}

    async def _handle_tools_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools/call request.

        Args:
            params: Tool call parameters (name, arguments)

        Returns:
            Tool execution result
        """
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if not tool_name:
            raise ValueError("Tool name is required")

        result = await self.plugin_manager.execute_tool(tool_name, arguments)

        if result.success:
            return {
                "content": result.content,
            }
        else:
            return {
                "content": result.content,
                "isError": True,
                "error": result.error_message,
            }

    async def handle_http_request(
        self, body: str, headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Handle HTTP request with MCP JSON-RPC payload.

        This method is used by Lambda handler to process HTTP requests.

        Args:
            body: Request body (JSON string)
            headers: HTTP headers (optional)

        Returns:
            Response dictionary with statusCode and body
        """
        try:
            request = json.loads(body)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in request body: {e}")
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {
                            "code": -32700,
                            "message": "Parse error",
                            "data": str(e),
                        },
                    }
                ),
            }

        # Handle the request
        response = await self.handle_request(request)

        # If response is None, it was a notification - return empty response
        if response is None:
            return {
                "statusCode": 200,
                "headers": {"Content-Type": "application/json"},
                "body": "",
            }

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(response),
        }
