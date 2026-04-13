"""Google Cloud Functions (gen2) HTTP adapter for OpenContext MCP server.

Maps Flask `Request` objects (via functions-framework) to UniversalHTTPHandler.
Config is read from OPENCONTEXT_CONFIG (set by Terraform), same contract as AWS Lambda.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any, Optional

import functions_framework
from flask import Request

from server.http_handler import UniversalHTTPHandler

logger = logging.getLogger(__name__)

_handler: Optional[UniversalHTTPHandler] = None


def get_handler() -> UniversalHTTPHandler:
    """Lazy handler for warm starts."""
    global _handler
    if _handler is None:
        _handler = UniversalHTTPHandler()
    return _handler


def _request_id(request: Request) -> str:
    rid = request.headers.get("X-Request-ID") or request.headers.get(
        "X-Cloud-Trace-Context"
    )
    if rid and "/" in rid:  # trace context form: TRACE_ID/SPAN_ID;o=1
        rid = rid.split("/")[0]
    return rid or str(uuid.uuid4())


@functions_framework.http
def mcp_http(request: Request) -> Any:
    """HTTP Cloud Function entry point (Terraform entry_point = mcp_http, main.py re-exports)."""
    req_id = _request_id(request)
    method = request.method.upper()
    path = request.path or "/"

    try:
        if method == "OPTIONS":
            handler = get_handler()
            status_code, headers, body = handler.handle_options(request_id=req_id)
            return (body, status_code, headers)

        body_raw = request.get_data(as_text=True)
        if not body_raw:
            body_raw = "{}"

        headers = {k.lower(): v for k, v in request.headers.items()}

        handler = get_handler()

        async def _run_with_cleanup():
            try:
                return await handler.handle_request(
                    method=method,
                    path=path,
                    body=body_raw,
                    headers=headers,
                    request_id=req_id,
                )
            finally:
                from server import http_handler

                if http_handler._plugin_manager is not None:
                    await http_handler._plugin_manager.shutdown()
                    http_handler._plugin_manager = None
                    http_handler._mcp_server = None

        status_code, response_headers, response_body = asyncio.run(_run_with_cleanup())
        return (response_body, status_code, response_headers)

    except Exception as e:
        logger.error(
            "Error in Cloud Functions handler: %s",
            e,
            extra={"request_id": req_id, "error_type": type(e).__name__},
            exc_info=True,
        )
        err = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32603,
                    "message": "Internal error",
                    "data": str(e),
                },
            }
        )
        return (
            err,
            500,
            {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
        )
