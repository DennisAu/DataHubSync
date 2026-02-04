# DataHubSync - 软件设计文档

> **版本**: 2.1 - 新鲜度规则调整  
> **更新日期**: 2026-02-04  
> **项目路径**: `/opt/projects/DataHubSync`（仓库示例路径；hub 运行于 Windows，客户端示例为 Linux）

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
│                           │  │ • 扫描 CSV mtime    │    │   │
│                           │  │ • 统计多数分钟      │    │   │
│                           │  │ • newer_ratio>=0.30 │    │   │
│                           │  │ • 60s 防抖          │    │   │
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

### 2.1 Cloudflare Tunnel 要点

- hub 上运行 cloudflared（Windows 服务），对外暴露 HTTPS 入口
- 公网域名指向 Tunnel，转发到本地 HTTP Server
- 客户端仅需 HTTPS 访问，不安装额外软件
- 可选：通过 Cloudflare Access 或 IP 白名单做访问控制

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

**判断标准（数据表级别）**：

1. 扫描数据目录下所有 CSV 文件的 `mtime`，按分钟粒度取整（由 `freshness.mtime_granularity` 指定，默认 minute）。
2. 统计出现次数最多的分钟（majority-minute），作为数据表的 `majority_minute`。
3. 计算 `newer_ratio` = `mtime > hub.last_updated` 的 CSV 数量 / CSV 总数。
4. 当 `newer_ratio >= 0.30` 且距离上次触发打包 >= 60s，认为数据已更新并触发打包。

> 不依赖交易日历文件，仅基于数据目录内 CSV 文件的 mtime。  
> 时间格式统一为 ISO8601，示例使用 +08:00。

```
示例：
hub.last_updated = 2025-02-04T20:15:00+08:00
扫描 5600 个 CSV：
- 2100 个 mtime > hub.last_updated (newer_ratio = 0.375)
- majority_minute = 2025-02-04T20:16:00+08:00
=> newer_ratio >= 0.30 且防抖通过，触发打包并更新 last_updated
```

### 3.3 预打包流程

```
数据更新完成
    │
    ▼
┌─────────────────┐
│ 新鲜度检测      │
│ • 扫描 CSV      │
│ • 多数分钟统计  │
│ • newer_ratio>=0.30 │
│ • 60s 防抖      │
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
  "generated_at": "2025-02-04T20:30:00+08:00",
  "datasets": [
    {
      "name": "stock-trading-data-pro",
      "last_updated": "2025-02-04T20:15:00+08:00",
      "file_count": 5600,
      "total_size": 560000000,
      "package_ready": true,
      "package_size": 180000000
    },
    {
      "name": "stock-fin-data-xbx", 
      "last_updated": "2025-02-04T07:05:00+08:00",
      "file_count": 3200,
      "total_size": 32000000,
      "package_ready": true,
      "package_size": 10000000
    },
    {
      "name": "stock-etf-trading-data",
      "last_updated": "2025-02-04T20:10:00+08:00",
      "file_count": 200,
      "total_size": 20000000,
      "package_ready": true,
      "package_size": 6000000
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

> 客户端脚本需兼容 Linux/Windows。示例以 Linux 路径，Windows 请替换为对应盘符路径。Hub 运行于 Windows（数据路径示例见 6.1）。

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


# 每日 8:15 执行（本地时间 +08:00）
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
    newer_ratio_threshold: 0.30
    
  - name: "stock-fin-data-xbx"
    path: "stock-fin-data-xbx"
    newer_ratio_threshold: 0.30

  - name: "stock-etf-trading-data"
    path: "stock-etf-trading-data"
    newer_ratio_threshold: 0.30

freshness:
  debounce_seconds: 60
  mtime_granularity: "minute"
  
packaging:
  format: "zip"
  auto_package: true
```

### 6.2 核心模块

```python
class DataFreshnessChecker:
    """数据新鲜度检测器"""
    
    def check(
        self,
        dataset_path: str,
        hub_last_updated: datetime,
        newer_ratio_threshold: float = 0.30,
        debounce_seconds: int = 60,
        mtime_granularity: str = "minute",
    ) -> FreshnessResult:
        """
        检查数据目录新鲜度
        
        Returns:
            is_fresh: 是否达到阈值（newer_ratio>=0.30 且防抖通过）
            last_updated: majority_minute（作为新的 last_updated）
            newer_ratio: mtime > hub_last_updated 的比例
            newer_count: 新于 hub 的文件数
            total_count: 总文件数
            mtime_granularity: mtime 粒度（minute）
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

| 云厂商 | 入站流量（客户端→云厂商） | 出站流量（云厂商→客户端） |
|--------|-----------------|-----------------|
| 阿里云/腾讯云 | **免费** ✅ | 收费 |

**当前方案成本 = 0（本地 Hub + Cloudflare Tunnel）**
- 客户端下载通过 Cloudflare Tunnel 访问本地 Hub，不使用云厂商出站
- 若改为云厂商托管/出站带宽方案，可能产生出站费用

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
2月4日 交易日（本地时间 +08:00）
──────────────────────────────────────────────────────►
  20:00     20:15       20:20       次日 8:15     9:15
    │          │          │            │          │
    ▼          ▼          ▼            ▼          ▼
┌────────┐ ┌────────┐ ┌────────┐  ┌────────┐ ┌────────┐
│ 数据   │ │ 检测   │ │ 打包   │  │ 客户端 │ │ 开始   │
│ 更新   │ │ 30%    │ │ 完成   │  │ 同步   │ │ 交易   │
│ 完成   │ │ 达标   │ │ zip    │  │        │ │        │
└────────┘ └────────┘ └────────┘  └────────┘ └────────┘
             │
             ▼
       last_updated = "2025-02-04T20:16:00+08:00"
```

---

## 11. 更新记录

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0 | 2025-02-03 | 初始设计，支持增量更新 |
| 2.0 | 2025-02-04 | 极简设计，取消增量，预打包优先 |
| 2.1 | 2026-02-04 | 新鲜度改为多数分钟 + newer_ratio>=0.30，加入 60s 防抖，取消交易日历 |
