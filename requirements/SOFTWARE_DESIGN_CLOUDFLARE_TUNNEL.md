# DataHubSync - 软件设计文档

> **版本**: 2.0 - 极简设计  
> **更新日期**: 2025-02-04  
> **项目路径**: `/opt/projects/DataHubSync`

---

## 1. 设计原则

| 原则 | 说明 |
|------|------|
| **KISS** | Keep It Simple, Stupid - 极度简化 |
| **YAGNI** | You Aren't Gonna Need It - 不要过度开发 |
| **预打包优先** | 每日数据全量打包，避免实时压缩 |
| **客户端决策** | 客户端对比日期，决定是否下载 |

---

## 2. 系统架构（极简版）

```
┌─────────────────────────────────────────────────────────────┐
│                        hub 电脑 (Windows)                    │
│                                                              │
│  ┌─────────────────┐      ┌─────────────────────────────┐   │
│  │   Data Update   │      │      DataHubSync Server     │   │
│  │   (其他系统)    │─────▶│                             │   │
│  │                 │      │  ┌─────────────────────┐    │   │
│  │ • 生成 CSV 文件 │      │  │ Data Freshness      │    │   │
│  │ • 更新数据目录  │      │  │ Checker             │    │   │
│  └─────────────────┘      │  │                     │    │   │
│                           │  │ • 扫描目录 mtime    │    │   │
│                           │  │ • 对比交易日历      │    │   │
│                           │  │ • 85% 阈值判断      │    │   │
│                           │  │ • 触发打包          │    │   │
│                           │  └─────────────────────┘    │   │
│                           │              │               │   │
│                           │              ▼               │   │
│                           │  ┌─────────────────────┐    │   │
│                           │  │ Async Packager      │    │   │
│                           │  │                     │    │   │
│                           │  │ • 后台打包 zip      │    │   │
│                           │  │ • 保存到 .cache/    │    │   │
│                           │  └─────────────────────┘    │   │
│                           │              │               │   │
│                           │              ▼               │   │
│                           │  ┌─────────────────────┐    │   │
│                           │  │ HTTP Server         │    │   │
│                           │  │                     │    │   │
│                           │  │ GET /api/datasets   │    │   │
│                           │  │ GET /package/*.zip  │    │   │
│                           │  └─────────────────────┘    │   │
│                           │              │               │   │
│                           └──────────────┼───────────────┘   │
│                                          │                   │
│                              ┌───────────┴───────────┐       │
│                              │  Cloudflare Tunnel    │       │
│                              └───────────┬───────────┘       │
└──────────────────────────────────────────┼───────────────────┘
                                           │
                    ┌──────────────────────┼──────────────────────┐
                    │                      │                      │
                    ▼                      ▼                      ▼
            ┌───────────────┐      ┌───────────────┐      ┌───────────────┐
            │   客户端 1     │      │   客户端 2-5   │      │   客户端 6     │
            │   (局域网)     │      │   (异地机房)   │      │   (海外)       │
            │               │      │               │      │               │
            │ 1. 请求日期   │      │  1. 请求日期   │      │  1. 请求日期   │
            │ 2. 对比本地   │      │  2. 对比本地   │      │  2. 对比本地   │
            │ 3. 下载 zip   │      │  3. 下载 zip   │      │  3. 下载 zip   │
            │ 4. 解压覆盖   │      │  4. 解压覆盖   │      │  4. 解压覆盖   │
            └───────────────┘      └───────────────┘      └───────────────┘
```

---

## 3. 核心概念

### 3.1 数据表（Dataset）

一个数据表对应一个数据目录：

| 数据表名称 | 目录 | 文件数 | 大小 |
|-----------|------|--------|------|
| `stock-trading-data-pro` | `F:\xbx_datas\stock-trading-data-pro\` | ~5600 | ~600MB |
| `stock-fin-data-xbx` | `F:\xbx_datas\stock-fin-data-xbx\` | ~3200 | ~30MB |
| `stock-etf-trading-data` | `F:\xbx_datas\stock-etf-trading-data\` | ~200 | ~20MB |

### 3.2 数据新鲜度

**判断标准**：数据表中 **85%** 以上文件的 `mtime` >= 上一个交易日

```
交易日历 (period_offset.csv):
2025-02-03  (周一)
2025-02-04  (周二)  ← 今天
2025-02-05  (周三)  ← 下一个交易日

今天 2月4日：
- 上一个交易日 = 2月3日
- 如果 85% 文件的 mtime >= 2025-02-03 00:00
- 则认为数据已更新到 2月3日
```

### 3.3 预打包流程

```
数据更新完成
    │
    ▼
┌─────────────────┐
│ 新鲜度检测      │
│ • 扫描目录      │
│ • 85% 阈值判断  │
└────────┬────────┘
         │ 达标
         ▼
┌─────────────────┐
│ 异步打包        │
│ • 创建 zip      │
│ • 压缩率 ~30%   │
│ • 保存 .cache/  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 更新状态        │
│ • last_updated  │
│ • zip 路径      │
└─────────────────┘
```

---

## 4. API 设计

### 4.1 获取数据表列表

```http
GET /api/datasets
```

**响应：**
```json
{
  "generated_at": "2025-02-04T20:30:00Z",
  "datasets": [
    {
      "name": "stock-trading-data-pro",
      "last_updated": "2025-02-04T20:15:00Z",
      "file_count": 5600,
      "total_size": 560000000,
      "package_ready": true,
      "package_size": 180000000
    },
    {
      "name": "stock-fin-data-xbx", 
      "last_updated": "2025-02-04T07:05:00Z",
      "file_count": 3200,
      "total_size": 32000000,
      "package_ready": true,
      "package_size": 10000000
    }
  ]
}
```

### 4.2 下载数据包

```http
GET /package/{dataset}.zip

示例：
GET /package/stock-trading-data-pro.zip
```

**响应：**
- 200 OK + zip 文件流
- 404 Not Found（包未生成）

---

## 5. 客户端同步流程

```python
# 伪代码

def sync_dataset(dataset_name):
    # 1. 获取远程状态
    remote = fetch(f"{HUB_URL}/api/datasets")
    remote_info = find(remote.datasets, name=dataset_name)
    
    # 2. 获取本地状态
    local_last_updated = read_local_timestamp(dataset_name)
    
    # 3. 对比日期
    if remote_info.last_updated <= local_last_updated:
        log(f"{dataset_name} already up to date")
        return
    
    log(f"{dataset_name} need update: local={local_last_updated}, remote={remote_info.last_updated}")
    
    # 4. 下载 zip
    zip_url = f"{HUB_URL}/package/{dataset_name}.zip"
    zip_path = f"/tmp/{dataset_name}.zip"
    
    download_file(zip_url, zip_path)
    
    # 5. 解压覆盖
    data_dir = f"/data/{dataset_name}"
    unzip(zip_path, data_dir)
    
    # 6. 更新本地时间戳
    write_local_timestamp(dataset_name, remote_info.last_updated)
    
    log(f"{dataset_name} synced successfully")


# 每日 8:15 执行
def main():
    datasets = ["stock-trading-data-pro", "stock-fin-data-xbx"]
    
    for dataset in datasets:
        try:
            sync_dataset(dataset)
        except Exception as e:
            log_error(f"Failed to sync {dataset}: {e}")
            # 继续下一个，不中断
```

---

## 6. hub 端组件

### 6.1 配置

```yaml
# config.yaml
server:
  port: 8080
  data_root: "F:\\xbx_datas"
  cache_dir: "F:\\xbx_datas\\.cache"
  
datasets:
  - name: "stock-trading-data-pro"
    path: "stock-trading-data-pro"
    freshness_threshold: 0.85
    
  - name: "stock-fin-data-xbx"
    path: "stock-fin-data-xbx"
    freshness_threshold: 0.85
    
calendar:
  period_offset_file: "F:\\xbx_datas\\period_offset.csv"
  
packaging:
  format: "zip"
  auto_package: true
```

### 6.2 核心模块

```python
class DataFreshnessChecker:
    """数据新鲜度检测器"""
    
    def check(self, dataset_path: str, threshold: float = 0.85) -> FreshnessResult:
        """
        检查数据目录新鲜度
        
        Returns:
            is_fresh: 是否达到新鲜度阈值
            last_updated: 85%分位数文件的mtime
            fresh_ratio: 新鲜文件比例
            fresh_count: 新鲜文件数
            total_count: 总文件数
        """
        pass


class AsyncPackager:
    """异步打包器"""
    
    def package(self, dataset_name: str, dataset_path: str, output_path: str):
        """
        后台打包数据目录为 zip
        """
        pass


class DataServer:
    """HTTP 服务器"""
    
    def handle_datasets(self, request) -> Response:
        """返回数据表列表和状态"""
        pass
    
    def handle_package(self, request, dataset_name: str) -> Response:
        """返回 zip 包"""
        pass
```

---

## 7. 取消的功能（YAGNI）

| 功能 | 取消原因 |
|------|---------|
| 增量更新 | 每日 5600 文件全更新，增量无意义 |
| 文件级 MD5 列表 | 太大，客户端只需知道数据表日期 |
| 断点续传 | zip 下载用 curl -C 即可 |
| 多线程下载 | 单线程下载 zip 足够快 |
| manifest 缓存 | 只需维护 last_updated 时间 |
| 数据生成 | DataHubSync 只负责分发，不生成数据 |

---

## 8. 流量成本

| 云厂商 | 入站流量（下载） | 出站流量（上传） |
|--------|-----------------|-----------------|
| 阿里云/腾讯云 | **免费** ✅ | 收费 |

**成本 = 0**
- 客户端下载 zip：入站流量免费
- hub 上传：通过 Cloudflare Tunnel（免费）

---

## 9. 存储占用

```
原始数据：
  stock-trading-data-pro: 600MB
  stock-fin-data-xbx: 30MB
  其他: ~50MB
  总计: ~680MB

压缩包（30%压缩率）：
  ~680MB × 0.3 = ~200MB

缓存策略（保留2个版本）：
  ~400MB

总占用: ~1.1GB
```

---

## 10. 时间线示例

```
2月4日 交易日
──────────────────────────────────────────────────────►
  20:00     20:15       20:20       次日 8:15     9:15
    │          │          │            │          │
    ▼          ▼          ▼            ▼          ▼
┌────────┐ ┌────────┐ ┌────────┐  ┌────────┐ ┌────────┐
│ 数据   │ │ 检测   │ │ 打包   │  │ 客户端 │ │ 开始   │
│ 更新   │ │ 85%    │ │ 完成   │  │ 同步   │ │ 交易   │
│ 完成   │ │ 达标   │ │ zip    │  │        │ │        │
└────────┘ └────────┘ └────────┘  └────────┘ └────────┘
              │
              ▼
        last_updated = "2025-02-04T20:15:00Z"
```

---

## 11. 更新记录

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0 | 2025-02-03 | 初始设计，支持增量更新 |
| 2.0 | 2025-02-04 | 极简设计，取消增量，预打包优先 |
