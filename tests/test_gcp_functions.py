"""Tests for Google Cloud Functions (gen2) HTTP adapter."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from flask import Request
from werkzeug.test import EnvironBuilder

import server.adapters.gcp_functions as gcp_functions
from server.adapters.gcp_functions import mcp_http


@pytest.fixture(autouse=True)
def reset_gcp_handler():
    gcp_functions._handler = None
    yield
    gcp_functions._handler = None


def _make_request(method: str, path: str, body: str | None = None) -> Request:
    kwargs: dict = {"method": method, "path": path}
    if body is not None:
        kwargs["data"] = body
        kwargs["content_type"] = "application/json"
    builder = EnvironBuilder(**kwargs)
    return Request(builder.get_environ())


class TestMcpHttp:
    def test_options_returns_cors(self):
        req = _make_request("OPTIONS", "/mcp")
        with patch("server.adapters.gcp_functions.get_handler") as mock_get:
            mock_h = MagicMock()
            mock_h.handle_options.return_value = (
                200,
                {"Access-Control-Allow-Origin": "*"},
                "",
            )
            mock_get.return_value = mock_h

            out = mcp_http(req)

            assert out[1] == 200
            mock_h.handle_options.assert_called_once()

    def test_post_invokes_handle_request(self):
        body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping", "params": {}})
        req = _make_request("POST", "/mcp", body)

        with patch("server.adapters.gcp_functions.get_handler") as mock_get:
            mock_h = MagicMock()
            mock_h.handle_request = AsyncMock(
                return_value=(
                    200,
                    {"Content-Type": "application/json"},
                    json.dumps({"jsonrpc": "2.0", "id": 1, "result": {}}),
                )
            )
            mock_get.return_value = mock_h

            out = mcp_http(req)

            assert out[1] == 200
            mock_h.handle_request.assert_called_once()
            call = mock_h.handle_request.call_args[1]
            assert call["method"] == "POST"
            assert call["path"] == "/mcp"
