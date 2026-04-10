"""Tests for CLI architecture command."""

from __future__ import annotations

import io

from rich.console import Console


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _capture_architecture() -> str:
    """Run the architecture command and capture its Rich output as a string."""
    from cli.commands.architecture import architecture

    buf = io.StringIO()
    capture_console = Console(file=buf, highlight=False, markup=True)

    import cli.commands.architecture as arch_module

    original_console = arch_module.console
    arch_module.console = capture_console
    try:
        architecture()
    finally:
        arch_module.console = original_console

    return buf.getvalue()


# ---------------------------------------------------------------------------
# Basic invocation
# ---------------------------------------------------------------------------


class TestArchitectureInvokes:
    def test_runs_without_error(self):
        """architecture() should complete without raising any exception."""
        from cli.commands.architecture import architecture

        # Should not raise
        architecture()

    def test_returns_none(self):
        """architecture() returns None (no explicit return value)."""
        from cli.commands.architecture import architecture

        result = architecture()
        assert result is None


# ---------------------------------------------------------------------------
# Output content — key terms
# ---------------------------------------------------------------------------


class TestArchitectureOutput:
    def setup_method(self):
        self.output = _capture_architecture()

    def test_contains_overview_section(self):
        assert "Resource Tagging" in self.output

    def test_contains_request_flow_section(self):
        assert "Request Flow" in self.output

    def test_contains_plugin_discovery_section(self):
        assert "SQS Dead Letter Queue" in self.output

    def test_contains_tool_namespacing_section(self):
        assert "REST API" in self.output

    def test_contains_deployment_modes_section(self):
        assert "Custom Domain" in self.output

    def test_contains_key_config_section(self):
        assert "OPENCONTEXT_CONFIG" in self.output

    def test_mentions_one_fork_rule(self):
        assert "AWSLambdaBasicExecutionRole" in self.output

    def test_mentions_mcp_protocol(self):
        assert "MCP" in self.output

    def test_mentions_json_rpc(self):
        assert "JSON-RPC" in self.output

    def test_mentions_plugin_manager(self):
        assert "CloudWatch Logs" in self.output

    def test_mentions_tool_namespacing_format(self):
        assert "lambda_handler" in self.output

    def test_mentions_example_tool(self):
        assert "opencontext-terraform-state" in self.output

    def test_mentions_lambda_deployment(self):
        assert "Lambda" in self.output

    def test_mentions_local_dev_server(self):
        assert "Python 3.11" in self.output

    def test_mentions_config_yaml(self):
        assert "config.yaml" in self.output

    def test_mentions_api_gateway(self):
        assert "API Gateway" in self.output

    def test_mentions_terraform(self):
        assert "terraform" in self.output

    def test_mentions_supported_plugins(self):
        assert "CloudWatch" in self.output
        assert "X-Ray" in self.output
        assert "SQS" in self.output

    def test_mentions_initialize_method(self):
        assert "create_before_destroy" in self.output

    def test_mentions_double_underscore_separator(self):
        assert "lambda_handler" in self.output


# ---------------------------------------------------------------------------
# Main.py registration
# ---------------------------------------------------------------------------


class TestArchitectureRegistered:
    def test_architecture_command_registered_in_app(self):
        """architecture should be registered in the main app.

        Typer stores name=None when app.command()(fn) is used and derives the
        name from the function at runtime. Check via the callback instead.
        """
        from cli.commands.architecture import architecture
        from cli.main import app

        callbacks = [cmd.callback for cmd in app.registered_commands]
        assert architecture in callbacks
