# DataBorder Hub 端服务

独立的Hub端数据管理和分发服务。

## 📁 项目结构

```
hub/
├── src/                    # Hub端源码
│   ├── __init__.py        # 包初始化
│   ├── main.py            # 主启动脚本
│   ├── http_server.py     # HTTP服务器
│   ├── packager.py        # 数据打包器
│   ├── state_manager.py   # 状态管理器
│   ├── scheduler.py       # 调度器
│   ├── freshness_checker.py # 新鲜度检查器
│   └── calendar_reader.py # 日历读取器
├── tests/                  # Hub端测试
├── scripts/               # 部署脚本
│   ├── start_hub.sh       # 启动脚本
│   └── test_hub.sh        # 测试脚本
├── config/                # 配置文件
│   └── config.yaml       # Hub配置
├── docs/                  # 文档
├── requirements.txt       # Python依赖
└── README.md             # 本文件
```

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置

编辑 `config/config.yaml` 设置您的数据目录和参数。

### 3. 测试

```bash
bash scripts/test_hub.sh
```

### 4. 启动

```bash
bash scripts/start_hub.sh
```

或直接运行：

```bash
python src/main.py
```

## 📋 功能特性

- **数据打包**: 自动将数据集打包为ZIP文件
- **HTTP服务**: 提供数据包下载API
- **定时调度**: 定期检查数据新鲜度并自动打包
- **状态管理**: 持久化保存数据集状态
- **并发安全**: 支持多线程安全访问
- **路径安全**: 防止目录遍历攻击

## 🔧 API接口

### GET /api/datasets

获取所有数据集状态。

```json
{
  "datasets": [
    {
      "name": "stock-trading-data-pro",
      "status": "ready",
      "package_url": "/package/stock-trading-data-pro.zip",
      "updated_at": "2025-02-04T20:15:00Z",
      "freshness_ratio": 0.92
    }
  ]
}
```

### GET /package/{dataset_name}.zip

下载指定数据集的ZIP包。

支持Range请求实现断点续传。

## 🛠️ 配置说明

主要配置项：

- `hub.data_dir`: 数据根目录
- `hub.cache_dir`: 缓存目录
- `hub.port`: HTTP服务端口
- `datasets`: 数据集列表
- `hub.scheduler.interval_minutes`: 检查间隔（分钟）

详细配置请参考 `config/config.yaml`。

## 🧪 测试

运行测试套件：

```bash
cd tests && python -m unittest discover -v
```

或使用测试脚本：

```bash
bash scripts/test_hub.sh
```

## 📖 开发

本项目使用模块化设计：

- `main.py`: 主入口，整合所有组件
- `http_server.py`: HTTP API服务
- `scheduler.py`: 定时任务调度
- `packager.py`: 数据打包逻辑
- `state_manager.py`: 状态持久化
- `freshness_checker.py`: 数据新鲜度检查

## 📄 许可证

本项目遵循MIT许可证。