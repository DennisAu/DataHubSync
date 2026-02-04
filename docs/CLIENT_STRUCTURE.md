# DataBorder 客户端独立项目结构

## 📁 目录结构

```
DataBorder/
├── server.py                 # 服务端代码（与客户端分离）
├── src/                      # 服务端源码
├── tests/                    # 服务端测试
├── requirements/             # 需求文档
│   ├── TODO.md
│   ├── REQUIREMENTS_CLOUDFLARE_TUNNEL.md
│   └── SOFTWARE_DESIGN_CLOUDFLARE_TUNNEL.md
│
└── client/                   # 🎯 独立的客户端项目
    ├── src/                  # 客户端源码
    │   ├── __init__.py       # 包初始化
    │   ├── sync_client.py    # 核心同步逻辑
    │   └── cli.py            # 命令行接口
    ├── tests/                # 客户端测试
    │   ├── test_sync_client.py
    │   ├── test_client_config.py
    │   └── test_deployment.py
    ├── scripts/              # 部署脚本
    │   ├── install_client.sh
    │   ├── sync.sh
    │   └── test_client.sh
    ├── config/               # 配置文件
    │   └── config_client_example.yaml
    ├── docs/                 # 客户端文档
    │   ├── CLIENT_SYNC_README.md
    │   └── PHASE2_COMPLETION_REPORT.md
    ├── requirements.txt      # Python依赖
    ├── README.md            # 客户端说明
    └── package.sh           # 打包脚本
```

## 🚀 使用方式

### 1. 作为独立项目使用

```bash
# 进入客户端目录
cd client

# 安装依赖
pip install -r requirements.txt

# 配置
cp config/config_client_example.yaml config.yaml
# 编辑 config.yaml

# 运行同步
python src/cli.py
```

### 2. 打包部署

```bash
cd client
bash package.sh

# 生成的 databorder-client-1.0.0.tar.gz 可以独立分发
```

### 3. 自动化部署

```bash
cd client/scripts
sudo bash install_client.sh --setup-crontab
```

## 🎯 设计原则

1. **独立性**: 客户端代码完全独立，不依赖服务端代码
2. **模块化**: 清晰的模块划分，便于维护和扩展
3. **可测试**: 完整的单元测试覆盖
4. **易部署**: 提供自动化部署脚本
5. **文档全**: 详细的使用和部署文档

## 📦 分发

客户端可以独立分发：
- 源码形式：直接复制 client/ 目录
- 打包形式：使用 package.sh 生成 tar.gz 包
- 安装包：可以进一步制作为 deb/rpm 包

## 🔧 公共代码

只有基础的Python标准库和第三方包是公用的：
- HTTP处理: http.client, requests
- 文件操作: pathlib, zipfile, shutil
- 配置管理: yaml, json
- 日志记录: logging
- 时间处理: datetime

所有业务逻辑都在各自的模块中实现，确保代码的清晰分离。