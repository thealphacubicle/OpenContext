"""Stdio client for OpenContext MCP servers.

This client reads MCP JSON-RPC messages from stdin and forwards them to
a Lambda Function URL via HTTP POST, writing responses to stdout.
"""

import asyncio
import json
import os
import sys
from typing import Optional

import httpx


class OpenContextClient:
    """Stdio client that bridges stdin/stdout to Lambda HTTP endpoint."""

    def __init__(self, lambda_url: str, timeout: int = 30) -> None:
        """Initialize client with Lambda URL.

        Args:
            lambda_url: Lambda Function URL
            timeout: HTTP request timeout in seconds
        """
        self.lambda_url = lambda_url.rstrip("/")
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)

    async def handle_request(self, request: dict) -> dict:
        """Handle a single JSON-RPC request.

        Args:
            request: JSON-RPC request dictionary

        Returns:
            JSON-RPC response dictionary
        """
        try:
            response = await self.client.post(
                self.lambda_url,
                json=request,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            return {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "error": {
                    "code": -32603,
                    "message": "HTTP error",
                    "data": str(e),
                },
            }
        except json.JSONDecodeError as e:
            return {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "error": {
                    "code": -32603,
                    "message": "Invalid JSON response from server",
                    "data": f"Failed to parse response: {str(e)}",
                },
            }

    async def run(self) -> None:
        """Run the client, reading from stdin and writing to stdout."""
        try:
            while True:
                # Read line from stdin
                line = await asyncio.to_thread(sys.stdin.readline)
                if not line:
                    break

                line = line.strip()
                if not line:
                    continue

                try:
                    request = json.loads(line)
                except json.JSONDecodeError as e:
                    error_response = {
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {
                            "code": -32700,
                            "message": "Parse error",
                            "data": str(e),
                        },
                    }
                    print(json.dumps(error_response), flush=True)
                    continue

                # Handle request
                response = await self.handle_request(request)

                # Write response to stdout
                print(json.dumps(response), flush=True)

        except KeyboardInterrupt:
            pass
        finally:
            await self.client.aclose()


def main() -> None:
    """Main entry point."""
    # Get Lambda URL from command line or environment
    if len(sys.argv) > 1:
        lambda_url = sys.argv[1]
    else:
        lambda_url = os.environ.get("OPENCONTEXT_LAMBDA_URL")

    if not lambda_url:
        print(
            "Error: Lambda URL required\n"
            "Usage: opencontext-client <lambda_url>\n"
            "Or set OPENCONTEXT_LAMBDA_URL environment variable",
            file=sys.stderr,
        )
        sys.exit(1)

    # Get timeout from environment (optional)
    timeout_str = os.environ.get("OPENCONTEXT_TIMEOUT", "30")
    try:
        timeout = int(timeout_str)
        if timeout <= 0:
            raise ValueError("Timeout must be positive")
    except ValueError as e:
        print(
            f"Error: Invalid OPENCONTEXT_TIMEOUT value '{timeout_str}'. "
            f"Must be a positive integer. {e}",
            file=sys.stderr,
        )
        sys.exit(1)

    client = OpenContextClient(lambda_url, timeout)
    asyncio.run(client.run())


if __name__ == "__main__":
    main()
