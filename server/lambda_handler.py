"""AWS Lambda handler for OpenContext MCP server.

This handler processes HTTP requests from Lambda Function URL and routes
them to the MCP server for processing.
"""

import asyncio
import json
import logging
import os
import time
import uuid
from typing import Any, Dict

from core.logging_utils import (
    configure_json_logging,
    format_request_log,
    format_response_log,
)
from core.mcp_server import MCPServer
from core.plugin_manager import PluginManager
from core.validators import (
    ConfigurationError,
    get_logging_config,
    load_and_validate_config,
)

# Configure JSON logging globally (must be called before other loggers are created)
# Try to get log level from config, but default to INFO if config not available yet
try:
    # Try loading config to get log level
    if os.environ.get("OPENCONTEXT_CONFIG"):
        config_json = os.environ.get("OPENCONTEXT_CONFIG")
        config = json.loads(config_json)
        logging_config = get_logging_config(config)
        log_level = logging_config.get("level", "INFO")
    else:
        # Try loading from config.yaml (for local testing)
        config = load_and_validate_config("config.yaml")
        logging_config = get_logging_config(config)
        log_level = logging_config.get("level", "INFO")
except Exception:
    # If config loading fails, use default
    log_level = "INFO"

configure_json_logging(level=log_level, pretty=False)  # Compact JSON for CloudWatch
logger = logging.getLogger(__name__)

# Global variables for Lambda container reuse
_plugin_manager: PluginManager | None = None
_mcp_server: MCPServer | None = None
_config: Dict[str, Any] | None = None


def _load_config() -> Dict[str, Any]:
    """Load configuration from environment or embedded config.

    Returns:
        Configuration dictionary
    """
    global _config

    if _config is not None:
        return _config

    # Try to load from environment variable (set by Terraform)
    config_json = os.environ.get("OPENCONTEXT_CONFIG")
    if config_json:
        try:
            _config = json.loads(config_json)
            logger.info("Loaded configuration from environment variable")
            return _config
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse config from environment: {e}")
            raise

    # Fall back to loading from config.yaml (for local testing)
    try:
        _config = load_and_validate_config("config.yaml")
        logger.info("Loaded configuration from config.yaml")
        return _config
    except FileNotFoundError:
        logger.error(
            "No configuration found. Set OPENCONTEXT_CONFIG environment variable "
            "or ensure config.yaml exists."
        )
        raise


async def _initialize_server() -> None:
    """Initialize plugin manager and MCP server.

    This function is called on first request (cold start) and reuses
    the initialized instances for subsequent requests (warm starts).
    """
    global _plugin_manager, _mcp_server

    if _plugin_manager is not None and _mcp_server is not None:
        return

    try:
        config = _load_config()

        # Initialize Plugin Manager
        _plugin_manager = PluginManager(config)

        # Load plugins (validates ONE plugin enabled)
        await _plugin_manager.load_plugins()

        # Initialize MCP Server
        _mcp_server = MCPServer(_plugin_manager)

        logger.info("OpenContext MCP server initialized successfully")

    except ConfigurationError as e:
        # Log error and crash Lambda
        logger.error(f"Configuration error: {e}")
        raise RuntimeError(f"Configuration error: {e}") from e
    except Exception as e:
        logger.error(f"Failed to initialize server: {e}", exc_info=True)
        raise


async def _handle_request(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Async handler logic for processing Lambda requests.

    Args:
        event: Lambda event (HTTP request from Function URL)
        context: Lambda context

    Returns:
        HTTP response dictionary
    """
    start_time = time.perf_counter()
    request_id = context.aws_request_id if context else "unknown"

    # Extract request details
    http_method = event.get("requestContext", {}).get("http", {}).get("method", "POST")
    request_path = event.get("requestContext", {}).get("http", {}).get("path", "/")
    if not request_path:
        request_path = event.get("rawPath", "/")

    # Validate path - must be /mcp
    if request_path != "/mcp":
        duration_ms = (time.perf_counter() - start_time) * 1000
        error_response = {
            "statusCode": 404,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32601,
                        "message": "Not Found",
                        "data": f"Path '{request_path}' not found. Expected '/mcp'",
                    },
                }
            ),
        }
        logger.warning(
            f"404 error: Path '{request_path}' not found",
            extra={
                "request_id": request_id,
                "request_path": request_path,
                "http_method": http_method,
                "duration_ms": duration_ms,
            },
        )
        return error_response

    # Validate method - must be POST
    if http_method != "POST":
        duration_ms = (time.perf_counter() - start_time) * 1000
        error_response = {
            "statusCode": 405,
            "headers": {"Content-Type": "application/json", "Allow": "POST"},
            "body": json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32601,
                        "message": "Method Not Allowed",
                        "data": f"Method '{http_method}' not allowed. Expected 'POST'",
                    },
                }
            ),
        }
        logger.warning(
            f"405 error: Method '{http_method}' not allowed",
            extra={
                "request_id": request_id,
                "request_path": request_path,
                "http_method": http_method,
                "duration_ms": duration_ms,
            },
        )
        return error_response

    # Extract request body
    body = event.get("body", "{}")
    if isinstance(body, dict):
        body = json.dumps(body)

    # Extract headers
    headers = event.get("headers", {})
    if isinstance(headers, dict):
        # Convert header keys to lowercase for consistency
        headers = {k.lower(): v for k, v in headers.items()}

    # Parse JSON to check if this is an initialize request
    try:
        request_json = json.loads(body)
        is_initialize = request_json.get("method") == "initialize"
    except (json.JSONDecodeError, AttributeError):
        is_initialize = False

    # Generate session ID for initialize requests
    session_id = None
    if is_initialize:
        session_id = str(uuid.uuid4())
        logger.info(
            f"Initialize request detected, generating session ID: {session_id}",
            extra={"request_id": request_id},
        )

    # Log request details
    request_log_data = format_request_log(
        request_id=request_id,
        http_method=http_method,
        request_path=request_path,
        headers=headers,
        body=body,
        lambda_context=context,
    )
    logger.info("Incoming HTTP request", extra=request_log_data)

    try:
        # Initialize server on first request
        await _initialize_server()

        # Handle request
        response = await _mcp_server.handle_http_request(body, headers)

        # Add session ID to response headers if this was an initialize request
        if session_id:
            if "headers" not in response:
                response["headers"] = {}
            response["headers"]["Mcp-Session-Id"] = session_id

        # Calculate duration
        duration_ms = (time.perf_counter() - start_time) * 1000

        # Add request ID to response headers for tracing
        if "headers" in response:
            response["headers"]["X-Request-ID"] = request_id
        else:
            response["headers"] = {"X-Request-ID": request_id}

        # Log response details
        response_log_data = format_response_log(
            request_id=request_id,
            status_code=response.get("statusCode", 200),
            headers=response.get("headers", {}),
            body=response.get("body", ""),
            duration_ms=duration_ms,
            success=True,
        )
        logger.info("HTTP request processed successfully", extra=response_log_data)

        return response

    except ConfigurationError as e:
        # Configuration errors should crash Lambda
        duration_ms = (time.perf_counter() - start_time) * 1000
        error_response = {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32603,
                        "message": "Server configuration error",
                        "data": str(e),
                    },
                }
            ),
        }

        # Log error response
        response_log_data = format_response_log(
            request_id=request_id,
            status_code=500,
            headers=error_response.get("headers", {}),
            body=error_response.get("body", ""),
            duration_ms=duration_ms,
            success=False,
        )
        logger.error(
            f"Configuration error in request {request_id}: {e}",
            extra={**response_log_data, "error_type": "ConfigurationError"},
            exc_info=True,
        )

        return error_response

    except Exception as e:
        duration_ms = (time.perf_counter() - start_time) * 1000
        error_response = {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32603,
                        "message": "Internal error",
                        "data": str(e),
                    },
                }
            ),
        }

        # Log error response
        response_log_data = format_response_log(
            request_id=request_id,
            status_code=500,
            headers=error_response.get("headers", {}),
            body=error_response.get("body", ""),
            duration_ms=duration_ms,
            success=False,
        )
        logger.error(
            f"Error processing request {request_id}: {e}",
            extra={**response_log_data, "error_type": type(e).__name__},
            exc_info=True,
        )

        return error_response


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """AWS Lambda handler function.

    This is a synchronous wrapper that uses asyncio.run() to execute
    the async request handling logic. AWS Lambda requires synchronous
    handler functions.

    Args:
        event: Lambda event (HTTP request from Function URL)
        context: Lambda context

    Returns:
        HTTP response dictionary
    """
    return asyncio.run(_handle_request(event, context))
