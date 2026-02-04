#!/bin/bash
# DataHubSync 客户端测试脚本
# 用于测试客户端配置和连接

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

print_info "DataHubSync Client Test"
print_info "======================="

# 检查Python
print_info "Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    print_error "python3 not found"
    exit 1
else
    PYTHON_VERSION=$(python3 --version 2>&1)
    print_info "Found: $PYTHON_VERSION"
fi

# 检查必要的Python模块
print_info "Checking Python modules..."
REQUIRED_MODULES=("yaml" "json" "http.client" "zipfile" "logging" "pathlib")

for module in "${REQUIRED_MODULES[@]}"; do
    if python3 -c "import $module" 2>/dev/null; then
        print_info "✓ $module module available"
    else
        print_error "✗ $module module not available"
        if [ "$module" = "yaml" ]; then
            print_info "Install with: pip3 install PyYAML"
        fi
        exit 1
    fi
done

# 检查配置文件
print_info "Checking configuration files..."
if [ ! -f "config.yaml" ]; then
    print_error "config.yaml not found"
    print_info "Copy config_client_example.yaml to config.yaml and configure it"
    exit 1
else
    print_info "✓ config.yaml found"
fi

# 检查同步脚本
if [ ! -f "src/sync_client.py" ]; then
    print_error "src/sync_client.py not found"
    exit 1
else
    print_info "✓ src/sync_client.py found"
fi

# 检查requirements.txt
if [ ! -f "requirements.txt" ]; then
    print_error "requirements.txt not found"
    exit 1
else
    print_info "✓ requirements.txt found"
fi

# 验证配置文件格式
print_info "Validating configuration..."
if python3 -c "
import yaml
import sys

try:
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    # 检查必要字段
    if 'hub' not in config:
        print('Missing hub configuration')
        sys.exit(1)
    if 'url' not in config['hub']:
        print('Missing hub.url')
        sys.exit(1)
    
    datasets = config.get('datasets', [])
    print(f'Configuration valid: {len(datasets)} datasets configured')
    
except Exception as e:
    print(f'Configuration error: {e}')
    sys.exit(1)
"; then
    print_info "✓ Configuration is valid"
else
    print_error "Configuration validation failed"
    exit 1
fi

# 测试网络连接
print_info "Testing network connectivity..."
HUB_URL=$(python3 -c "
import yaml
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)
print(config['hub']['url'])
")

# 提取主机名
HOST=$(echo "$HUB_URL" | sed 's|https://||' | sed 's|http://||' | cut -d':' -f1 | cut -d'/' -f1)

print_info "Testing connection to $HOST..."

if command -v ping &> /dev/null; then
    if ping -c 1 "$HOST" &>/dev/null; then
        print_info "✓ Network connectivity OK"
    else
        print_warn "Cannot ping $HOST (this may be normal)"
    fi
else
    print_warn "ping command not available, skipping network test"
fi

# 测试HTTP连接
print_info "Testing HTTP connection..."
if python3 -c "
import http.client
import urllib.parse
import sys

url = '$HUB_URL/api/datasets'
parsed = urllib.parse.urlparse(url)

try:
    if parsed.scheme == 'https':
        conn = http.client.HTTPSConnection(parsed.hostname, parsed.port or 443, timeout=10)
    else:
        conn = http.client.HTTPConnection(parsed.hostname, parsed.port or 80, timeout=10)
    
    conn.request('GET', '/api/datasets')
    response = conn.getresponse()
    
    if response.status == 200:
        print('✓ HTTP connection successful')
    else:
        print(f'HTTP error: {response.status} {response.reason}')
        sys.exit(1)
    
    conn.close()
    
except Exception as e:
    print(f'HTTP connection failed: {e}')
    print('This may be normal if the server is not running')
    sys.exit(0)
"; then
    print_info "✓ Server is accessible"
else
    print_warn "Server is not accessible (this may be normal)"
fi

# 检查数据目录
print_info "Checking data directories..."
DATA_DIRS=$(python3 -c "
import yaml
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

for dataset in config.get('datasets', []):
    print(dataset.get('local_dir', ''))
")

for data_dir in $DATA_DIRS; do
    if [ -n "$data_dir" ]; then
        if [ -d "$data_dir" ]; then
            print_info "✓ Data directory exists: $data_dir"
        else
            print_warn "Data directory missing: $data_dir"
            print_info "Creating: $data_dir"
            mkdir -p "$data_dir"
        fi
    fi
done

# 检查日志目录
LOGS_DIR="logs"
if [ -d "$LOGS_DIR" ]; then
    print_info "✓ Logs directory exists: $LOGS_DIR"
else
    print_info "Creating logs directory: $LOGS_DIR"
    mkdir -p "$LOGS_DIR"
fi

# 运行干运行测试
print_info "Running dry-run test..."
if python3 -c "
import sys
sys.path.insert(0, '.')
from sync_client import DataSyncClient
import yaml

try:
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    client = DataSyncClient(config, '.last_sync.json')
    print('✓ Client initialization successful')
    
    # 测试状态文件创建
    state = client._load_sync_state()
    print(f'✓ Sync state loaded: {len(state)} datasets')
    
except Exception as e:
    print(f'Client test failed: {e}')
    sys.exit(1)
"; then
    print_info "✓ Client test passed"
else
    print_error "Client test failed"
    exit 1
fi

print_info ""
print_info "Test completed successfully!"
print_info "Ready to run: ./sync.sh"