#!/bin/bash
# DataHubSync 客户端安装脚本
# 用于在Linux服务器上部署客户端

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

# 默认配置
INSTALL_DIR="/opt/datahubsync"
DATA_DIR="/data"
HUB_URL="https://data.quantrade.fun"
SYNCHRONIZE=false
SETUP_CRONTAB=false

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --install-dir)
            INSTALL_DIR="$2"
            shift 2
            ;;
        --data-dir)
            DATA_DIR="$2"
            shift 2
            ;;
        --hub-url)
            HUB_URL="$2"
            shift 2
            ;;
        --sync)
            SYNCHRONIZE=true
            shift
            ;;
        --setup-crontab)
            SETUP_CRONTAB=true
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo "Options:"
            echo "  --install-dir DIR     Installation directory (default: /opt/datahubsync)"
            echo "  --data-dir DIR       Data directory (default: /data)"
            echo "  --hub-url URL        Hub server URL (default: https://data.quantrade.fun)"
            echo "  --sync               Run initial sync after installation"
            echo "  --setup-crontab     Setup crontab entry for daily sync"
            echo "  --help              Show this help message"
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# 检查是否以root权限运行
if [[ $EUID -ne 0 ]]; then
    print_error "This script must be run as root"
    exit 1
fi

print_info "Installing DataHubSync client to $INSTALL_DIR"

# 创建安装目录
mkdir -p "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR/logs"
mkdir -p "$DATA_DIR"

# 复制文件
print_info "Copying files..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cp "$SCRIPT_DIR/sync_client.py" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/sync.sh" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/config_client_example.yaml" "$INSTALL_DIR/config.yaml"

# 设置权限
chmod 755 "$INSTALL_DIR/sync.sh"
chmod 644 "$INSTALL_DIR/sync_client.py"
chmod 644 "$INSTALL_DIR/config.yaml"

# 创建同步状态文件
touch "$INSTALL_DIR/.last_sync.json"

# 创建数据目录
for dataset in "stock-trading-data-pro" "stock-fin-data-xbx" "stock-etf-trading-data"; do
    mkdir -p "$DATA_DIR/$dataset"
done

# 更新配置文件中的URL
print_info "Updating configuration..."
sed -i "s|https://test.datahub.com|$HUB_URL|g" "$INSTALL_DIR/config.yaml"
sed -i "s|/data/|$DATA_DIR/|g" "$INSTALL_DIR/config.yaml"

# 设置crontab（如果请求）
if [ "$SETUP_CRONTAB" = true ]; then
    print_info "Setting up crontab..."
    
    # 检查是否已存在crontab条目
    if crontab -l 2>/dev/null | grep -q "$INSTALL_DIR/sync.sh"; then
        print_warn "Crontab entry already exists"
    else
        # 添加crontab条目（每天8:15执行）
        (crontab -l 2>/dev/null; echo "15 8 * * * $INSTALL_DIR/sync.sh") | crontab -
        print_info "Crontab entry added: 15 8 * * * $INSTALL_DIR/sync.sh"
    fi
fi

# 运行初始同步（如果请求）
if [ "$SYNCHRONIZE" = true ]; then
    print_info "Running initial sync..."
    cd "$INSTALL_DIR"
    if ./sync.sh; then
        print_info "Initial sync completed successfully"
    else
        print_warn "Initial sync failed (this may be normal if server is not ready)"
    fi
fi

# 创建logrotate配置
print_info "Setting up log rotation..."
cat > /etc/logrotate.d/datahubsync << EOF
$INSTALL_DIR/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 644 root root
}
EOF

print_info "Installation completed successfully!"
print_info "Configuration file: $INSTALL_DIR/config.yaml"
print_info "Sync script: $INSTALL_DIR/sync.sh"
print_info "Logs directory: $INSTALL_DIR/logs"
print_info "Data directory: $DATA_DIR"

if [ "$SETUP_CRONTAB" = false ]; then
    print_info "To setup crontab manually, run:"
    print_info "  crontab -e"
    print_info "  and add: 15 8 * * * $INSTALL_DIR/sync.sh"
fi

print_info "To run sync manually, execute:"
print_info "  $INSTALL_DIR/sync.sh"