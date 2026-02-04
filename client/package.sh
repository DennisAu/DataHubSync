#!/bin/bash
# 客户端打包脚本

set -e

PACKAGE_NAME="databorder-client"
VERSION="1.0.0"
PACKAGE_DIR="${PACKAGE_NAME}-${VERSION}"

echo "🔧 打包 DataBorder 客户端..."
echo "包名: $PACKAGE_NAME"
echo "版本: $VERSION"

# 创建临时目录
rm -rf "$PACKAGE_DIR"
mkdir -p "$PACKAGE_DIR"

# 复制客户端文件
echo "📁 复制客户端文件..."
cp -r src "$PACKAGE_DIR/"
cp -r scripts "$PACKAGE_DIR/"
cp -r config "$PACKAGE_DIR/"
cp -r docs "$PACKAGE_DIR/"
cp requirements.txt "$PACKAGE_DIR/"
cp README.md "$PACKAGE_DIR/"

# 创建安装说明
cat > "$PACKAGE_DIR/INSTALL.md" << 'EOF'
# DataBorder 客户端安装指南

## 快速安装

1. 解压到目标目录：
```bash
tar -xzf databorder-client-1.0.0.tar.gz
cd databorder-client-1.0.0
```

2. 安装依赖：
```bash
pip install -r requirements.txt
```

3. 配置：
```bash
cp config/config_client_example.yaml config.yaml
# 编辑 config.yaml 设置你的配置
```

4. 测试：
```bash
python src/cli.py --dry-run
```

5. 部署（可选）：
```bash
sudo bash scripts/install_client.sh --setup-crontab
```

详细文档请参考 docs/ 目录。
EOF

# 创建tar包
echo "📦 创建压缩包..."
tar -czf "${PACKAGE_NAME}-${VERSION}.tar.gz" "$PACKAGE_DIR"

# 清理临时目录
rm -rf "$PACKAGE_DIR"

echo "✅ 打包完成: ${PACKAGE_NAME}-${VERSION}.tar.gz"
echo ""
echo "部署步骤："
echo "1. 将 ${PACKAGE_NAME}-${VERSION}.tar.gz 复制到目标服务器"
echo "2. 解压并按照 INSTALL.md 中的说明进行安装"