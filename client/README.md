# DataBorder 客户端同步工具

独立的客户端数据同步工具，用于从DataBorder Hub同步量化数据集。

## 📁 项目结构

```
client/
├── src/                    # 源代码
│   ├── __init__.py        # 包初始化
│   ├── sync_client.py     # 核心同步逻辑
│   └── cli.py             # 命令行接口
├── tests/                  # 测试文件
│   ├── test_sync_client.py
│   ├── test_client_config.py
│   └── test_deployment.py
├── scripts/               # 部署脚本
│   ├── install_client.sh
│   ├── sync.sh
│   └── test_client.sh
├── config/                # 配置文件
│   └── config_client_example.yaml
├── docs/                  # 文档
│   ├── CLIENT_SYNC_README.md
│   └── PHASE2_COMPLETION_REPORT.md
├── requirements.txt       # Python依赖
└── README.md             # 本文件
```

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置

复制并编辑配置文件：

```bash
mkdir config
cp config/config_client_example.yaml config/config.yaml
```

编辑 `config/config.yaml` 设置你的服务器地址和要同步的数据集。

### 3. 运行同步

```bash
# 使用命令行接口
python src/cli.py

# 或者直接导入使用
python -c "
from src.sync_client import DataSyncClient
client = DataSyncClient('config/config.yaml')
client.sync_all()
"
```

## 📋 功能特性

- **增量同步**: 基于时间戳的智能同步，避免重复下载
- **断点续传**: 支持大文件下载的中断恢复  
- **多数据集**: 可同时同步多个数据集
- **自动化部署**: 提供完整的自动化部署脚本
- **配置灵活**: YAML配置文件，支持多个数据集配置
- **日志完整**: 详细的同步日志和错误处理

## 🛠️ 部署

使用自动化脚本部署：

```bash
# 运行安装脚本
bash scripts/install_client.sh

# 测试部署
bash scripts/test_client.sh

# 手动同步
bash scripts/sync.sh
```

## 🧪 测试

运行测试套件：

```bash
# 运行所有测试
cd tests && python -m unittest discover -v

# 运行特定测试
python tests/test_sync_client.py
python tests/test_client_config.py  
python tests/test_deployment.py
```

## 📖 详细文档

- [客户端同步详细文档](docs/CLIENT_SYNC_README.md)
- [Phase 2完成报告](docs/PHASE2_COMPLETION_REPORT.md)

## 🤝 开发

本项目使用测试驱动开发(TDD)方式，主要特性：

- 完整的单元测试覆盖
- 模块化设计，易于扩展
- 详细的错误处理和日志记录
- 类型注解和文档字符串

## 📄 许可证

本项目遵循MIT许可证。