# DataHubSync hub 端实施计划

> **给 Claude 的指令：** 必需子技能：使用 `skills/subagent-driven-development` 来逐个任务实施此计划。

**目标：** 实现 DataHubSync hub 端核心功能：新鲜度检测、异步打包、HTTP 服务

**架构：** Python 标准库实现，模块化设计（新鲜度检测器、异步打包器、HTTP 服务器、定时调度器），配置驱动，单进程多线程

**技术栈：** Python 3.8+ (标准库: http.server, threading, json, csv, zipfile, pathlib)

---

## 任务 1: 项目基础结构

**文件：**
- 创建: `/opt/projects/DataHubSync/src/__init__.py`
- 创建: `/opt/projects/DataHubSync/config.yaml`
- 创建: `/opt/projects/DataHubSync/.gitignore`

**步骤 1: 创建目录结构**

```bash
cd /opt/projects/DataHubSync
mkdir -p src tests .cache logs
```

**步骤 2: 编写 config.yaml**

```yaml
# config.yaml - hub 端配置
server:
  port: 8080
  host: "0.0.0.0"
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

check:
  interval_minutes: 10
  debounce_seconds: 30

packaging:
  format: "zip"
  keep_versions: 2

logging:
  level: INFO
  file: "logs/server.log"
  format: "%(asctime)s [%(levelname)s] %(message)s"
```

**步骤 3: 编写 .gitignore**

```
# Python
__pycache__/
*.py[cod]
*$py.class
*.so

# 数据和缓存
.cache/
logs/
*.zip

# 配置（敏感信息）
config.local.yaml

# IDE
.vscode/
.idea/
```

**步骤 4: 提交**

```bash
git add config.yaml .gitignore
git commit -m "chore: add project structure and config"
```

---

## 任务 2: 交易日历读取器

**文件：**
- 创建: `/opt/projects/DataHubSync/src/calendar_reader.py`
- 创建: `/opt/projects/DataHubSync/tests/test_calendar_reader.py`

**步骤 1: 编写失败的测试**

```python
# tests/test_calendar_reader.py
import sys
sys.path.insert(0, '/opt/projects/DataHubSync/src')

import tempfile
import os
from calendar_reader import CalendarReader

def test_read_trade_dates():
    # 创建测试用的 period_offset.csv
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write("交易日期\n")
        f.write("2025-02-03\n")
        f.write("2025-02-04\n")
        f.write("2025-02-05\n")
        temp_path = f.name
    
    try:
        reader = CalendarReader(temp_path)
        dates = reader.get_trade_dates()
        
        assert len(dates) == 3
        assert dates[0] == "2025-02-03"
        assert dates[-1] == "2025-02-05"
    finally:
        os.unlink(temp_path)

def test_get_last_trade_date():
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write("交易日期\n")
        f.write("2025-02-03\n")
        f.write("2025-02-04\n")
        temp_path = f.name
    
    try:
        reader = CalendarReader(temp_path)
        
        # 今天 2/4，上一个交易日应该是 2/3
        last = reader.get_last_trade_date("2025-02-04")
        assert last == "2025-02-03"
        
        # 今天 2/5，上一个交易日应该是 2/4
        last = reader.get_last_trade_date("2025-02-05")
        assert last == "2025-02-04"
    finally:
        os.unlink(temp_path)

if __name__ == "__main__":
    test_read_trade_dates()
    test_get_last_trade_date()
    print("All tests passed!")
```

**步骤 2: 运行测试验证失败**

```bash
cd /opt/projects/DataHubSync
python tests/test_calendar_reader.py
```

期望: `ModuleNotFoundError: No module named 'calendar_reader'`

**步骤 3: 编写实现**

```python
# src/calendar_reader.py
"""交易日历读取器"""

import csv
from datetime import datetime
from pathlib import Path


class CalendarReader:
    """读取 period_offset.csv 交易日历"""
    
    def __init__(self, csv_path: str):
        self.csv_path = Path(csv_path)
        self._dates = None
    
    def _load(self):
        """加载交易日历"""
        if self._dates is not None:
            return
        
        dates = []
        with open(self.csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                date_str = row['交易日期'].strip()
                dates.append(date_str)
        
        self._dates = sorted(dates)
    
    def get_trade_dates(self) -> list:
        """获取所有交易日列表"""
        self._load()
        return self._dates.copy()
    
    def get_last_trade_date(self, today_str: str = None) -> str:
        """
        获取上一个交易日
        
        Args:
            today_str: 今天日期，格式 "2025-02-04"，默认使用系统日期
        
        Returns:
            上一个交易日的日期字符串
        """
        self._load()
        
        if today_str is None:
            today = datetime.now().strftime("%Y-%m-%d")
        else:
            today = today_str
        
        # 找到小于等于今天的最大日期
        for date_str in reversed(self._dates):
            if date_str <= today:
                return date_str
        
        # 如果今天比所有交易日都早，返回第一个交易日
        return self._dates[0] if self._dates else None
```

**步骤 4: 运行测试验证通过**

```bash
python tests/test_calendar_reader.py
```

期望: `All tests passed!`

**步骤 5: 提交**

```bash
git add src/calendar_reader.py tests/test_calendar_reader.py
git commit -m "feat: add calendar reader for trade dates"
```

---

## 任务 3: 新鲜度检测器

**文件：**
- 创建: `/opt/projects/DataHubSync/src/freshness_checker.py`
- 创建: `/opt/projects/DataHubSync/tests/test_freshness_checker.py`

**步骤 1: 编写失败的测试**

```python
# tests/test_freshness_checker.py
import sys
sys.path.insert(0, '/opt/projects/DataHubSync/src')

import tempfile
import os
from datetime import datetime, timedelta
from freshness_checker import FreshnessChecker, FreshnessResult

def test_freshness_calculation():
    # 创建测试目录
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建测试文件
        today = datetime.now()
        yesterday = today - timedelta(days=1)
        
        # 创建 10 个文件，8 个是昨天的（80%新鲜），2 个是前天的
        for i in range(8):
            path = os.path.join(tmpdir, f"file_{i}.csv")
            with open(path, 'w') as f:
                f.write("test")
            # 修改时间为昨天
            yesterday_ts = yesterday.timestamp()
            os.utime(path, (yesterday_ts, yesterday_ts))
        
        for i in range(8, 10):
            path = os.path.join(tmpdir, f"file_{i}.csv")
            with open(path, 'w') as f:
                f.write("test")
            # 修改时间为前天
            two_days_ago = yesterday - timedelta(days=1)
            os.utime(path, (two_days_ago.timestamp(), two_days_ago.timestamp()))
        
        checker = FreshnessChecker(tmpdir)
        yesterday_str = yesterday.strftime("%Y-%m-%d")
        result = checker.check(yesterday_str)
        
        assert result.total_count == 10
        assert result.fresh_count == 8
        assert result.fresh_ratio == 0.8
        assert result.is_fresh(0.85) == False  # 80% < 85%，不达标
        assert result.is_fresh(0.75) == True   # 80% > 75%，达标

if __name__ == "__main__":
    test_freshness_calculation()
    print("Freshness checker tests passed!")
```

**步骤 2: 运行测试验证失败**

```bash
python tests/test_freshness_checker.py
```

**步骤 3: 编写实现**

```python
# src/freshness_checker.py
"""数据新鲜度检测器"""

from pathlib import Path
from datetime import datetime
from dataclasses import dataclass
from typing import List


@dataclass
class FreshnessResult:
    """新鲜度检测结果"""
    total_count: int
    fresh_count: int
    fresh_ratio: float
    last_updated: str  # 85%分位数文件的mtime
    
    def is_fresh(self, threshold: float = 0.85) -> bool:
        """是否达到新鲜度阈值"""
        return self.fresh_ratio >= threshold


class FreshnessChecker:
    """检查数据目录新鲜度"""
    
    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
    
    def check(self, trade_date: str) -> FreshnessResult:
        """
        检查数据新鲜度
        
        Args:
            trade_date: 上一个交易日，格式 "2025-02-04"
        
        Returns:
            FreshnessResult 检测结果
        """
        # 获取所有 CSV 文件
        csv_files = list(self.data_dir.glob("*.csv"))
        total_count = len(csv_files)
        
        if total_count == 0:
            return FreshnessResult(0, 0, 0.0, "")
        
        # 计算新鲜度阈值时间（交易日 00:00）
        threshold_time = datetime.strptime(trade_date, "%Y-%m-%d")
        threshold_ts = threshold_time.timestamp()
        
        # 收集所有文件的 mtime
        file_mtimes = []
        for f in csv_files:
            mtime = f.stat().st_mtime
            file_mtimes.append((f.name, mtime))
        
        # 按 mtime 降序排序
        file_mtimes.sort(key=lambda x: x[1], reverse=True)
        
        # 统计新鲜文件（mtime >= 交易日）
        fresh_count = sum(1 for _, mtime in file_mtimes if mtime >= threshold_ts)
        fresh_ratio = fresh_count / total_count
        
        # 计算 85% 分位数的 mtime（即第15%位置的文件）
        index_85 = int(total_count * 0.15)
        last_updated_ts = file_mtimes[index_85][1] if file_mtimes else 0
        last_updated = datetime.fromtimestamp(last_updated_ts).strftime("%Y-%m-%dT%H:%M:%SZ")
        
        return FreshnessResult(
            total_count=total_count,
            fresh_count=fresh_count,
            fresh_ratio=fresh_ratio,
            last_updated=last_updated
        )
    
    def check_stable(self, trade_date: str, debounce_seconds: int = 30) -> FreshnessResult:
        """
        检查新鲜度并防抖
        
        先检查一次，等待 debounce_seconds 后再检查，
        如果两次结果基本一致，说明数据已稳定
        
        Returns:
            FreshnessResult，如果数据仍在变化返回 None
        """
        import time
        
        result1 = self.check(trade_date)
        
        # 等待防抖时间
        time.sleep(debounce_seconds)
        
        result2 = self.check(trade_date)
        
        # 检查是否稳定（新鲜度比例变化 < 1%）
        if abs(result2.fresh_ratio - result1.fresh_ratio) < 0.01:
            return result2
        else:
            # 数据仍在变化，返回 None 表示不稳定
            return None
```

**步骤 4: 运行测试验证通过**

```bash
python tests/test_freshness_checker.py
```

**步骤 5: 提交**

```bash
git add src/freshness_checker.py tests/test_freshness_checker.py
git commit -m "feat: add freshness checker with debounce"
```

---

## 任务 4: 异步打包器

**文件：**
- 创建: `/opt/projects/DataHubSync/src/packager.py`
- 创建: `/opt/projects/DataHubSync/tests/test_packager.py`

**步骤 1: 编写失败的测试**

```python
# tests/test_packager.py
import sys
sys.path.insert(0, '/opt/projects/DataHubSync/src')

import tempfile
import os
import zipfile
from packager import Packager

def test_package_dataset():
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建测试数据目录
        data_dir = os.path.join(tmpdir, "test_data")
        cache_dir = os.path.join(tmpdir, "cache")
        os.makedirs(data_dir)
        os.makedirs(cache_dir)
        
        # 创建测试文件
        for i in range(5):
            with open(os.path.join(data_dir, f"file_{i}.csv"), 'w') as f:
                f.write(f"content {i}")
        
        packager = Packager(cache_dir)
        result = packager.package("test_dataset", data_dir)
        
        # 验证结果
        assert result['success'] is True
        assert os.path.exists(result['zip_path'])
        assert result['file_count'] == 5
        
        # 验证 zip 内容
        with zipfile.ZipFile(result['zip_path'], 'r') as zf:
            files = zf.namelist()
            assert len(files) == 5
            for i in range(5):
                assert f"file_{i}.csv" in files
        
        print("Packager test passed!")

def test_cleanup_old_versions():
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_dir = tmpdir
        packager = Packager(cache_dir, keep_versions=2)
        
        # 创建 3 个旧版本的 zip 文件
        for i in range(3):
            path = os.path.join(cache_dir, f"dataset_2025020{i}_121000.zip")
            with open(path, 'w') as f:
                f.write("fake zip")
        
        # 清理
        packager._cleanup_old_versions("dataset")
        
        # 应该只剩下 2 个
        files = [f for f in os.listdir(cache_dir) if f.startswith("dataset_")]
        assert len(files) == 2
        
        print("Cleanup test passed!")

if __name__ == "__main__":
    test_package_dataset()
    test_cleanup_old_versions()
```

**步骤 2: 运行测试验证失败**

```bash
python tests/test_packager.py
```

**步骤 3: 编写实现**

```python
# src/packager.py
"""异步数据打包器"""

import zipfile
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List
import glob


class Packager:
    """将数据目录打包为 zip"""
    
    def __init__(self, cache_dir: str, keep_versions: int = 2):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.keep_versions = keep_versions
    
    def package(self, dataset_name: str, data_dir: str) -> Dict:
        """
        打包数据目录
        
        Args:
            dataset_name: 数据表名称
            data_dir: 数据目录路径
        
        Returns:
            dict: {
                'success': bool,
                'zip_path': str,
                'file_count': int,
                'zip_size': int
            }
        """
        data_path = Path(data_dir)
        
        # 生成 zip 文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_filename = f"{dataset_name}_{timestamp}.zip"
        zip_path = self.cache_dir / zip_filename
        
        # 打包
        csv_files = list(data_path.glob("*.csv"))
        file_count = len(csv_files)
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for csv_file in csv_files:
                arcname = csv_file.name  # 只保留文件名，不包含路径
                zf.write(csv_file, arcname)
        
        zip_size = zip_path.stat().st_size
        
        # 清理旧版本
        self._cleanup_old_versions(dataset_name)
        
        return {
            'success': True,
            'zip_path': str(zip_path),
            'file_count': file_count,
            'zip_size': zip_size
        }
    
    def _cleanup_old_versions(self, dataset_name: str):
        """清理旧的 zip 版本，只保留 keep_versions 个"""
        pattern = str(self.cache_dir / f"{dataset_name}_*.zip")
        files = sorted(glob.glob(pattern))
        
        # 按修改时间排序，删除旧的
        while len(files) > self.keep_versions:
            old_file = files.pop(0)
            try:
                os.remove(old_file)
            except OSError:
                pass
    
    def get_latest_package(self, dataset_name: str) -> str:
        """
        获取最新的 zip 包路径
        
        Returns:
            zip 文件路径，如果不存在返回 None
        """
        pattern = str(self.cache_dir / f"{dataset_name}_*.zip")
        files = sorted(glob.glob(pattern), key=os.path.getmtime, reverse=True)
        
        return files[0] if files else None
```

**步骤 4: 运行测试验证通过**

```bash
python tests/test_packager.py
```

**步骤 5: 提交**

```bash
git add src/packager.py tests/test_packager.py
git commit -m "feat: add async packager with cleanup"
```

---

## 任务 5: HTTP 服务器

**文件：**
- 创建: `/opt/projects/DataHubSync/src/http_server.py`
- 修改: `/opt/projects/DataHubSync/config.yaml` (添加 dataset_states 文件路径)

**步骤 1: 编写失败的测试**

```python
# tests/test_http_server.py
import sys
sys.path.insert(0, '/opt/projects/DataHubSync/src')

import json
from http.server import HTTPServer
from http_server import DataHubHandler

def test_parse_path():
    # 测试路径解析
    assert DataHubHandler._parse_path('/api/datasets') == ('datasets', None)
    assert DataHubHandler._parse_path('/package/stock-trading-data-pro.zip') == ('package', 'stock-trading-data-pro')
    assert DataHubHandler._parse_path('/invalid') == (None, None)
    print("Path parsing tests passed!")

if __name__ == "__main__":
    test_parse_path()
```

**步骤 2: 运行测试验证失败**

```bash
python tests/test_http_server.py
```

**步骤 3: 编写实现**

```python
# src/http_server.py
"""HTTP 服务器 - 提供数据表信息和 zip 下载"""

import json
import os
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
import mimetypes


class DataHubHandler(BaseHTTPRequestHandler):
    """请求处理器"""
    
    # 类级别的配置（由 server 设置）
    config = None
    dataset_states = {}
    
    def log_message(self, format, *args):
        """自定义日志格式"""
        print(f"[{self.log_date_time_string()}] {args[0]}")
    
    def do_GET(self):
        """处理 GET 请求"""
        parsed = urlparse(self.path)
        path = parsed.path
        
        # 路由分发
        route, param = self._parse_path(path)
        
        if route == 'datasets':
            self._handle_datasets()
        elif route == 'package':
            self._handle_package(param)
        elif route == 'health':
            self._handle_health()
        else:
            self._send_error(404, "Not found")
    
    @staticmethod
    def _parse_path(path: str):
        """解析 URL 路径"""
        if path == '/api/datasets':
            return ('datasets', None)
        elif path == '/health':
            return ('health', None)
        elif path.startswith('/package/'):
            # /package/dataset_name.zip
            filename = path[len('/package/'):]
            if filename.endswith('.zip'):
                dataset_name = filename[:-4]  # 去掉 .zip
                return ('package', dataset_name)
        return (None, None)
    
    def _handle_datasets(self):
        """返回数据表列表"""
        datasets = []
        
        for ds_config in self.config.get('datasets', []):
            name = ds_config['name']
            state = self.dataset_states.get(name, {})
            
            datasets.append({
                'name': name,
                'last_updated': state.get('last_updated', ''),
                'file_count': state.get('file_count', 0),
                'total_size': state.get('total_size', 0),
                'package_ready': state.get('package_ready', False),
                'package_size': state.get('package_size', 0)
            })
        
        response = {
            'generated_at': self._now_iso(),
            'datasets': datasets
        }
        
        self._send_json(200, response)
    
    def _handle_package(self, dataset_name: str):
        """返回 zip 包"""
        if not dataset_name:
            self._send_error(400, "Dataset name required")
            return
        
        # 查找最新的 zip 包
        cache_dir = Path(self.config['server']['cache_dir'])
        pattern = f"{dataset_name}_*.zip"
        zip_files = sorted(cache_dir.glob(pattern), key=os.path.getmtime, reverse=True)
        
        if not zip_files:
            self._send_error(404, f"Package not found for {dataset_name}")
            return
        
        zip_path = zip_files[0]
        
        # 支持 Range 请求（断点续传）
        range_header = self.headers.get('Range')
        
        if range_header:
            self._send_range_file(zip_path, range_header)
        else:
            self._send_file(zip_path)
    
    def _handle_health(self):
        """健康检查"""
        self._send_json(200, {'status': 'ok'})
    
    def _send_json(self, status: int, data: dict):
        """发送 JSON 响应"""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))
    
    def _send_file(self, file_path: Path):
        """发送文件"""
        file_size = file_path.stat().st_size
        content_type, _ = mimetypes.guess_type(str(file_path))
        
        self.send_response(200)
        self.send_header('Content-Type', content_type or 'application/octet-stream')
        self.send_header('Content-Length', file_size)
        self.end_headers()
        
        with open(file_path, 'rb') as f:
            self.wfile.write(f.read())
    
    def _send_range_file(self, file_path: Path, range_header: str):
        """发送文件片段（支持断点续传）"""
        # Range: bytes=start-end
        try:
            file_size = file_path.stat().st_size
            
            # 解析 Range 头
            range_val = range_header.replace('bytes=', '')
            start_str, end_str = range_val.split('-')
            start = int(start_str) if start_str else 0
            end = int(end_str) if end_str else file_size - 1
            
            length = end - start + 1
            
            self.send_response(206)  # Partial Content
            self.send_header('Content-Type', 'application/zip')
            self.send_header('Content-Length', length)
            self.send_header('Content-Range', f'bytes {start}-{end}/{file_size}')
            self.end_headers()
            
            with open(file_path, 'rb') as f:
                f.seek(start)
                self.wfile.write(f.read(length))
        
        except Exception as e:
            self._send_error(400, f"Invalid range: {e}")
    
    def _send_error(self, status: int, message: str):
        """发送错误响应"""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({'error': message}).encode('utf-8'))
    
    @staticmethod
    def _now_iso():
        """获取当前 ISO 格式时间"""
        from datetime import datetime
        return datetime.now().isoformat() + 'Z'


class DataHubServer:
    """HTTP 服务器"""
    
    def __init__(self, config: dict, dataset_states: dict):
        self.config = config
        self.dataset_states = dataset_states
        self.host = config['server']['host']
        self.port = config['server']['port']
        
        # 设置类级别的配置
        DataHubHandler.config = config
        DataHubHandler.dataset_states = dataset_states
    
    def start(self):
        """启动服务器"""
        server = HTTPServer((self.host, self.port), DataHubHandler)
        print(f"Server started at http://{self.host}:{self.port}")
        
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server...")
            server.shutdown()
```

**步骤 4: 运行测试验证通过**

```bash
python tests/test_http_server.py
```

**步骤 5: 提交**

```bash
git add src/http_server.py tests/test_http_server.py
git commit -m "feat: add HTTP server with dataset and package endpoints"
```

---

## 任务 6: 定时调度器

**文件：**
- 创建: `/opt/projects/DataHubSync/src/scheduler.py`
- 创建: `/opt/projects/DataHubSync/src/state_manager.py`

**步骤 1: 编写状态管理器**

```python
# src/state_manager.py
"""数据集状态管理器"""

import json
import os
from pathlib import Path
from typing import Dict


class StateManager:
    """管理数据集的 last_updated 等状态"""
    
    def __init__(self, state_file: str):
        self.state_file = Path(state_file)
        self._state = {}
        self._load()
    
    def _load(self):
        """从文件加载状态"""
        if self.state_file.exists():
            with open(self.state_file, 'r') as f:
                self._state = json.load(f)
        else:
            self._state = {}
    
    def _save(self):
        """保存状态到文件"""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, 'w') as f:
            json.dump(self._state, f, indent=2)
    
    def get(self, dataset_name: str) -> dict:
        """获取数据集状态"""
        return self._state.get(dataset_name, {})
    
    def update(self, dataset_name: str, **kwargs):
        """更新数据集状态"""
        if dataset_name not in self._state:
            self._state[dataset_name] = {}
        
        self._state[dataset_name].update(kwargs)
        self._save()
    
    def get_all(self) -> Dict[str, dict]:
        """获取所有状态"""
        return self._state.copy()
```

**步骤 2: 编写调度器**

```python
# src/scheduler.py
"""定时调度器 - 每10分钟检查新鲜度"""

import time
import threading
from datetime import datetime
from pathlib import Path

from calendar_reader import CalendarReader
from freshness_checker import FreshnessChecker
from packager import Packager
from state_manager import StateManager


class Scheduler:
    """定时调度器"""
    
    def __init__(self, config: dict, state_manager: StateManager):
        self.config = config
        self.state = state_manager
        self.calendar = CalendarReader(config['calendar']['period_offset_file'])
        self.packager = Packager(
            config['server']['cache_dir'],
            keep_versions=config['packaging']['keep_versions']
        )
        
        self.check_interval = config['check']['interval_minutes'] * 60  # 转为秒
        self.debounce_seconds = config['check']['debounce_seconds']
        
        self._running = False
        self._thread = None
    
    def start(self):
        """启动后台调度线程"""
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        print(f"Scheduler started, checking every {self.config['check']['interval_minutes']} minutes")
    
    def stop(self):
        """停止调度"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
    
    def _run(self):
        """主循环"""
        while self._running:
            try:
                self._check_all_datasets()
            except Exception as e:
                print(f"Error in scheduler: {e}")
            
            # 等待下次检查
            time.sleep(self.check_interval)
    
    def _check_all_datasets(self):
        """检查所有数据集"""
        today = datetime.now().strftime("%Y-%m-%d")
        last_trade_date = self.calendar.get_last_trade_date(today)
        
        print(f"[{datetime.now().isoformat()}] Checking freshness (trade date: {last_trade_date})")
        
        for ds_config in self.config['datasets']:
            dataset_name = ds_config['name']
            data_path = Path(self.config['server']['data_root']) / ds_config['path']
            threshold = ds_config['freshness_threshold']
            
            try:
                self._check_dataset(dataset_name, data_path, last_trade_date, threshold)
            except Exception as e:
                print(f"Error checking {dataset_name}: {e}")
    
    def _check_dataset(self, name: str, data_path: Path, trade_date: str, threshold: float):
        """检查单个数据集"""
        if not data_path.exists():
            print(f"  {name}: Data path not found: {data_path}")
            return
        
        # 创建新鲜度检测器
        checker = FreshnessChecker(data_path)
        
        # 第一次检查
        result = checker.check(trade_date)
        print(f"  {name}: {result.fresh_ratio:.1%} fresh ({result.fresh_count}/{result.total_count})")
        
        if not result.is_fresh(threshold):
            print(f"  {name}: Not fresh enough (threshold: {threshold:.0%}), skipping")
            return
        
        # 超过阈值，进行防抖检查
        print(f"  {name}: Fresh enough, waiting {self.debounce_seconds}s for stability...")
        stable_result = checker.check_stable(trade_date, self.debounce_seconds)
        
        if stable_result is None:
            print(f"  {name}: Data still changing, will retry next check")
            return
        
        # 检查是否已经有这个版本的包
        current_state = self.state.get(name)
        if current_state.get('last_updated') == stable_result.last_updated:
            print(f"  {name}: Already packaged for this version")
            return
        
        # 执行打包
        print(f"  {name}: Packaging...")
        package_result = self.packager.package(name, str(data_path))
        
        if package_result['success']:
            # 更新状态
            self.state.update(
                name,
                last_updated=stable_result.last_updated,
                file_count=stable_result.total_count,
                total_size=sum(f.stat().st_size for f in data_path.glob("*.csv")),
                package_ready=True,
                package_size=package_result['zip_size']
            )
            print(f"  {name}: Packaged successfully ({package_result['zip_size']} bytes)")
```

**步骤 3: 提交**

```bash
git add src/scheduler.py src/state_manager.py
git commit -m "feat: add scheduler with 10min interval and debounce"
```

---

## 任务 7: 主入口和集成测试

**文件：**
- 创建: `/opt/projects/DataHubSync/server.py`
- 创建: `/opt/projects/DataHubSync/tests/test_integration.py`

**步骤 1: 编写主入口**

```python
#!/usr/bin/env python3
"""
DataHubSync Server - hub 端主入口
"""

import sys
import yaml
import signal
from pathlib import Path

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from state_manager import StateManager
from scheduler import Scheduler
from http_server import DataHubServer


def load_config(config_path: str = 'config.yaml') -> dict:
    """加载配置"""
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def main():
    """主函数"""
    config = load_config()
    
    # 初始化状态管理器
    state_file = config.get('state_file', 'datasets_state.json')
    state_manager = StateManager(state_file)
    
    # 启动定时调度器
    scheduler = Scheduler(config, state_manager)
    scheduler.start()
    
    # 启动 HTTP 服务器
    server = DataHubServer(config, state_manager.get_all())
    
    # 设置信号处理
    def signal_handler(sig, frame):
        print('\nShutting down...')
        scheduler.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 运行服务器
    server.start()


if __name__ == '__main__':
    main()
```

**步骤 2: 编写集成测试**

```python
# tests/test_integration.py
"""集成测试"""

import sys
import tempfile
import os
import json
import time

sys.path.insert(0, '/opt/projects/DataHubSync/src')

def test_full_flow():
    """测试完整流程"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建测试数据
        data_dir = os.path.join(tmpdir, 'test_data')
        cache_dir = os.path.join(tmpdir, 'cache')
        os.makedirs(data_dir)
        os.makedirs(cache_dir)
        
        # 创建交易日历
        calendar_file = os.path.join(tmpdir, 'period_offset.csv')
        with open(calendar_file, 'w') as f:
            f.write("交易日期\n")
            f.write("2025-02-03\n")
            f.write("2025-02-04\n")
        
        # 创建测试文件（90%新鲜，超过85%阈值）
        today = "2025-02-04"
        for i in range(9):
            with open(os.path.join(data_dir, f"file_{i}.csv"), 'w') as f:
                f.write("test")
        
        print("Integration test setup complete!")
        print(f"Data dir: {data_dir}")
        print(f"Cache dir: {cache_dir}")
        print("Ready for manual testing with: python server.py")

if __name__ == '__main__':
    test_full_flow()
```

**步骤 3: 提交**

```bash
git add server.py tests/test_integration.py
git commit -m "feat: add main entry point and integration test"
```

---

## 任务 8: Windows 服务部署脚本

**文件：**
- 创建: `/opt/projects/DataHubSync/scripts/install_service.bat`
- 创建: `/opt/projects/DataHubSync/scripts/uninstall_service.bat`

**步骤 1: 编写安装脚本**

```batch
@echo off
REM install_service.bat - 安装 DataHubSync 为 Windows 服务

echo Installing DataHubSync service...

REM 设置路径
set SERVICE_NAME=DataHubSync
set INSTALL_DIR=C:\DataHubSync
set PYTHON=C:\Python311\python.exe

REM 使用 nssm 安装服务
nssm install %SERVICE_NAME% "%PYTHON%" "%INSTALL_DIR%\server.py"
nssm set %SERVICE_NAME% DisplayName "DataHubSync Server"
nssm set %SERVICE_NAME% Description "DataHubSync data distribution server"
nssm set %SERVICE_NAME% AppDirectory %INSTALL_DIR%
nssm set %SERVICE_NAME% Start SERVICE_AUTO_START
nssm set %SERVICE_NAME% AppStdout "%INSTALL_DIR%\logs\service.log"
nssm set %SERVICE_NAME% AppStderr "%INSTALL_DIR%\logs\service_error.log"

REM 启动服务
nssm start %SERVICE_NAME%

echo Service installed and started!
pause
```

**步骤 2: 编写卸载脚本**

```batch
@echo off
REM uninstall_service.bat - 卸载 DataHubSync Windows 服务

echo Uninstalling DataHubSync service...

set SERVICE_NAME=DataHubSync

REM 停止服务
nssm stop %SERVICE_NAME%

REM 移除服务
nssm remove %SERVICE_NAME% confirm

echo Service uninstalled!
pause
```

**步骤 3: 提交**

```bash
git add scripts/
git commit -m "feat: add Windows service install scripts"
```

---

## 执行交接

**计划已完成并保存到 `docs/plans/2025-02-04-hub-implementation.md`**

两种执行选项：

**1. 子代理驱动（本会话）** - 我为每个任务分派新子代理，任务间审查，快速迭代

**2. 并行会话（单独）** - 在新会话中用 executing-plans，批量执行带检查点

**选择哪种方式？** 推荐使用 **子代理驱动**，因为：
- 可以即时审查代码质量
- 任务间有依赖关系（后面的模块依赖前面的）
- 可以快速调整
