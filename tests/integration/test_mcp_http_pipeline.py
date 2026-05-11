"""Hermetic integration: UniversalHTTPHandler + real PluginManager + fake plugin."""

from __future__ import annotations

import json

import pytest

from server.http_handler import UniversalHTTPHandler


@pytest.mark.asyncio
async def test_mcp_jsonrpc_pipeline_via_universal_handler(
    opencontext_config_env: None,
    reset_http_handler_globals: None,
) -> None:
    handler = UniversalHTTPHandler()

    ping_body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"})
    status, headers, body = await handler.handle_request(
        "POST", "/mcp", ping_body, {"content-type": "application/json"}
    )
    assert status == 200
    assert "Access-Control-Allow-Origin" in headers
    payload = json.loads(body)
    assert payload["result"] == {"status": "ok"}

    init_body = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "pytest", "version": "1"},
            },
        }
    )
    status, headers, body = await handler.handle_request(
        "POST", "/mcp", init_body, {"content-type": "application/json"}
    )
    assert status == 200
    assert "Mcp-Session-Id" in headers
    payload = json.loads(body)
    assert "protocolVersion" in payload["result"]

    list_body = json.dumps({"jsonrpc": "2.0", "id": 3, "method": "tools/list"})
    status, _, body = await handler.handle_request(
        "POST", "/mcp", list_body, {"content-type": "application/json"}
    )
    assert status == 200
    tools_payload = json.loads(body)
    tools = tools_payload["result"]["tools"]
    names = {t["name"] for t in tools}
    assert "integration_test_fake__echo" in names
    assert "integration_test_fake__fail_me" in names

    call_body = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "integration_test_fake__echo",
                "arguments": {"msg": "hello-integration"},
            },
        }
    )
    status, _, body = await handler.handle_request(
        "POST", "/mcp", call_body, {"content-type": "application/json"}
    )
    assert status == 200
    call_payload = json.loads(body)
    content = call_payload["result"]["content"]
    assert any(c.get("text") == "hello-integration" for c in content)

    fail_body = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "integration_test_fake__fail_me",
                "arguments": {},
            },
        }
    )
    status, _, body = await handler.handle_request(
        "POST", "/mcp", fail_body, {"content-type": "application/json"}
    )
    assert status == 200
    fail_payload = json.loads(body)
    assert fail_payload["result"].get("isError") is True
    assert "integration fake failure" in fail_payload["result"].get("error", "")


@pytest.mark.asyncio
async def test_wrong_path_returns_404(
    opencontext_config_env: None,
    reset_http_handler_globals: None,
) -> None:
    handler = UniversalHTTPHandler()
    status, _, body = await handler.handle_request(
        "POST",
        "/wrong",
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"}),
        {},
    )
    assert status == 404
    err = json.loads(body)["error"]
    assert err["message"] == "Not Found"
