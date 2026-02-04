#!/bin/bash
# DataBorder Hub 启动脚本

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

print_info "DataBorder Hub Server"
print_info "====================="
print_info "Hub Directory: $HUB_DIR"

# 检查Python
if ! command -v python3 &> /dev/null; then
    print_error "Python3 not found"
    exit 1
fi

# 检查配置文件
CONFIG_FILE="$HUB_DIR/config/config.yaml"
if [ ! -f "$CONFIG_FILE" ]; then
    print_error "Configuration file not found: $CONFIG_FILE"
    exit 1
else
    print_info "✓ Configuration file found: $CONFIG_FILE"
fi

# 检查源码文件
MAIN_FILE="$HUB_DIR/src/main.py"
if [ ! -f "$MAIN_FILE" ]; then
    print_error "Main script not found: $MAIN_FILE"
    exit 1
else
    print_info "✓ Main script found: $MAIN_FILE"
fi

# 检查数据目录
DATA_DIR="$(grep -A 5 "data_dir:" "$CONFIG_FILE" | head -1 | cut -d: -f2 | tr -d ' "')"
if [ ! -d "$DATA_DIR" ]; then
    print_warn "Data directory not found: $DATA_DIR"
    print_info "Creating data directory..."
    mkdir -p "$DATA_DIR"
fi

# 设置环境变量
export PYTHONPATH="$HUB_DIR/src:$PYTHONPATH"
export HUB_CONFIG="$CONFIG_FILE"

print_info "Starting Hub Server..."
print_info "Press Ctrl+C to stop"
print_info ""

# 启动服务器
cd "$HUB_DIR"
python3 src/main.py