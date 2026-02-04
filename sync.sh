#!/bin/bash
# DataHubSync 客户端同步脚本
# 用于定时同步数据

set -e

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 检查Python是否可用
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 not found" >&2
    exit 1
fi

# 检查配置文件
if [ ! -f "config.yaml" ]; then
    echo "Error: config.yaml not found in $SCRIPT_DIR" >&2
    exit 1
fi

# 检查同步脚本
if [ ! -f "sync_client.py" ]; then
    echo "Error: sync_client.py not found in $SCRIPT_DIR" >&2
    exit 1
fi

# 创建日志目录
mkdir -p logs

# 记录开始时间
echo "$(date '+%Y-%m-%d %H:%M:%S') - Starting DataHubSync" >> logs/sync.log

# 运行同步
if python3 sync_client.py config.yaml >> logs/sync.log 2>&1; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') - DataHubSync completed successfully" >> logs/sync.log
    exit 0
else
    echo "$(date '+%Y-%m-%d %H:%M:%S') - DataHubSync failed with exit code $?" >> logs/sync.log
    exit 1
fi