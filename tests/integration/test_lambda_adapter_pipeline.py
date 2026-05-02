"""Hermetic integration: AWS Lambda adapter event shapes."""

from __future__ import annotations

import base64
import json
from typing import Any
from unittest.mock import MagicMock

from server.adapters.aws_lambda import lambda_handler


def test_apigw_proxy_event_base64_body_round_trip(
    opencontext_config_env: None,
    reset_http_handler_globals: None,
    reset_lambda_adapter_handler: None,
) -> None:
    ctx = MagicMock()
    ctx.aws_request_id = "req-integration-1"
    ctx.function_name = "fn"
    ctx.memory_limit_in_mb = 128

    payload = {"jsonrpc": "2.0", "id": 1, "method": "ping"}
    raw = json.dumps(payload).encode()
    event: dict[str, Any] = {
        "httpMethod": "POST",
        "path": "/mcp",
        "headers": {"Content-Type": "application/json"},
        "body": base64.b64encode(raw).decode("ascii"),
        "isBase64Encoded": True,
    }

    resp = lambda_handler(event, ctx)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["result"] == {"status": "ok"}
    assert resp["headers"].get("Access-Control-Allow-Origin") == "*"


def test_options_preflight(
    opencontext_config_env: None,
    reset_http_handler_globals: None,
    reset_lambda_adapter_handler: None,
) -> None:
    ctx = MagicMock()
    ctx.aws_request_id = "req-integration-2"

    event = {
        "httpMethod": "OPTIONS",
        "path": "/mcp",
        "headers": {},
    }
    resp = lambda_handler(event, ctx)
    assert resp["statusCode"] == 200
    assert resp["body"] == ""
    assert "Access-Control-Allow-Methods" in resp["headers"]


def test_sequential_invocations_reinitialize_cleanly(
    opencontext_config_env: None,
    reset_http_handler_globals: None,
    reset_lambda_adapter_handler: None,
) -> None:
    """Lambda adapter asyncio.run + shutdown should allow a second invocation."""
    ctx = MagicMock()
    ctx.aws_request_id = "req-integration-3"

    def make_event(rid: int) -> dict[str, Any]:
        return {
            "httpMethod": "POST",
            "path": "/mcp",
            "headers": {"content-type": "application/json"},
            "body": json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": rid,
                    "method": "tools/list",
                }
            ),
        }

    ctx.aws_request_id = "a"
    r1 = lambda_handler(make_event(1), ctx)
    assert r1["statusCode"] == 200

    ctx.aws_request_id = "b"
    r2 = lambda_handler(make_event(2), ctx)
    assert r2["statusCode"] == 200
    tools = json.loads(r2["body"])["result"]["tools"]
    assert any(t["name"] == "integration_test_fake__echo" for t in tools)
