"""Tests for server/lambda_handler.py — cold start, warm start, request routing."""

import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_context(request_id: str = "test-req-id-123") -> MagicMock:
    ctx = MagicMock()
    ctx.aws_request_id = request_id
    return ctx


def _make_event(body: dict | str | None = None, headers: dict | None = None) -> dict:
    if body is None:
        body = {"jsonrpc": "2.0", "method": "initialize", "id": 1}
    if isinstance(body, dict):
        body = json.dumps(body)
    return {
        "body": body,
        "headers": headers or {"content-type": "application/json"},
    }


# ---------------------------------------------------------------------------
# _load_config — environment variable path
# ---------------------------------------------------------------------------


class TestLoadConfig:
    def setup_method(self):
        """Reset module-level globals before each test."""
        import server.lambda_handler as lh

        lh._config = None

    def test_loads_from_env_variable(self):
        cfg = {"server_name": "test", "plugins": {}}
        with patch.dict(os.environ, {"OPENCONTEXT_CONFIG": json.dumps(cfg)}):
            import server.lambda_handler as lh

            lh._config = None  # ensure reset
            result = lh._load_config()
        assert result["server_name"] == "test"

    def test_caches_config_on_second_call(self):
        cfg = {"server_name": "cached", "plugins": {}}
        with patch.dict(os.environ, {"OPENCONTEXT_CONFIG": json.dumps(cfg)}):
            import server.lambda_handler as lh

            lh._config = None
            lh._load_config()
            # Second call must not re-parse env — just return cached
            with patch("json.loads", side_effect=AssertionError("should not call")):
                result = lh._load_config()
        assert result["server_name"] == "cached"

    def test_falls_back_to_config_yaml(self, tmp_path):
        cfg = {"server_name": "fromfile", "plugins": {"ckan": {"enabled": True}}}
        import server.lambda_handler as lh

        lh._config = None

        with patch.dict(os.environ, {}, clear=False):
            # ensure OPENCONTEXT_CONFIG is not set
            os.environ.pop("OPENCONTEXT_CONFIG", None)
            with patch(
                "server.lambda_handler.load_and_validate_config", return_value=cfg
            ):
                result = lh._load_config()
        assert result["server_name"] == "fromfile"

    def test_raises_on_invalid_json_in_env(self):
        import server.lambda_handler as lh

        lh._config = None
        with patch.dict(os.environ, {"OPENCONTEXT_CONFIG": "not-valid-json"}):
            with pytest.raises(json.JSONDecodeError):
                lh._load_config()

    def test_raises_file_not_found_when_no_config(self):
        import server.lambda_handler as lh

        lh._config = None
        os.environ.pop("OPENCONTEXT_CONFIG", None)
        with patch(
            "server.lambda_handler.load_and_validate_config",
            side_effect=FileNotFoundError("no config.yaml"),
        ):
            with pytest.raises(FileNotFoundError):
                lh._load_config()


# ---------------------------------------------------------------------------
# _initialize_server — cold start & warm start
# ---------------------------------------------------------------------------


class TestInitializeServer:
    def setup_method(self):
        import server.lambda_handler as lh

        lh._plugin_manager = None
        lh._mcp_server = None
        lh._config = None

    @pytest.mark.asyncio
    async def test_cold_start_initializes_once(self):
        import server.lambda_handler as lh

        cfg = {"server_name": "test", "plugins": {"ckan": {"enabled": True}}}

        mock_pm = AsyncMock()
        mock_server = MagicMock()

        with (
            patch("server.lambda_handler._load_config", return_value=cfg),
            patch("server.lambda_handler.PluginManager", return_value=mock_pm),
            patch("server.lambda_handler.MCPServer", return_value=mock_server),
        ):
            await lh._initialize_server()

        assert lh._plugin_manager is mock_pm
        assert lh._mcp_server is mock_server
        mock_pm.load_plugins.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_warm_start_skips_init(self):
        import server.lambda_handler as lh

        lh._plugin_manager = MagicMock()
        lh._mcp_server = MagicMock()

        with patch(
            "server.lambda_handler._load_config",
            side_effect=AssertionError("cold only"),
        ):
            await lh._initialize_server()  # should not raise

    @pytest.mark.asyncio
    async def test_configuration_error_raises_runtime_error(self):
        from core.validators import ConfigurationError

        import server.lambda_handler as lh

        lh._plugin_manager = None
        lh._mcp_server = None

        with patch(
            "server.lambda_handler._load_config",
            side_effect=ConfigurationError("bad config"),
        ):
            with pytest.raises(RuntimeError, match="Configuration error"):
                await lh._initialize_server()

    @pytest.mark.asyncio
    async def test_unexpected_exception_propagates(self):
        import server.lambda_handler as lh

        lh._plugin_manager = None
        lh._mcp_server = None

        with patch(
            "server.lambda_handler._load_config",
            side_effect=RuntimeError("boom"),
        ):
            with pytest.raises(RuntimeError, match="boom"):
                await lh._initialize_server()


# ---------------------------------------------------------------------------
# _handle_request — routing
# ---------------------------------------------------------------------------


class TestHandleRequest:
    def setup_method(self):
        import server.lambda_handler as lh

        lh._plugin_manager = MagicMock()
        lh._mcp_server = AsyncMock()
        lh._config = {"server_name": "test"}

    @pytest.mark.asyncio
    async def test_returns_200_on_success(self):
        import server.lambda_handler as lh

        response_body = json.dumps({"jsonrpc": "2.0", "result": {}, "id": 1})
        lh._mcp_server.handle_http_request = AsyncMock(
            return_value={
                "statusCode": 200,
                "headers": {"Content-Type": "application/json"},
                "body": response_body,
            }
        )

        event = _make_event()
        ctx = _make_context("req-abc")

        response = await lh._handle_request(event, ctx)
        assert response["statusCode"] == 200
        assert response["headers"]["X-Request-ID"] == "req-abc"

    @pytest.mark.asyncio
    async def test_handles_dict_body(self):
        """When body is already a dict (API Gateway v2), it is JSON-serialised."""
        import server.lambda_handler as lh

        lh._mcp_server.handle_http_request = AsyncMock(
            return_value={"statusCode": 200, "headers": {}, "body": "{}"}
        )

        event = {
            "body": {"jsonrpc": "2.0", "method": "tools/list", "id": 2},
            "headers": {},
        }
        await lh._handle_request(event, _make_context())
        # Verify handle_http_request was called with a string body
        call_args = lh._mcp_server.handle_http_request.call_args[0]
        assert isinstance(call_args[0], str)

    @pytest.mark.asyncio
    async def test_headers_converted_to_lowercase(self):
        import server.lambda_handler as lh

        lh._mcp_server.handle_http_request = AsyncMock(
            return_value={"statusCode": 200, "headers": {}, "body": "{}"}
        )

        event = {
            "body": "{}",
            "headers": {"Content-Type": "application/json", "X-Custom": "val"},
        }
        await lh._handle_request(event, _make_context())
        headers_passed = lh._mcp_server.handle_http_request.call_args[0][1]
        assert "content-type" in headers_passed
        assert "x-custom" in headers_passed

    @pytest.mark.asyncio
    async def test_response_without_headers_key_gets_request_id(self):
        import server.lambda_handler as lh

        lh._mcp_server.handle_http_request = AsyncMock(
            return_value={"statusCode": 200, "body": "{}"}
        )

        response = await lh._handle_request(_make_event(), _make_context("id-xyz"))
        assert response["headers"]["X-Request-ID"] == "id-xyz"

    @pytest.mark.asyncio
    async def test_configuration_error_returns_500(self):
        from core.validators import ConfigurationError

        import server.lambda_handler as lh

        lh._mcp_server.handle_http_request = AsyncMock(
            side_effect=ConfigurationError("missing plugin")
        )

        response = await lh._handle_request(_make_event(), _make_context())
        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        assert body["error"]["code"] == -32603
        assert "configuration error" in body["error"]["message"].lower()

    @pytest.mark.asyncio
    async def test_generic_exception_returns_500(self):
        import server.lambda_handler as lh

        lh._mcp_server.handle_http_request = AsyncMock(
            side_effect=ValueError("unexpected failure")
        )

        response = await lh._handle_request(_make_event(), _make_context())
        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        assert body["error"]["code"] == -32603
        assert "Internal error" in body["error"]["message"]

    @pytest.mark.asyncio
    async def test_missing_body_defaults_to_empty_json(self):
        """Event with no body key defaults to '{}'."""
        import server.lambda_handler as lh

        lh._mcp_server.handle_http_request = AsyncMock(
            return_value={"statusCode": 200, "headers": {}, "body": "{}"}
        )

        event = {"headers": {}}
        await lh._handle_request(event, _make_context())
        body_arg = lh._mcp_server.handle_http_request.call_args[0][0]
        assert body_arg == "{}"

    @pytest.mark.asyncio
    async def test_none_context_uses_unknown_request_id(self):
        import server.lambda_handler as lh

        lh._mcp_server.handle_http_request = AsyncMock(
            return_value={"statusCode": 200, "headers": {}, "body": "{}"}
        )

        response = await lh._handle_request(_make_event(), None)
        assert response["headers"]["X-Request-ID"] == "unknown"


# ---------------------------------------------------------------------------
# handler — synchronous entry point
# ---------------------------------------------------------------------------


class TestHandler:
    def setup_method(self):
        import server.lambda_handler as lh

        lh._plugin_manager = MagicMock()
        lh._mcp_server = AsyncMock()
        lh._config = {"server_name": "test"}

    def test_handler_returns_dict(self):
        import server.lambda_handler as lh

        lh._mcp_server.handle_http_request = AsyncMock(
            return_value={"statusCode": 200, "headers": {}, "body": "{}"}
        )

        response = lh.handler(_make_event(), _make_context())
        assert isinstance(response, dict)
        assert response["statusCode"] == 200

    def test_handler_is_synchronous(self):
        """Verify handler can be called without await (it wraps asyncio.run)."""
        import server.lambda_handler as lh

        lh._mcp_server.handle_http_request = AsyncMock(
            return_value={"statusCode": 200, "headers": {}, "body": "{}"}
        )

        import inspect

        assert not inspect.iscoroutinefunction(lh.handler)
