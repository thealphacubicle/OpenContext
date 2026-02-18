# Testing Guide

## Quick Checks

### Config Validation

```bash
python3 -c "
import yaml
from core.validators import load_and_validate_config
config = load_and_validate_config('config.yaml')
print('✅ Config valid:', config['server_name'])
"
```

### Plugin Loading

```bash
python3 -c "
import asyncio, yaml
from core.plugin_manager import PluginManager
async def t():
    with open('config.yaml') as f: config = yaml.safe_load(f)
    pm = PluginManager(config)
    await pm.load_plugins()
    print('✅ Tools:', [t['name'] for t in pm.get_all_tools()])
    await pm.shutdown()
asyncio.run(t())
"
```

## Local Server

```bash
pip install aiohttp
python3 scripts/local_server.py
```

In another terminal:

```bash
# Ping
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"ping"}'

# List tools
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list"}'

# Call tool
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"ckan__search_datasets","arguments":{"query":"housing","limit":3}}}'
```

Or use: `./scripts/test_streamable_http.sh`

## Unit Tests

```bash
pip install pytest pytest-asyncio sqlparse
pytest
pytest tests/test_plugin_manager.py -v
pytest --cov=core --cov=plugins
```

## Lambda Deployment

```bash
LAMBDA_URL="https://your-lambda-url.lambda-url.us-east-1.on.aws"
curl -X POST $LAMBDA_URL/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"ping"}'
```

## Go Client

```bash
cd client && make build
echo '{"jsonrpc":"2.0","id":1,"method":"ping"}' | ./opencontext-client http://localhost:8000
```
