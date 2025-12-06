"""AWS Lambda handler for OpenContext MCP server.

This handler processes HTTP requests from Lambda Function URL and routes
them to the MCP server for processing.
"""

import json
import logging
import os
from typing import Any, Dict

from pythonjsonlogger import jsonlogger

from core.mcp_server import MCPServer
from core.plugin_manager import PluginManager
from core.validators import ConfigurationError, load_and_validate_config

# Configure structured logging for CloudWatch
log_handler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter("%(asctime)s %(name)s %(levelname)s %(message)s")
log_handler.setFormatter(formatter)

logger = logging.getLogger(__name__)
logger.addHandler(log_handler)
logger.setLevel(logging.INFO)

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


async def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """AWS Lambda handler function.

    Args:
        event: Lambda event (HTTP request from Function URL)
        context: Lambda context

    Returns:
        HTTP response dictionary
    """
    request_id = context.aws_request_id if context else "unknown"

    try:
        # Initialize server on first request
        await _initialize_server()

        # Extract request body
        body = event.get("body", "{}")
        if isinstance(body, dict):
            body = json.dumps(body)

        # Extract headers
        headers = event.get("headers", {})
        if isinstance(headers, dict):
            # Convert header keys to lowercase for consistency
            headers = {k.lower(): v for k, v in headers.items()}

        # Handle request
        response = await _mcp_server.handle_http_request(body, headers)

        # Add request ID to response headers for tracing
        if "headers" in response:
            response["headers"]["X-Request-ID"] = request_id
        else:
            response["headers"] = {"X-Request-ID": request_id}

        logger.info(
            f"Request {request_id} processed successfully",
            extra={"request_id": request_id},
        )

        return response

    except ConfigurationError as e:
        # Configuration errors should crash Lambda
        logger.error(
            f"Configuration error in request {request_id}: {e}",
            extra={"request_id": request_id},
        )
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(
                {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32603,
                        "message": "Server configuration error",
                        "data": str(e),
                    },
                }
            ),
        }

    except Exception as e:
        logger.error(
            f"Error processing request {request_id}: {e}",
            exc_info=True,
            extra={"request_id": request_id},
        )
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(
                {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32603,
                        "message": "Internal error",
                        "data": str(e),
                    },
                }
            ),
        }
