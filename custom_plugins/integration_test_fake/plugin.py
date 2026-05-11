"""Hermetic integration-test plugin (disabled in normal configs).

Enable only in tests via a temporary config or OPENCONTEXT_CONFIG JSON.
"""

from __future__ import annotations

from typing import Any, Dict, List

from core.interfaces import MCPPlugin, PluginType, ToolDefinition, ToolResult


class IntegrationTestFakePlugin(MCPPlugin):
    """Minimal MCP plugin for cross-component integration tests."""

    plugin_name = "integration_test_fake"
    plugin_type = PluginType.CUSTOM_API
    plugin_version = "0.0.1"

    async def initialize(self) -> bool:
        self._initialized = True
        return True

    async def shutdown(self) -> None:
        self._initialized = False

    def get_tools(self) -> List[ToolDefinition]:
        return [
            ToolDefinition(
                name="echo",
                description="Echo message for integration tests",
                input_schema={
                    "type": "object",
                    "properties": {"msg": {"type": "string"}},
                    "additionalProperties": False,
                },
            ),
            ToolDefinition(
                name="fail_me",
                description="Always returns failure for error-path tests",
                input_schema={"type": "object"},
            ),
        ]

    async def execute_tool(
        self, tool_name: str, arguments: Dict[str, Any]
    ) -> ToolResult:
        if tool_name == "echo":
            msg = arguments.get("msg", "")
            return ToolResult(
                content=[{"type": "text", "text": msg}],
                success=True,
            )
        if tool_name == "fail_me":
            return ToolResult(
                success=False,
                error_message="integration fake failure",
            )
        return ToolResult(success=False, error_message=f"unknown tool: {tool_name}")

    async def health_check(self) -> bool:
        return True
