#!/bin/bash
# OpenContext Deployment Script
#
# This script validates configuration and deploys the MCP server to AWS Lambda.
# It enforces the "one fork = one MCP server" rule.

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Script directory (scripts/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Project root (parent directory)
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

echo -e "${GREEN}🚀 OpenContext Deployment${NC}"
echo "================================"
echo ""

# Check if config.yaml exists
if [ ! -f "config.yaml" ]; then
    echo -e "${RED}❌ Error: config.yaml not found${NC}"
    echo "Create config.yaml based on the template in the repository."
    exit 1
fi

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Error: python3 not found${NC}"
    echo "Please install Python 3.11 or later."
    exit 1
fi

# Check if Terraform is available
if ! command -v terraform &> /dev/null; then
    echo -e "${RED}❌ Error: terraform not found${NC}"
    echo "Please install Terraform: https://www.terraform.io/downloads"
    exit 1
fi

echo -e "${YELLOW}📋 Step 1: Validating configuration...${NC}"

# Count enabled plugins using Python for reliable YAML parsing
ENABLED_COUNT=$(python3 << 'EOF'
import yaml
import sys

try:
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    plugins = config.get('plugins', {})
    enabled = []
    
    for plugin_name, plugin_config in plugins.items():
        if isinstance(plugin_config, dict) and plugin_config.get('enabled', False):
            enabled.append(plugin_name)
    
    count = len(enabled)
    
    if count == 0:
        print("0", file=sys.stderr)
        print("No plugins enabled", file=sys.stderr)
        sys.exit(1)
    elif count > 1:
        print(str(count), file=sys.stderr)
        print(" ".join(enabled), file=sys.stderr)
        sys.exit(2)
    else:
        print(count)
        print(enabled[0], file=sys.stderr)
        sys.exit(0)
        
except Exception as e:
    print(f"Error parsing config.yaml: {e}", file=sys.stderr)
    sys.exit(3)
EOF
)

EXIT_CODE=$?

if [ $EXIT_CODE -eq 1 ]; then
    echo -e "${RED}❌ Configuration Error: No Plugins Enabled${NC}"
    echo ""
    echo "You must enable exactly ONE plugin in config.yaml."
    echo ""
    echo "To enable a plugin, set 'enabled: true' for:"
    echo "  • ckan"
    echo "  • A custom plugin in custom_plugins/"
    echo ""
    echo "See docs/QUICKSTART.md for setup instructions."
    exit 1
elif [ $EXIT_CODE -eq 2 ]; then
    ENABLED_PLUGINS=$(python3 << 'EOF'
import yaml
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)
plugins = config.get('plugins', {})
enabled = [name for name, cfg in plugins.items() 
           if isinstance(cfg, dict) and cfg.get('enabled', False)]
print("\n".join(f"  • {name}" for name in enabled))
EOF
    )
    
    echo -e "${RED}❌ Configuration Error: Multiple Plugins Enabled${NC}"
    echo ""
    echo "You have $ENABLED_COUNT plugins enabled in config.yaml:"
    echo "$ENABLED_PLUGINS"
    echo ""
    echo "OpenContext enforces: One Fork = One MCP Server"
    echo ""
    echo "This keeps deployments:"
    echo "  ✓ Simple and focused"
    echo "  ✓ Independently scalable"
    echo "  ✓ Easy to maintain"
    echo ""
    echo "To deploy multiple MCP servers:"
    echo ""
    echo "  1. Fork this repository again"
    echo "     Example: opencontext-opendata, opencontext-mbta"
    echo ""
    echo "  2. Configure ONE plugin per fork"
    FIRST_PLUGIN=$(echo "$ENABLED_PLUGINS" | head -n1 | sed 's/  • //')
    SECOND_PLUGIN=$(echo "$ENABLED_PLUGINS" | tail -n1 | sed 's/  • //')
    echo "     Fork #1: Enable $FIRST_PLUGIN only"
    echo "     Fork #2: Enable $SECOND_PLUGIN only"
    echo ""
    echo "  3. Deploy each fork separately"
    echo "     ./scripts/deploy.sh (in each fork)"
    echo ""
    echo "See docs/ARCHITECTURE.md for details."
    exit 1
elif [ $EXIT_CODE -ne 0 ]; then
    echo -e "${RED}❌ Error validating configuration${NC}"
    exit 1
fi

ENABLED_PLUGIN=$(python3 << 'EOF'
import yaml
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)
plugins = config.get('plugins', {})
enabled = [name for name, cfg in plugins.items() 
           if isinstance(cfg, dict) and cfg.get('enabled', False)]
print(enabled[0])
EOF
)

echo -e "${GREEN}✓ Configuration valid: ${ENABLED_PLUGIN} plugin enabled${NC}"
echo ""

# Extract server name and AWS settings
SERVER_NAME=$(python3 << 'EOF'
import yaml
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)
print(config.get('server_name', 'my-mcp-server'))
EOF
)

AWS_REGION=$(python3 << 'EOF'
import yaml
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)
print(config.get('aws', {}).get('region', 'us-east-1'))
EOF
)

LAMBDA_NAME=$(python3 << 'EOF'
import yaml
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)
lambda_name = config.get('aws', {}).get('lambda_name', '')
if not lambda_name:
    server_name = config.get('server_name', 'my-mcp-server')
    lambda_name = server_name.lower().replace(' ', '-')
print(lambda_name)
EOF
)

echo -e "${YELLOW}📦 Step 2: Packaging Lambda code...${NC}"

# Create deployment package directory
PACKAGE_DIR=".deploy"
rm -rf "$PACKAGE_DIR"
mkdir -p "$PACKAGE_DIR"

# Copy code to package directory
cp -r core "$PACKAGE_DIR/"
cp -r plugins "$PACKAGE_DIR/"
cp -r custom_plugins "$PACKAGE_DIR/" 2>/dev/null || mkdir -p "$PACKAGE_DIR/custom_plugins"
cp -r server "$PACKAGE_DIR/"
cp requirements.txt "$PACKAGE_DIR/" 2>/dev/null || true

# Create zip file
ZIP_FILE="lambda-deployment.zip"
cd "$PACKAGE_DIR"
zip -r "../$ZIP_FILE" . > /dev/null
cd ..

echo -e "${GREEN}✓ Lambda package created: $ZIP_FILE${NC}"
echo ""

echo -e "${YELLOW}🏗️  Step 3: Deploying with Terraform...${NC}"

# Initialize Terraform if needed
if [ ! -d "terraform/aws/.terraform" ]; then
    echo "Initializing Terraform..."
    cd terraform/aws
    terraform init
    cd ../..
fi

# Deploy with Terraform
cd terraform/aws
terraform apply \
    -var="lambda_name=$LAMBDA_NAME" \
    -var="aws_region=$AWS_REGION" \
    -var="config_file=../config.yaml" \
    -auto-approve

# Get Lambda URL from Terraform output
LAMBDA_URL=$(terraform output -raw lambda_url 2>/dev/null || echo "")

cd ..

echo ""
echo -e "${GREEN}✅ Deployment complete!${NC}"
echo ""
echo "Lambda Function URL:"
echo -e "${GREEN}$LAMBDA_URL${NC}"
echo ""
echo "To use with Claude Desktop:"
echo ""
echo "1. Download opencontext-client binary from:"
echo "   https://github.com/thealphacubicle/OpenContext/releases"
echo ""
echo "2. Add to your Claude Desktop config:"
echo ""
echo "  \"mcpServers\": {"
echo "    \"$SERVER_NAME\": {"
echo "      \"command\": \"/path/to/opencontext-client\","
echo "      \"args\": ["
echo "        \"$LAMBDA_URL\""
echo "      ]"
echo "    }"
echo "  }"
echo ""
echo "For direct HTTP access, use the Lambda URL directly with MCP JSON-RPC format."
echo ""

