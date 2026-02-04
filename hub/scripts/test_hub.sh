#!/bin/bash
# DataBorder Hub 测试脚本

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
HUB_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

print_info "DataBorder Hub Test Suite"
print_info "========================="
print_info "Hub Directory: $HUB_DIR"

# 检查Python
print_info "Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    print_error "Python3 not found"
    exit 1
else
    PYTHON_VERSION=$(python3 --version 2>&1)
    print_info "✓ Found: $PYTHON_VERSION"
fi

# 检查必要的Python模块
print_info "Checking Python modules..."
REQUIRED_MODULES=("yaml" "json" "http.server" "socketserver" "threading" "pathlib" "datetime" "logging")

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
CONFIG_FILE="$HUB_DIR/config/config.yaml"
if [ ! -f "$CONFIG_FILE" ]; then
    print_error "config.yaml not found"
    exit 1
else
    print_info "✓ config.yaml found"
fi

# 验证配置文件格式
print_info "Validating configuration..."
if python3 -c "
import yaml
import sys

try:
    with open('$CONFIG_FILE', 'r') as f:
        config = yaml.safe_load(f)
    
    # 检查必要字段
    if 'hub' not in config:
        print('Missing hub configuration')
        sys.exit(1)
    if 'data_dir' not in config['hub']:
        print('Missing hub.data_dir')
        sys.exit(1)
    
    print('✓ Configuration valid')
    
except Exception as e:
    print(f'Configuration error: {e}')
    sys.exit(1)
"; then
    print_info "✓ Configuration format valid"
else
    print_error "Configuration validation failed"
    exit 1
fi

# 检查源码文件
print_info "Checking source files..."
REQUIRED_FILES=("main.py" "http_server.py" "packager.py" "state_manager.py" "scheduler.py")

for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$HUB_DIR/src/$file" ]; then
        print_info "✓ src/$file found"
    else
        print_error "✗ src/$file not found"
        exit 1
    fi
done

# 运行单元测试
print_info "Running unit tests..."
cd "$HUB_DIR"

# 设置环境变量
export PYTHONPATH="$HUB_DIR/src:$PYTHONPATH"

# 运行测试
TEST_FILES=$(find tests -name "test_*.py" 2>/dev/null || true)
if [ -n "$TEST_FILES" ]; then
    for test_file in $TEST_FILES; do
        print_info "Running $test_file..."
        if python3 "$test_file"; then
            print_info "✓ $test_file passed"
        else
            print_error "✗ $test_file failed"
            exit 1
        fi
    done
else
    print_warn "No test files found in tests/ directory"
fi

print_info ""
print_info "✅ Hub test completed successfully!"
print_info "Hub is ready to start with: bash scripts/start_hub.sh"