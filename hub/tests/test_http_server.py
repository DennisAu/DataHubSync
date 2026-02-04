"""
测试 HTTP 服务器
"""

import os
import json
import time
import shutil
import zipfile
import unittest
import threading
import http.client
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import HTTPError

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from http_server import DataHubServer, DataHubHandler


class TestDataHubServer(unittest.TestCase):
    """测试 DataHub HTTP 服务器"""
    
    @classmethod
    def setUpClass(cls):
        """设置测试环境"""
        cls.test_dir = Path(__file__).parent.parent / 'tests' / 'test_data' / 'http_server'
        cls.cache_dir = cls.test_dir / 'cache'
        cls.data_dir = cls.test_dir / 'data'
        
        # 创建测试目录
        cls.cache_dir.mkdir(parents=True, exist_ok=True)
        cls.data_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建测试配置
        cls.config = {
            'server': {
                'host': '127.0.0.1',
                'port': 18080,  # 使用非标准端口避免冲突
                'cache_dir': str(cls.cache_dir),
                'data_root': str(cls.data_dir)
            },
            'datasets': [
                {'name': 'test-dataset-1', 'path': 'test-dataset-1', 'freshness_threshold': 0.85},
                {'name': 'test-dataset-2', 'path': 'test-dataset-2', 'freshness_threshold': 0.85}
            ]
        }
        
        cls.dataset_states = {}
    
    @classmethod
    def tearDownClass(cls):
        """清理测试环境"""
        if cls.test_dir.exists():
            shutil.rmtree(cls.test_dir.parent)
    
    def setUp(self):
        """每个测试前的设置"""
        # 清理缓存目录
        if self.cache_dir.exists():
            shutil.rmtree(self.cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # 清理数据目录
        if self.data_dir.exists():
            shutil.rmtree(self.data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # 重置状态
        self.dataset_states.clear()
    
    def _create_test_data(self, dataset_name: str, file_count: int = 3) -> Path:
        """创建测试数据目录"""
        dataset_dir = self.data_dir / dataset_name
        dataset_dir.mkdir(parents=True, exist_ok=True)
        
        for i in range(file_count):
            (dataset_dir / f'file_{i}.txt').write_text(f'Content {i}')
        
        return dataset_dir
    
    def _create_test_package(self, dataset_name: str, content: bytes = None) -> Path:
        """创建测试 zip 包"""
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        zip_path = self.cache_dir / f"{dataset_name}_{timestamp}.zip"
        
        with zipfile.ZipFile(zip_path, 'w') as zf:
            if content:
                zf.writestr('test.txt', content)
            else:
                zf.writestr('test.txt', b'test content')
        
        return zip_path


class TestDataHubHandler(TestDataHubServer):
    """测试 HTTP 处理器"""
    
    def test_health_endpoint(self):
        """测试健康检查端点"""
        # 设置处理器配置
        DataHubHandler.config = self.config
        DataHubHandler.dataset_states = self.dataset_states
        
        # 创建服务器（但不启动）
        server = DataHubServer(self.config, self.dataset_states)
        
        try:
            # 启动服务器在线程中
            server_thread = threading.Thread(target=server.start)
            server_thread.daemon = True
            server_thread.start()
            time.sleep(0.5)  # 等待服务器启动
            
            # 测试健康检查
            conn = http.client.HTTPConnection('127.0.0.1', 18080)
            conn.request('GET', '/health')
            response = conn.getresponse()
            
            self.assertEqual(response.status, 200)
            data = json.loads(response.read().decode('utf-8'))
            self.assertEqual(data['status'], 'ok')
            
            conn.close()
        finally:
            server.stop()
    
    def test_datasets_endpoint_empty(self):
        """测试数据集列表端点（空数据集）"""
        DataHubHandler.config = self.config
        DataHubHandler.dataset_states = self.dataset_states
        
        server = DataHubServer(self.config, self.dataset_states)
        
        try:
            server_thread = threading.Thread(target=server.start)
            server_thread.daemon = True
            server_thread.start()
            time.sleep(0.5)
            
            conn = http.client.HTTPConnection('127.0.0.1', 18080)
            conn.request('GET', '/api/datasets')
            response = conn.getresponse()
            
            self.assertEqual(response.status, 200)
            data = json.loads(response.read().decode('utf-8'))
            self.assertIn('datasets', data)
            self.assertEqual(len(data['datasets']), 2)
            
            # 验证数据集结构
            for dataset in data['datasets']:
                self.assertIn('name', dataset)
                self.assertIn('last_updated', dataset)
                self.assertIn('file_count', dataset)
                self.assertIn('total_size', dataset)
                self.assertIn('package_ready', dataset)
                self.assertIn('package_size', dataset)
            
            conn.close()
        finally:
            server.stop()
    
    def test_datasets_endpoint_with_data(self):
        """测试数据集列表端点（有数据）"""
        # 创建测试数据
        self._create_test_data('test-dataset-1', file_count=5)
        
        DataHubHandler.config = self.config
        DataHubHandler.dataset_states = self.dataset_states
        
        server = DataHubServer(self.config, self.dataset_states)
        
        try:
            server_thread = threading.Thread(target=server.start)
            server_thread.daemon = True
            server_thread.start()
            time.sleep(0.5)
            
            conn = http.client.HTTPConnection('127.0.0.1', 18080)
            conn.request('GET', '/api/datasets')
            response = conn.getresponse()
            
            self.assertEqual(response.status, 200)
            data = json.loads(response.read().decode('utf-8'))
            
            # 找到 test-dataset-1
            dataset1 = next(d for d in data['datasets'] if d['name'] == 'test-dataset-1')
            self.assertEqual(dataset1['file_count'], 5)
            self.assertGreater(dataset1['total_size'], 0)
            
            conn.close()
        finally:
            server.stop()
    
    def test_package_endpoint_not_found(self):
        """测试包下载端点（包不存在）"""
        DataHubHandler.config = self.config
        DataHubHandler.dataset_states = self.dataset_states
        
        server = DataHubServer(self.config, self.dataset_states)
        
        try:
            server_thread = threading.Thread(target=server.start)
            server_thread.daemon = True
            server_thread.start()
            time.sleep(0.5)
            
            conn = http.client.HTTPConnection('127.0.0.1', 18080)
            conn.request('GET', '/package/nonexistent.zip')
            response = conn.getresponse()
            
            self.assertEqual(response.status, 404)
            data = json.loads(response.read().decode('utf-8'))
            self.assertIn('error', data)
            
            conn.close()
        finally:
            server.stop()
    
    def test_package_endpoint_download(self):
        """测试包下载端点（正常下载）"""
        # 创建测试包
        test_content = b'Hello, World! This is test content for the zip file.'
        zip_path = self._create_test_package('test-dataset-1', test_content)
        
        DataHubHandler.config = self.config
        DataHubHandler.dataset_states = self.dataset_states
        
        server = DataHubServer(self.config, self.dataset_states)
        
        try:
            server_thread = threading.Thread(target=server.start)
            server_thread.daemon = True
            server_thread.start()
            time.sleep(0.5)
            
            conn = http.client.HTTPConnection('127.0.0.1', 18080)
            conn.request('GET', '/package/test-dataset-1.zip')
            response = conn.getresponse()
            
            self.assertEqual(response.status, 200)
            self.assertEqual(response.getheader('Content-Type'), 'application/zip')
            self.assertEqual(response.getheader('Accept-Ranges'), 'bytes')
            
            # 读取并验证内容
            content = response.read()
            self.assertGreater(len(content), 0)
            
            # 验证是有效的 zip 文件
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            
            with zipfile.ZipFile(tmp_path, 'r') as zf:
                self.assertIn('test.txt', zf.namelist())
            
            os.unlink(tmp_path)
            conn.close()
        finally:
            server.stop()
    
    def test_package_endpoint_range_request(self):
        """测试包下载端点（Range 断点续传）"""
        # 创建测试包
        test_content = b'A' * 1000  # 1KB 内容
        zip_path = self._create_test_package('test-dataset-1', test_content)
        
        # 获取文件大小
        file_size = zip_path.stat().st_size
        
        DataHubHandler.config = self.config
        DataHubHandler.dataset_states = self.dataset_states
        
        server = DataHubServer(self.config, self.dataset_states)
        
        try:
            server_thread = threading.Thread(target=server.start)
            server_thread.daemon = True
            server_thread.start()
            time.sleep(0.5)
            
            # 测试 Range 请求
            conn = http.client.HTTPConnection('127.0.0.1', 18080)
            headers = {'Range': 'bytes=0-99'}
            conn.request('GET', '/package/test-dataset-1.zip', headers=headers)
            response = conn.getresponse()
            
            self.assertEqual(response.status, 206)  # Partial Content
            self.assertEqual(response.getheader('Content-Length'), '100')
            self.assertEqual(response.getheader('Accept-Ranges'), 'bytes')
            
            # 验证 Content-Range 头
            content_range = response.getheader('Content-Range')
            self.assertIn('bytes 0-99', content_range)
            
            # 读取内容
            content = response.read()
            self.assertEqual(len(content), 100)
            
            conn.close()
        finally:
            server.stop()
    
    def test_package_endpoint_invalid_range(self):
        """测试包下载端点（无效 Range）"""
        # 创建测试包
        zip_path = self._create_test_package('test-dataset-1')
        
        DataHubHandler.config = self.config
        DataHubHandler.dataset_states = self.dataset_states
        
        server = DataHubServer(self.config, self.dataset_states)
        
        try:
            server_thread = threading.Thread(target=server.start)
            server_thread.daemon = True
            server_thread.start()
            time.sleep(0.5)
            
            conn = http.client.HTTPConnection('127.0.0.1', 18080)
            headers = {'Range': 'bytes=invalid'}
            conn.request('GET', '/package/test-dataset-1.zip', headers=headers)
            response = conn.getresponse()
            
            self.assertEqual(response.status, 400)
            data = json.loads(response.read().decode('utf-8'))
            self.assertIn('error', data)
            
            conn.close()
        finally:
            server.stop()
    
    def test_package_endpoint_out_of_range(self):
        """测试包下载端点（Range 超出范围）"""
        # 创建测试包
        zip_path = self._create_test_package('test-dataset-1')
        file_size = zip_path.stat().st_size
        
        DataHubHandler.config = self.config
        DataHubHandler.dataset_states = self.dataset_states
        
        server = DataHubServer(self.config, self.dataset_states)
        
        try:
            server_thread = threading.Thread(target=server.start)
            server_thread.daemon = True
            server_thread.start()
            time.sleep(0.5)
            
            conn = http.client.HTTPConnection('127.0.0.1', 18080)
            # 请求超出文件大小的范围
            headers = {'Range': f'bytes={file_size + 1000}-{file_size + 2000}'}
            conn.request('GET', '/package/test-dataset-1.zip', headers=headers)
            response = conn.getresponse()
            
            self.assertEqual(response.status, 416)  # Range Not Satisfiable
            
            conn.close()
        finally:
            server.stop()
    
    def test_invalid_path(self):
        """测试无效路径"""
        DataHubHandler.config = self.config
        DataHubHandler.dataset_states = self.dataset_states
        
        server = DataHubServer(self.config, self.dataset_states)
        
        try:
            server_thread = threading.Thread(target=server.start)
            server_thread.daemon = True
            server_thread.start()
            time.sleep(0.5)
            
            conn = http.client.HTTPConnection('127.0.0.1', 18080)
            conn.request('GET', '/invalid/path')
            response = conn.getresponse()
            
            self.assertEqual(response.status, 404)
            
            conn.close()
        finally:
            server.stop()
    
    def test_invalid_dataset_name(self):
        """测试无效数据集名称"""
        DataHubHandler.config = self.config
        DataHubHandler.dataset_states = self.dataset_states
        
        server = DataHubServer(self.config, self.dataset_states)
        
        try:
            server_thread = threading.Thread(target=server.start)
            server_thread.daemon = True
            server_thread.start()
            time.sleep(0.5)
            
            # 测试包含 .. 的数据集名称
            conn = http.client.HTTPConnection('127.0.0.1', 18080)
            conn.request('GET', '/package/../../../etc/passwd.zip')
            response = conn.getresponse()
            
            self.assertEqual(response.status, 400)
            data = json.loads(response.read().decode('utf-8'))
            self.assertIn('error', data)
            
            conn.close()
        finally:
            server.stop()
    
    def test_datasets_with_states(self):
        """测试数据集端点（带状态信息）"""
        # 设置数据集状态
        self.dataset_states['test-dataset-1'] = {
            'status': 'packaged',
            'freshness': {
                'total_count': 10,
                'fresh_count': 9,
                'fresh_ratio': 0.9,
                'last_updated': '2024-01-15T10:30:00',
                'is_fresh': True
            }
        }
        
        DataHubHandler.config = self.config
        DataHubHandler.dataset_states = self.dataset_states
        
        server = DataHubServer(self.config, self.dataset_states)
        
        try:
            server_thread = threading.Thread(target=server.start)
            server_thread.daemon = True
            server_thread.start()
            time.sleep(0.5)
            
            conn = http.client.HTTPConnection('127.0.0.1', 18080)
            conn.request('GET', '/api/datasets')
            response = conn.getresponse()
            
            self.assertEqual(response.status, 200)
            data = json.loads(response.read().decode('utf-8'))
            
            # 找到 test-dataset-1
            dataset1 = next(d for d in data['datasets'] if d['name'] == 'test-dataset-1')
            self.assertEqual(dataset1['status'], 'packaged')
            self.assertIn('freshness', dataset1)
            self.assertEqual(dataset1['freshness']['fresh_ratio'], 0.9)
            
            conn.close()
        finally:
            server.stop()


class TestDataHubServerClass(unittest.TestCase):
    """测试 DataHubServer 类"""
    
    def test_server_initialization(self):
        """测试服务器初始化"""
        config = {
            'server': {
                'host': '127.0.0.1',
                'port': 18081,
                'cache_dir': '/tmp/cache',
                'data_root': '/tmp/data'
            },
            'datasets': []
        }
        dataset_states = {}
        
        server = DataHubServer(config, dataset_states)
        
        self.assertEqual(server.host, '127.0.0.1')
        self.assertEqual(server.port, 18081)
        self.assertEqual(server.config, config)
        self.assertEqual(server.dataset_states, dataset_states)
        
        # 验证处理器配置已设置
        self.assertEqual(DataHubHandler.config, config)
        self.assertEqual(DataHubHandler.dataset_states, dataset_states)
    
    def test_server_default_values(self):
        """测试服务器默认值"""
        config = {
            'server': {},
            'datasets': []
        }
        dataset_states = {}
        
        server = DataHubServer(config, dataset_states)
        
        self.assertEqual(server.host, '0.0.0.0')
        self.assertEqual(server.port, 8080)


if __name__ == '__main__':
    unittest.main(verbosity=2)
