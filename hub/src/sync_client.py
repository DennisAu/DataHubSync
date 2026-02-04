"""
数据同步客户端
用于从 DataHub 服务器同步数据到本地
"""

import os
import json
import time
import shutil
import zipfile
import logging
import http.client
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from urllib.parse import urlparse


class SyncResult:
    """同步结果"""
    
    def __init__(self, dataset_name: str, success: bool, status: str, error: Optional[str] = None):
        self.dataset_name = dataset_name
        self.success = success
        self.status = status  # 'success', 'up_to_date', 'download_failed', 'extract_failed', 'package_not_ready'
        self.error = error
        self.timestamp = datetime.now(timezone.utc).isoformat()
    
    def __str__(self):
        if self.success:
            return f"SyncResult({self.dataset_name}: {self.status})"
        else:
            return f"SyncResult({self.dataset_name}: {self.status} - {self.error})"


class DataSyncClient:
    """数据同步客户端"""
    
    def __init__(self, config: Dict[str, Any], sync_state_file: str):
        """
        初始化同步客户端
        
        Args:
            config: 配置字典
            sync_state_file: 同步状态文件路径
        """
        self.hub_url = config['hub']['url']
        self.timeout = config['hub'].get('timeout', 300)
        self.datasets = config.get('datasets', [])
        self.sync_state_file = Path(sync_state_file)
        
        # 解析hub URL
        parsed_url = urlparse(self.hub_url)
        self.hub_host = parsed_url.hostname
        self.hub_scheme = parsed_url.scheme
        self.hub_port = parsed_url.port or (443 if self.hub_scheme == 'https' else 80)
        
        # 确保状态文件目录存在
        self.sync_state_file.parent.mkdir(parents=True, exist_ok=True)
        
        # 设置日志
        self._setup_logging(config.get('logging', {}))
        
        # 加载同步状态
        self.sync_state = self._load_sync_state()
    
    def _setup_logging(self, logging_config: Dict[str, Any]):
        """设置日志"""
        log_level = logging_config.get('level', 'INFO')
        log_file = logging_config.get('file')
        
        # 创建logger
        self.logger = logging.getLogger('sync_client')
        self.logger.setLevel(getattr(logging, log_level.upper()))
        
        # 避免重复添加handler
        if not self.logger.handlers:
            # 控制台handler
            console_handler = logging.StreamHandler()
            console_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            console_handler.setFormatter(console_formatter)
            self.logger.addHandler(console_handler)
            
            # 文件handler（如果配置了）
            if log_file:
                log_path = Path(log_file)
                log_path.parent.mkdir(parents=True, exist_ok=True)
                
                file_handler = logging.FileHandler(log_path)
                file_formatter = logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                )
                file_handler.setFormatter(file_formatter)
                self.logger.addHandler(file_handler)
    
    def _load_sync_state(self) -> Dict[str, str]:
        """加载同步状态"""
        if not self.sync_state_file.exists():
            return {}
        
        try:
            with open(self.sync_state_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            self.logger.warning(f"Failed to load sync state: {e}")
            return {}
    
    def _save_sync_state(self, state: Dict[str, str]):
        """保存同步状态"""
        try:
            with open(self.sync_state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
        except IOError as e:
            self.logger.error(f"Failed to save sync state: {e}")
            raise
    
    def _fetch_datasets(self) -> List[Dict[str, Any]]:
        """获取远程数据集列表"""
        try:
            if self.hub_scheme == 'https':
                conn = http.client.HTTPSConnection(self.hub_host, self.hub_port, timeout=self.timeout)
            else:
                conn = http.client.HTTPConnection(self.hub_host, self.hub_port, timeout=self.timeout)
            
            try:
                conn.request('GET', '/api/datasets')
                response = conn.getresponse()
                
                if response.status != 200:
                    raise Exception(f"HTTP {response.status}: {response.reason}")
                
                data = response.read().decode('utf-8')
                return json.loads(data)['datasets']
            
            finally:
                conn.close()
        
        except Exception as e:
            self.logger.error(f"Failed to fetch datasets: {e}")
            raise
    
    def _need_sync(self, remote_info: Dict[str, Any], local_state: Dict[str, str]) -> bool:
        """判断是否需要同步"""
        dataset_name = remote_info['name']
        
        # 检查包是否准备好
        if not remote_info.get('package_ready', False):
            self.logger.info(f"Dataset {dataset_name} package not ready")
            return False
        
        # 检查本地是否有记录
        if dataset_name not in local_state:
            self.logger.info(f"Dataset {dataset_name} not found locally, need sync")
            return True
        
        # 比较时间戳
        local_updated = local_state[dataset_name]
        remote_updated = remote_info['last_updated']
        
        if remote_updated > local_updated:
            self.logger.info(f"Dataset {dataset_name} remote newer: local={local_updated}, remote={remote_updated}")
            return True
        else:
            self.logger.info(f"Dataset {dataset_name} up to date: {local_updated}")
            return False
    
    def _download_package(self, dataset_name: str, output_path: Path) -> bool:
        """下载数据包"""
        try:
            if self.hub_scheme == 'https':
                conn = http.client.HTTPSConnection(self.hub_host, self.hub_port, timeout=self.timeout)
            else:
                conn = http.client.HTTPConnection(self.hub_host, self.hub_port, timeout=self.timeout)
            
            try:
                package_url = f'/package/{dataset_name}.zip'
                self.logger.info(f"Downloading {package_url} to {output_path}")
                
                conn.request('GET', package_url)
                response = conn.getresponse()
                
                self.logger.debug(f"Response status: {response.status}, type: {type(response.status)}")
                if response.status != 200:
                    self.logger.error(f"Download failed: HTTP {response.status}")
                    return False
                
                # 写入文件
                with open(output_path, 'wb') as f:
                    while True:
                        chunk = response.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
                
                self.logger.info(f"Downloaded {output_path} ({output_path.stat().st_size} bytes)")
                return True
            
            finally:
                conn.close()
        
        except Exception as e:
            self.logger.error(f"Failed to download {dataset_name}: {e}")
            return False
    
    def _extract_package(self, package_path: Path, target_dir: Path) -> bool:
        """解压数据包"""
        try:
            self.logger.info(f"Extracting {package_path} to {target_dir}")
            
            # 确保目标目录存在
            target_dir.mkdir(parents=True, exist_ok=True)
            
            # 解压zip文件
            with zipfile.ZipFile(package_path, 'r') as zf:
                zf.extractall(target_dir)
            
            # 验证解压结果
            extracted_files = list(target_dir.rglob('*'))
            self.logger.info(f"Extracted {len(extracted_files)} files to {target_dir}")
            
            return True
        
        except Exception as e:
            self.logger.error(f"Failed to extract {package_path}: {e}")
            return False
    
    def sync_dataset(self, dataset_name: str) -> SyncResult:
        """同步单个数据集"""
        try:
            self.logger.info(f"Starting sync for dataset: {dataset_name}")
            
            # 1. 获取远程状态
            datasets = self._fetch_datasets()
            remote_info = None
            for ds in datasets:
                if ds['name'] == dataset_name:
                    remote_info = ds
                    break
            
            if not remote_info:
                return SyncResult(dataset_name, False, 'not_found', f"Dataset {dataset_name} not found on server")
            
            # 2. 判断是否需要同步
            if not self._need_sync(remote_info, self.sync_state):
                # 更新本地状态（如果时间戳相同）
                if dataset_name in self.sync_state:
                    self.sync_state[dataset_name] = remote_info['last_updated']
                    self._save_sync_state(self.sync_state)
                return SyncResult(dataset_name, True, 'up_to_date')
            
            # 3. 获取数据集本地目录
            dataset_config = None
            for ds in self.datasets:
                if ds['name'] == dataset_name:
                    dataset_config = ds
                    break
            
            if not dataset_config:
                return SyncResult(dataset_name, False, 'config_error', f"Dataset {dataset_name} not found in config")
            
            local_dir = Path(dataset_config['local_dir'])
            
            # 4. 下载包
            temp_dir = Path.home() / '.datahub_sync' / 'temp'
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            package_path = temp_dir / f"{dataset_name}_{int(time.time())}.zip"
            
            if not self._download_package(dataset_name, package_path):
                return SyncResult(dataset_name, False, 'download_failed', "Failed to download package")
            
            # 5. 解压包
            if not self._extract_package(package_path, local_dir):
                return SyncResult(dataset_name, False, 'extract_failed', "Failed to extract package")
            
            # 6. 更新本地状态
            self.sync_state[dataset_name] = remote_info['last_updated']
            self._save_sync_state(self.sync_state)
            
            # 7. 清理临时文件
            try:
                package_path.unlink()
            except:
                pass
            
            self.logger.info(f"Successfully synced dataset: {dataset_name}")
            return SyncResult(dataset_name, True, 'success')
            
        except Exception as e:
            self.logger.error(f"Failed to sync {dataset_name}: {e}")
            return SyncResult(dataset_name, False, 'error', str(e))
    
    def sync_all(self) -> List[SyncResult]:
        """同步所有配置的数据集"""
        results = []
        
        for dataset_config in self.datasets:
            dataset_name = dataset_config['name']
            result = self.sync_dataset(dataset_name)
            results.append(result)
        
        return results


def main():
    """主函数 - 用于命令行调用"""
    import sys
    import yaml
    
    if len(sys.argv) < 2:
        print("Usage: python sync_client.py <config_file>")
        sys.exit(1)
    
    config_file = sys.argv[1]
    
    try:
        # 加载配置
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # 创建客户端
        client_dir = Path(config_file).parent
        sync_state_file = client_dir / '.last_sync.json'
        client = DataSyncClient(config, str(sync_state_file))
        
        # 同步所有数据集
        results = client.sync_all()
        
        # 输出结果
        success_count = sum(1 for r in results if r.success)
        total_count = len(results)
        
        print(f"\nSync completed: {success_count}/{total_count} successful")
        
        for result in results:
            print(f"  {result}")
        
        # 返回适当的退出码
        sys.exit(0 if success_count == total_count else 1)
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()