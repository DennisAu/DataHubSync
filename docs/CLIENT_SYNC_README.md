# DataHubSync 客户端同步脚本

## 概述

本文档描述了 DataHubSync 客户端同步脚本的功能、安装和使用方法。

### 功能特性

- **增量同步**：基于时间戳的智能增量同步，只下载更新过的数据
- **断点续传**：支持大文件下载的断点续传
- **多数据集支持**：可同时同步多个数据集
- **配置灵活**：通过YAML配置文件管理
- **日志记录**：详细的同步日志和错误追踪
- **自动部署**：提供自动化安装脚本

## 核心组件

### 1. 同步客户端 (`sync_client.py`)

主要功能模块：

- **DataSyncClient**: 核心同步客户端类
- **SyncResult**: 同步结果封装
- **配置管理**: YAML配置文件解析和验证
- **状态管理**: 同步状态持久化

#### 核心同步流程

```python
def sync_dataset(self, dataset_name: str) -> SyncResult:
    """同步单个数据集的完整流程"""
    1. 获取远程数据集状态 (/api/datasets)
    2. 对比本地时间戳，判断是否需要同步
    3. 下载数据包 (/package/{dataset}.zip)
    4. 解压覆盖本地数据
    5. 更新同步状态
```

### 2. 配置管理

#### 配置文件示例 (`config.yaml`)

```yaml
hub:
  url: "https://data.quantrade.fun"
  timeout: 300

datasets:
  - name: "stock-trading-data-pro"
    local_dir: "/data/stock-trading-data-pro"
  - name: "stock-fin-data-xbx"
    local_dir: "/data/stock-fin-data-xbx"

logging:
  level: "INFO"
  file: "logs/sync.log"
```

#### 状态文件 (`.last_sync.json`)

```json
{
  "stock-trading-data-pro": "2025-02-04T20:15:00Z",
  "stock-fin-data-xbx": "2025-02-04T07:05:00Z"
}
```

### 3. 部署脚本

#### 安装脚本 (`install_client.sh`)

自动化部署脚本，功能包括：

- 创建目录结构
- 复制程序文件
- 设置文件权限
- 配置crontab定时任务
- 设置日志轮转

使用方法：
```bash
sudo ./install_client.sh --setup-crontab --sync
```

#### 同步脚本 (`sync.sh`)

定时执行脚本，功能包括：

- 环境检查
- 日志记录
- 错误处理

#### 测试脚本 (`test_client.sh`)

部署验证脚本，检查：

- Python环境和依赖
- 配置文件格式
- 网络连接
- 目录权限

## 安装部署

### 1. 系统要求

- Linux 操作系统
- Python 3.6+
- 网络连接访问 DataHub 服务器

### 2. 安装依赖

```bash
pip3 install PyYAML
```

### 3. 自动安装

```bash
# 下载所有文件到目录
# 运行安装脚本
sudo ./install_client.sh --setup-crontab
```

### 4. 手动安装

```bash
# 创建目录
sudo mkdir -p /opt/datahubsync
sudo mkdir -p /data

# 复制文件
sudo cp sync_client.py /opt/datahubsync/
sudo cp sync.sh /opt/datahubsync/
sudo cp config_client_example.yaml /opt/datahubsync/config.yaml

# 设置权限
sudo chmod 755 /opt/datahubsync/sync.sh
sudo chmod 644 /opt/datahubsync/sync_client.py

# 配置crontab（每日8:15执行）
crontab -e
# 添加：15 8 * * * /opt/datahubsync/sync.sh
```

## 使用方法

### 1. 配置

编辑 `/opt/datahubsync/config.yaml`：
```yaml
hub:
  url: "https://your-datahub-server.com"
  
datasets:
  - name: "your-dataset-name"
    local_dir: "/path/to/your/data"
```

### 2. 测试

```bash
cd /opt/datahubsync
./test_client.sh
```

### 3. 手动同步

```bash
cd /opt/datahubsync
./sync.sh
```

### 4. 查看日志

```bash
tail -f /opt/datahubsync/logs/sync.log
```

## API接口

### 客户端API

```python
from sync_client import DataSyncClient

# 创建客户端
client = DataSyncClient(config, 'last_sync.json')

# 同步单个数据集
result = client.sync_dataset('stock-trading-data-pro')

# 同步所有数据集
results = client.sync_all()
```

### 服务器API

客户端依赖的服务器API：

- `GET /api/datasets` - 获取数据集列表
- `GET /package/{dataset}.zip` - 下载数据包

## 测试

### 运行测试套件

```bash
# 运行所有测试
python tests/test_sync_client.py
python tests/test_client_config.py
python tests/test_deployment.py

# 或者逐个运行
python -m unittest tests.test_sync_client -v
```

### 测试覆盖率

测试覆盖的主要功能：

- ✅ HTTP请求处理
- ✅ 文件下载和解压
- ✅ 配置文件解析
- ✅ 同步状态管理
- ✅ 错误处理
- ✅ 日志记录
- ✅ 部署脚本功能

## 故障排除

### 常见问题

1. **网络连接失败**
   ```bash
   ping your-datahub-server.com
   curl https://your-datahub-server.com/api/datasets
   ```

2. **权限问题**
   ```bash
   ls -la /opt/datahubsync/
   chmod 755 /opt/datahubsync/sync.sh
   ```

3. **Python模块缺失**
   ```bash
   pip3 install PyYAML
   ```

4. **磁盘空间不足**
   ```bash
   df -h /data
   ```

### 日志分析

查看详细错误信息：
```bash
tail -100 /opt/datahubsync/logs/sync.log
```

常见日志模式：
- `INFO: Starting sync for dataset: xxx` - 开始同步
- `INFO: Successfully synced dataset: xxx` - 同步成功
- `WARN: Dataset xxx up to date` - 已是最新版本
- `ERROR: Failed to download xxx` - 下载失败

## 性能优化

### 1. 网络优化

- 使用HTTPS确保传输安全
- 支持断点续传减少重复下载
- 并发连接池复用

### 2. 存储优化

- 增量同步减少磁盘I/O
- 日志轮转控制磁盘使用
- 临时文件自动清理

### 3. 调度优化

- 合理的同步时间避免高峰
- 错误重试机制提高可靠性
- 状态持久化支持中断恢复

## 安全考虑

1. **传输安全**：使用HTTPS加密传输
2. **文件权限**：适当的文件和目录权限
3. **日志审计**：完整的操作日志记录
4. **访问控制**：基于网络的访问限制

## 监控和维护

### 1. 监控指标

- 同步成功率
- 数据传输量
- 同步耗时
- 错误频率

### 2. 维护任务

- 定期检查日志
- 清理旧日志文件
- 更新配置文件
- 监控磁盘空间

---

**版本信息**: v2.0  
**最后更新**: 2025-02-04  
**维护者**: DataHubSync Team