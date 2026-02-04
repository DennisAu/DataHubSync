"""
HTTP Server - DataHub HTTP 服务器
提供 REST API 端点用于查询数据集状态和下载数据包
"""

import os
import re
import json
import logging
import mimetypes
from pathlib import Path
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional, Dict, List, Any

logger = logging.getLogger(__name__)


class DataHubHandler(BaseHTTPRequestHandler):
    """
    HTTP 请求处理器
    
    端点:
    - GET /api/datasets - 返回所有数据集列表
    - GET /package/{dataset}.zip - 下载数据包（支持 Range 断点续传）
    - GET /health - 健康检查
    """
    
    # 类级别配置和状态
    config = None
    dataset_states = {}
    
    def log_message(self, format: str, *args) -> None:
        """使用 logging 模块记录请求日志"""
        logger.info(f"{self.address_string()} - {format % args}")
    
    def log_error(self, format: str, *args) -> None:
        """使用 logging 模块记录错误日志"""
        logger.error(f"{self.address_string()} - {format % args}")
    
    def do_GET(self) -> None:
        """处理 GET 请求"""
        try:
            path = self.path
            
            # 路由分发
            if path == '/health':
                self._handle_health()
            elif path == '/api/datasets':
                self._handle_datasets()
            elif path.startswith('/package/') and path.endswith('.zip'):
                # 提取数据集名称 /package/{dataset}.zip
                dataset_name = path[9:-4]  # 去掉 '/package/' 和 '.zip'
                self._handle_package(dataset_name)
            else:
                self._send_json(404, {'error': 'Not found', 'path': path})
                
        except Exception as e:
            logger.exception("处理请求时发生错误")
            self._send_json(500, {'error': 'Internal server error', 'message': str(e)})
    
    def _handle_health(self) -> None:
        """处理健康检查请求"""
        self._send_json(200, {'status': 'ok'})
    
    def _handle_datasets(self) -> None:
        """
        处理数据集列表请求
        
        返回所有数据集的元数据信息，包括:
        - name: 数据集名称
        - last_updated: 最后更新时间
        - file_count: 文件数量
        - total_size: 总大小
        - package_ready: 包是否就绪
        - package_size: 包大小
        """
        datasets_info = []
        
        # 从配置中获取数据集列表
        datasets_config = self.config.get('datasets', [])
        cache_dir = self.config.get('server', {}).get('cache_dir', '.cache')
        data_root = self.config.get('server', {}).get('data_root', '')
        
        for dataset_config in datasets_config:
            name = dataset_config.get('name', '')
            path = dataset_config.get('path', '')
            
            # 获取数据集状态
            state = self.dataset_states.get(name, {})
            
            # 计算数据集信息
            dataset_info = self._get_dataset_info(name, path, data_root, cache_dir, state)
            datasets_info.append(dataset_info)
        
        self._send_json(200, {'datasets': datasets_info})
    
    def _get_dataset_info(
        self, 
        name: str, 
        path: str, 
        data_root: str, 
        cache_dir: str,
        state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        获取单个数据集的信息
        
        Args:
            name: 数据集名称
            path: 数据集路径
            data_root: 数据根目录
            cache_dir: 缓存目录
            state: 数据集状态
            
        Returns:
            数据集信息字典
        """
        # 获取数据目录信息
        data_path = Path(data_root) / path if data_root else Path(path)
        file_count = 0
        total_size = 0
        last_updated = None
        
        if data_path.exists() and data_path.is_dir():
            for file_path in data_path.rglob('*'):
                if file_path.is_file():
                    file_count += 1
                    try:
                        stat = file_path.stat()
                        total_size += stat.st_size
                        mtime = datetime.fromtimestamp(stat.st_mtime)
                        if last_updated is None or mtime > last_updated:
                            last_updated = mtime
                    except (OSError, IOError):
                        pass
        
        # 获取包信息
        package_path = self._find_latest_package(name, cache_dir)
        package_ready = package_path is not None
        package_size = 0
        
        if package_path and Path(package_path).exists():
            try:
                package_size = Path(package_path).stat().st_size
            except (OSError, IOError):
                pass
        
        return {
            'name': name,
            'last_updated': last_updated.isoformat() if last_updated else None,
            'file_count': file_count,
            'total_size': total_size,
            'package_ready': package_ready,
            'package_size': package_size,
            'freshness': state.get('freshness', {}),
            'status': state.get('status', 'unknown')
        }
    
    def _find_latest_package(self, dataset_name: str, cache_dir: str) -> Optional[str]:
        """
        查找最新的数据包
        
        Args:
            dataset_name: 数据集名称
            cache_dir: 缓存目录
            
        Returns:
            最新包的路径，如果不存在返回 None
        """
        cache_path = Path(cache_dir)
        if not cache_path.exists():
            return None
        
        # 查找匹配的 zip 文件
        pattern = f"{dataset_name}_*.zip"
        zip_files = sorted(
            cache_path.glob(pattern),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        
        if zip_files:
            return str(zip_files[0])
        return None
    
    def _handle_package(self, dataset_name: str) -> None:
        """
        处理数据包下载请求
        
        支持 Range 请求实现断点续传
        """
        # 验证数据集名称
        if not dataset_name or '..' in dataset_name or '/' in dataset_name:
            self._send_json(400, {'error': 'Invalid dataset name'})
            return
        
        # 查找包文件
        cache_dir = self.config.get('server', {}).get('cache_dir', '.cache')
        package_path = self._find_latest_package(dataset_name, cache_dir)
        
        if not package_path or not Path(package_path).exists():
            self._send_json(404, {'error': f'Package not found for dataset: {dataset_name}'})
            return
        
        # 检查 Range 请求头
        range_header = self.headers.get('Range')
        if range_header:
            self._send_range_file(package_path, range_header)
        else:
            self._send_file(package_path)
    
    def _send_json(self, status: int, data: Dict[str, Any]) -> None:
        """
        发送 JSON 响应
        
        Args:
            status: HTTP 状态码
            data: 响应数据字典
        """
        response_body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', len(response_body))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(response_body)
    
    def _send_file(self, file_path: str) -> None:
        """
        发送完整文件
        
        Args:
            file_path: 文件路径
        """
        path = Path(file_path)
        
        # 获取文件类型
        content_type, _ = mimetypes.guess_type(file_path)
        if content_type is None:
            content_type = 'application/octet-stream'
        
        # 获取文件大小
        file_size = path.stat().st_size
        
        # 发送响应头
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', file_size)
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Content-Disposition', f'attachment; filename="{path.name}"')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        # 发送文件内容
        with open(path, 'rb') as f:
            while True:
                chunk = f.read(64 * 1024)  # 64KB 块
                if not chunk:
                    break
                self.wfile.write(chunk)
        
        logger.info(f"文件发送完成: {file_path}")
    
    def _send_range_file(self, file_path: str, range_header: str) -> None:
        """
        发送文件的部分内容（支持断点续传）
        
        Args:
            file_path: 文件路径
            range_header: Range 请求头值
        """
        path = Path(file_path)
        file_size = path.stat().st_size
        
        # 解析 Range 头
        # 格式: bytes=start-end
        range_match = re.match(r'bytes=(\d+)-(\d*)', range_header)
        if not range_match:
            self._send_json(400, {'error': 'Invalid Range header'})
            return
        
        start_str, end_str = range_match.groups()
        start = int(start_str)
        end = int(end_str) if end_str else file_size - 1
        
        # 验证范围
        if start >= file_size or start < 0 or end >= file_size or start > end:
            self.send_response(416)  # Range Not Satisfiable
            self.send_header('Content-Range', f'bytes */{file_size}')
            self.end_headers()
            return
        
        # 计算内容长度
        content_length = end - start + 1
        
        # 获取文件类型
        content_type, _ = mimetypes.guess_type(file_path)
        if content_type is None:
            content_type = 'application/octet-stream'
        
        # 发送 206 Partial Content 响应
        self.send_response(206)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', content_length)
        self.send_header('Content-Range', f'bytes {start}-{end}/{file_size}')
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Content-Disposition', f'attachment; filename="{path.name}"')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        # 发送文件内容
        with open(path, 'rb') as f:
            f.seek(start)
            remaining = content_length
            while remaining > 0:
                chunk_size = min(64 * 1024, remaining)
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)
        
        logger.info(f"Range 文件发送完成: {file_path}, bytes={start}-{end}")


class DataHubServer:
    """
    DataHub HTTP 服务器
    
    提供数据集查询和数据包下载服务
    """
    
    def __init__(self, config: Dict[str, Any], dataset_states: Dict[str, Any]):
        """
        初始化服务器
        
        Args:
            config: 配置字典
            dataset_states: 数据集状态字典（共享状态）
        """
        self.config = config
        self.dataset_states = dataset_states
        
        # 获取服务器配置
        server_config = config.get('server', {})
        self.host = server_config.get('host', '0.0.0.0')
        self.port = server_config.get('port', 8080)
        
        # 设置处理器类级别的配置和状态
        DataHubHandler.config = config
        DataHubHandler.dataset_states = dataset_states
        
        # 创建 HTTP 服务器
        self.server = HTTPServer((self.host, self.port), DataHubHandler)
        
        logger.info(f"DataHubServer initialized: {self.host}:{self.port}")
    
    def start(self) -> None:
        """启动服务器"""
        logger.info(f"Starting HTTP server on {self.host}:{self.port}")
        print(f"Server running at http://{self.host}:{self.port}/")
        print(f"API endpoints:")
        print(f"  - GET /health")
        print(f"  - GET /api/datasets")
        print(f"  - GET /package/{{dataset}}.zip")
        print("Press Ctrl+C to stop")
        
        try:
            self.server.serve_forever()
        except KeyboardInterrupt:
            logger.info("Server stopped by user")
            self.stop()
    
    def stop(self) -> None:
        """停止服务器"""
        logger.info("Stopping HTTP server")
        self.server.shutdown()
        self.server.server_close()
    
    def run_once(self) -> None:
        """处理单个请求（用于测试）"""
        self.server.handle_request()


# 用于直接运行的入口点
if __name__ == '__main__':
    import yaml
    
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )
    
    # 加载配置
    config_path = Path(__file__).parent.parent / 'config.yaml'
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # 创建服务器
    dataset_states = {}
    server = DataHubServer(config, dataset_states)
    
    # 启动服务器
    server.start()
