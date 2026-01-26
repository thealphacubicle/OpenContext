# Local Testing with Claude Desktop

This guide shows you how to run the OpenContext MCP server locally and connect it to Claude Desktop for testing.

## Prerequisites

- Python 3.11+
- Node.js and npm (for the HTTP transport adapter)
- Claude Desktop installed

## Step 1: Install Dependencies

First, install the required Python dependencies:

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install aiohttp for local server
pip install aiohttp
```

## Step 2: Configure Your Plugin

Make sure your `config.yaml` has exactly ONE plugin enabled. For example:

```yaml
plugins:
  ckan:
    enabled: true
    base_url: "https://data.boston.gov"
    portal_url: "https://data.boston.gov"
    city_name: "Boston"
    timeout: 120
```

## Step 3: Start the Local Server

Start the local MCP server:

```bash
python3 scripts/local_server.py
```

You should see output like:

```
🚀 Initializing OpenContext MCP Server locally...
✅ Server initialized successfully
Loaded plugins: ['ckan']
Available tools: 5

==================================================
🌐 Local MCP Server running!
==================================================
URL: http://localhost:8000/mcp

Test with:
  ./scripts/test_streamable_http.sh
  or curl -X POST http://localhost:8000/mcp -H 'Content-Type: application/json' -d '{"jsonrpc":"2.0","id":1,"method":"ping"}'

Press Ctrl+C to stop
==================================================
```

**Keep this terminal running!** The server needs to stay active.

## Step 4: Test the Server (Optional)

In another terminal, verify the server is working:

```bash
# Test ping
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"ping"}'

# Test tools/list
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list"}'
```

Or use the comprehensive test script:

```bash
./scripts/test_streamable_http.sh http://localhost:8000/mcp
```

## Step 5: Configure Claude Desktop

Now configure Claude Desktop to connect to your local server using the **Streamable HTTP Transport** method.

### Find Your Claude Desktop Config File

**macOS:**
```
~/Library/Application Support/Claude/claude_desktop_config.json
```

**Windows:**
```
%APPDATA%\Claude\claude_desktop_config.json
```

### Edit the Config File

Open the config file and add your local MCP server configuration:

```json
{
  "mcpServers": {
    "OpenContext Local": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-stdio-to-http",
        "--transport",
        "streamable-http",
        "http://localhost:8000/mcp"
      ]
    }
  }
}
```

**Important Notes:**
- The `npx` command will automatically download the HTTP transport adapter if needed
- Use `http://localhost:8000/mcp` (not just `http://localhost:8000`)
- The `-y` flag tells npx to proceed without prompting

### Example Full Config

If you already have other MCP servers configured, your config might look like:

```json
{
  "mcpServers": {
    "OpenContext Local": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-stdio-to-http",
        "--transport",
        "streamable-http",
        "http://localhost:8000/mcp"
      ]
    },
    "Other Server": {
      "command": "/path/to/other-server"
    }
  }
}
```

## Step 6: Restart Claude Desktop

**Important:** You must restart Claude Desktop for the configuration changes to take effect.

1. Quit Claude Desktop completely
2. Reopen Claude Desktop
3. The MCP server should now be connected

## Step 7: Test in Claude

Once Claude Desktop is restarted, try asking Claude to use your MCP server:

```
Search for datasets about housing in Boston
```

or

```
What tools are available from the OpenContext server?
```

Claude should be able to:
- Connect to your local server
- List available tools
- Execute tool calls (like searching datasets)

## Troubleshooting

### Server Won't Start

**Error:** `ModuleNotFoundError: No module named 'aiohttp'`

**Solution:**
```bash
pip install aiohttp
```

### Claude Desktop Can't Connect

1. **Check the server is running:**
   ```bash
   curl -X POST http://localhost:8000/mcp \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"ping"}'
   ```

2. **Check your config file syntax:**
   - Make sure JSON is valid (no trailing commas)
   - Verify the URL is `http://localhost:8000/mcp`

3. **Check Claude Desktop logs:**
   - **macOS:** `~/Library/Logs/Claude/claude_desktop.log`
   - **Windows:** Check the Claude Desktop logs directory

4. **Verify npx is available:**
   ```bash
   which npx
   npx --version
   ```

### Connection Timeout

If Claude Desktop times out connecting:

1. Make sure the local server is still running
2. Check firewall settings (localhost should be accessible)
3. Try restarting both the server and Claude Desktop

### Tools Not Available

If Claude can't see the tools:

1. Check server logs for initialization errors
2. Verify your plugin is enabled in `config.yaml`
3. Test tools/list directly:
   ```bash
   curl -X POST http://localhost:8000/mcp \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":2,"method":"tools/list"}'
   ```

## Alternative: Using the Go Client Binary

If you prefer to use the Go client binary instead of the HTTP transport adapter:

1. **Build or download the client binary:**
   ```bash
   cd client
   make build
   ```

2. **Update Claude Desktop config:**
   ```json
   {
     "mcpServers": {
       "OpenContext Local": {
         "command": "/absolute/path/to/client/opencontext-client",
         "args": ["http://localhost:8000"]
       }
     }
   }
   ```

   Note: Use the full absolute path to the binary, and use `http://localhost:8000` (without `/mcp`) as the client automatically appends it.

## Next Steps

- Test different tools and queries
- Modify your plugin configuration
- Create custom plugins (see [Custom Plugins Guide](CUSTOM_PLUGINS.md))
- Deploy to AWS Lambda for production (see [Deployment Guide](DEPLOYMENT.md))

## See Also

- [Testing Guide](TESTING.md) - More testing options
- [Quick Start Guide](QUICKSTART.md) - Production deployment
- [FAQ](FAQ.md) - Common questions
