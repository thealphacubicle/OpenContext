# Testing Guide

This guide covers different ways to test your OpenContext MCP server.

## Quick Test

### 1. Test Configuration

```bash
python3 -c "
import yaml
from core.validators import load_and_validate_config

try:
    config = load_and_validate_config('config.yaml')
    print('✅ Configuration is valid!')
    print(f'   Server: {config[\"server_name\"]}')
    print(f'   Plugin enabled: {list(config[\"plugins\"].keys())[0]}')
except Exception as e:
    print(f'❌ Configuration error: {e}')
"
```

### 2. Test Plugin Loading

```bash
python3 -c "
import asyncio
import yaml
from core.plugin_manager import PluginManager

async def test():
    with open('config.yaml') as f:
        config = yaml.safe_load(f)

    manager = PluginManager(config)
    try:
        await manager.load_plugins()
        print('✅ Plugin loaded successfully!')
        print(f'   Plugin: {list(manager.plugins.keys())[0]}')
        print(f'   Tools available: {len(manager.get_all_tools())}')
        for tool in manager.get_all_tools():
            print(f'     - {tool[\"name\"]}')
        await manager.shutdown()
    except Exception as e:
        print(f'❌ Error: {e}')

asyncio.run(test())
"
```

### 3. Test Local Server

**Terminal 1 - Start the server:**

```bash
# Install aiohttp if needed
pip install aiohttp

# Start local server
python3 local_server.py
```

**Terminal 2 - Test with curl:**

```bash
# Test ping
curl -X POST http://localhost:8000 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"ping"}'

# Test tools/list
curl -X POST http://localhost:8000 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list"}'

# Test search_datasets
curl -X POST http://localhost:8000 \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc":"2.0",
    "id":3,
    "method":"tools/call",
    "params":{
      "name":"ckan.search_datasets",
      "arguments":{"query":"housing","limit":3}
    }
  }'
```

## Unit Tests

Run the test suite:

```bash
# Install test dependencies
pip install pytest pytest-asyncio

# Run all tests
pytest

# Run specific test file
pytest tests/test_plugin_manager.py

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=core --cov=plugins
```

## Example Requests

### Basic MCP Protocol

**Ping:**

```bash
curl -X POST http://localhost:8000 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"ping"}'
```

**Initialize:**

```bash
curl -X POST http://localhost:8000 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":2,"method":"initialize","params":{}}'
```

**List Tools:**

```bash
curl -X POST http://localhost:8000 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/list"}'
```

### CKAN Plugin Tools

**Search Datasets:**

```bash
curl -X POST http://localhost:8000 \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc":"2.0",
    "id":4,
    "method":"tools/call",
    "params":{
      "name":"ckan.search_datasets",
      "arguments":{"query":"housing","limit":5}
    }
  }'
```

**Get Dataset:**

```bash
curl -X POST http://localhost:8000 \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc":"2.0",
    "id":5,
    "method":"tools/call",
    "params":{
      "name":"ckan.get_dataset",
      "arguments":{"dataset_id":"311-service-requests"}
    }
  }'
```

**Query Data:**

```bash
curl -X POST http://localhost:8000 \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc":"2.0",
    "id":6,
    "method":"tools/call",
    "params":{
      "name":"ckan.query_data",
      "arguments":{
        "resource_id":"YOUR_RESOURCE_ID",
        "limit":10
      }
    }
  }'
```

## Testing Lambda Deployment

After deploying with `./deploy.sh`, test your Lambda URL:

```bash
# Replace with your actual Lambda URL
LAMBDA_URL="https://your-lambda-url.lambda-url.us-east-1.on.aws"

# Test ping
curl -X POST $LAMBDA_URL \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"ping"}'

# Test tools/list
curl -X POST $LAMBDA_URL \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list"}'
```

## Testing with Go Client

If you've built the Go client:

```bash
# Build client
cd client && make build && cd ..

# Test ping
echo '{"jsonrpc":"2.0","id":1,"method":"ping"}' | \
  ./client/opencontext-client http://localhost:8000

# Test tools/list
echo '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' | \
  ./client/opencontext-client http://localhost:8000
```

## Troubleshooting

### Local Server Won't Start

**Error:** `ModuleNotFoundError: No module named 'aiohttp'`

**Solution:**

```bash
pip install aiohttp
```

### Plugin Initialization Fails

**Check:**

1. Data source URL is correct in `config.yaml`
2. Data source is publicly accessible
3. Internet connection works
4. API keys are set (if required)

### Connection Timeout

**Solutions:**

1. Increase timeout in `config.yaml`:
   ```yaml
   plugins:
     ckan:
       timeout: 120 # Increase if needed
   ```
2. Check data source is accessible
3. Check firewall/network settings

## Next Steps

- [Deployment Guide](DEPLOYMENT.md) - Deploy to AWS Lambda
- [Architecture Guide](ARCHITECTURE.md) - Understand the system
- [Custom Plugins Guide](CUSTOM_PLUGINS.md) - Create custom plugins
