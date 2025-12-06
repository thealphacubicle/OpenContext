# OpenContext Client

Stdio client for connecting Claude Desktop to OpenContext MCP servers.

## Installation

```bash
pip install opencontext-client
```

Or using `uvx` (recommended for Claude Desktop):

```bash
uvx opencontext-client <lambda_url>
```

## Usage

### With Claude Desktop

Add to your Claude Desktop configuration file:

```json
{
  "mcpServers": {
    "my-mcp-server": {
      "command": "uvx",
      "args": [
        "opencontext-client",
        "https://your-lambda-url.lambda-url.us-east-1.on.aws"
      ]
    }
  }
}
```

### Command Line

```bash
# Using Lambda URL as argument
opencontext-client https://your-lambda-url.lambda-url.us-east-1.on.aws

# Using environment variable
export OPENCONTEXT_LAMBDA_URL=https://your-lambda-url.lambda-url.us-east-1.on.aws
opencontext-client
```

## Environment Variables

- `OPENCONTEXT_LAMBDA_URL`: Lambda Function URL (required if not provided as argument)
- `OPENCONTEXT_TIMEOUT`: HTTP request timeout in seconds (default: 30)

## How It Works

The client reads MCP JSON-RPC messages from stdin and forwards them to the Lambda Function URL via HTTP POST. Responses are written to stdout in the same JSON-RPC format.

This allows Claude Desktop to communicate with OpenContext MCP servers running on AWS Lambda without requiring direct HTTP access.

