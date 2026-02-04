"""
测试客户端同步器
"""

import os
import json
import time
import shutil
import zipfile
import unittest
import threading
from pathlib import Path
from unittest.mock import patch, Mock, MagicMock
from datetime import datetime, timezone

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from sync_client import DataSyncClient, SyncResult


class TestDataSyncClient(unittest.TestCase):
    """测试数据同步客户端"""
    
    def setUp(self):
        """设置测试环境"""
        self.test_dir = Path(__file__).parent / 'test_data' / 'sync_client'
        self.client_dir = self.test_dir / 'client'
        self.data_dir = self.test_dir / 'data'
        self.cache_dir = self.test_dir / 'cache'
        
        # 创建测试目录
        self.client_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建测试配置
        self.config = {
            'hub': {
                'url': 'https://test.datahub.com',
                'timeout': 30
            },
            'datasets': [
                {
                    'name': 'stock-trading-data-pro',
                    'local_dir': str(self.data_dir / 'stock-trading-data-pro')
                },
                {
                    'name': 'stock-fin-data-xbx',
                    'local_dir': str(self.data_dir / 'stock-fin-data-xbx')
                }
            ],
            'logging': {
                'level': 'INFO',
                'file': str(self.client_dir / 'sync.log')
            }
        }
        
        # 创建同步状态文件
        self.sync_state_file = self.client_dir / '.last_sync.json'
        
        # 创建客户端实例
        self.client = DataSyncClient(self.config, str(self.sync_state_file))
    
    def tearDown(self):
        """清理测试环境"""
        import time
        import logging
        # 关闭所有日志文件句柄
        for handler in logging.getLogger().handlers[:]:
            handler.close()
            logging.getLogger().removeHandler(handler)
        time.sleep(0.1)  # 等待文件释放
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_init_client(self):
        """测试客户端初始化"""
        self.assertEqual(self.client.hub_url, 'https://test.datahub.com')
        self.assertEqual(len(self.client.datasets), 2)
        self.assertEqual(self.client.timeout, 30)
    
    def test_load_sync_state_no_file(self):
        """测试加载同步状态（无文件）"""
        state = self.client._load_sync_state()
        self.assertEqual(state, {})
    
    def test_load_sync_state_existing_file(self):
        """测试加载同步状态（文件存在）"""
        # 创建同步状态文件
        test_state = {
            'stock-trading-data-pro': '2025-02-03T20:15:00Z',
            'stock-fin-data-xbx': '2025-02-03T07:05:00Z'
        }
        with open(self.sync_state_file, 'w') as f:
            json.dump(test_state, f)
        
        state = self.client._load_sync_state()
        self.assertEqual(state, test_state)
    
    def test_save_sync_state(self):
        """测试保存同步状态"""
        test_state = {
            'stock-trading-data-pro': '2025-02-04T20:15:00Z'
        }
        
        self.client._save_sync_state(test_state)
        
        # 验证文件已创建
        self.assertTrue(self.sync_state_file.exists())
        
        # 验证内容
        with open(self.sync_state_file, 'r') as f:
            saved_state = json.load(f)
        self.assertEqual(saved_state, test_state)
    
    @patch('sync_client.http.client.HTTPSConnection')
    def test_fetch_datasets_success(self, mock_https_connection):
        """测试获取数据集列表（成功）"""
        # 模拟HTTP响应
        mock_response = Mock()
        mock_response.read.return_value = json.dumps({
            'generated_at': '2025-02-04T20:30:00Z',
            'datasets': [
                {
                    'name': 'stock-trading-data-pro',
                    'last_updated': '2025-02-04T20:15:00Z',
                    'file_count': 5600,
                    'total_size': 560000000,
                    'package_ready': True,
                    'package_size': 180000000
                },
                {
                    'name': 'stock-fin-data-xbx',
                    'last_updated': '2025-02-04T07:05:00Z',
                    'file_count': 3200,
                    'total_size': 32000000,
                    'package_ready': True,
                    'package_size': 10000000
                }
            ]
        }).encode('utf-8')
        
        mock_conn = Mock()
        mock_conn.getresponse.return_value = mock_response
        mock_https_connection.return_value.__enter__.return_value = mock_conn
        
        # 执行测试
        datasets = self.client._fetch_datasets()
        
        # 验证结果
        self.assertEqual(len(datasets), 2)
        self.assertEqual(datasets[0]['name'], 'stock-trading-data-pro')
        self.assertEqual(datasets[0]['last_updated'], '2025-02-04T20:15:00Z')
        self.assertTrue(datasets[0]['package_ready'])
        
        # 验证HTTP调用
        mock_https_connection.assert_called_once_with('test.datahub.com', timeout=30)
        mock_conn.request.assert_called_once_with('GET', '/api/datasets')
    
    @patch('sync_client.http.client.HTTPSConnection')
    def test_fetch_datasets_http_error(self, mock_https_connection):
        """测试获取数据集列表（HTTP错误）"""
        mock_https_connection.side_effect = Exception("Connection error")
        
        with self.assertRaises(Exception) as cm:
            self.client._fetch_datasets()
        
        self.assertIn("Connection error", str(cm.exception))
    
    def test_need_sync_new_dataset(self):
        """测试是否需要同步（新数据集）"""
        remote_info = {
            'name': 'stock-trading-data-pro',
            'last_updated': '2025-02-04T20:15:00Z',
            'package_ready': True
        }
        
        # 本地无记录，需要同步
        self.assertTrue(self.client._need_sync(remote_info, {}))
    
    def test_need_sync_remote_newer(self):
        """测试是否需要同步（远程更新）"""
        remote_info = {
            'name': 'stock-trading-data-pro',
            'last_updated': '2025-02-04T20:15:00Z',
            'package_ready': True
        }
        
        local_state = {
            'stock-trading-data-pro': '2025-02-03T20:15:00Z'  # 比远程旧
        }
        
        self.assertTrue(self.client._need_sync(remote_info, local_state))
    
    def test_need_sync_up_to_date(self):
        """测试是否需要同步（已最新）"""
        remote_info = {
            'name': 'stock-trading-data-pro',
            'last_updated': '2025-02-04T20:15:00Z',
            'package_ready': True
        }
        
        local_state = {
            'stock-trading-data-pro': '2025-02-04T20:15:00Z'  # 与远程相同
        }
        
        self.assertFalse(self.client._need_sync(remote_info, local_state))
    
    def test_need_sync_package_not_ready(self):
        """测试是否需要同步（包未准备好）"""
        remote_info = {
            'name': 'stock-trading-data-pro',
            'last_updated': '2025-02-04T20:15:00Z',
            'package_ready': False
        }
        
        local_state = {}
        
        # 包未准备好，不同步
        self.assertFalse(self.client._need_sync(remote_info, local_state))
    
    @patch('http.client.HTTPSConnection')
    def test_download_package_success(self, mock_https_connection):
        """测试下载数据包（成功）"""
        # 创建测试zip文件
        test_zip_path = self.cache_dir / 'test.zip'
        with zipfile.ZipFile(test_zip_path, 'w') as zf:
            zf.writestr('test.csv', 'symbol,date,open,high,low,close,volume\nAAPL,2025-02-04,150,155,149,154,1000000\n')
        
        # 模拟HTTP响应
        with open(test_zip_path, 'rb') as f:
            zip_content = f.read()
        
        # 直接返回配置好的mock，不使用context manager
        mock_conn = Mock()
        mock_response = Mock()
        mock_response.status = 200
        mock_response.read.side_effect = [zip_content, b'']
        mock_conn.getresponse.return_value = mock_response
        mock_https_connection.return_value = mock_conn
        
        # 执行测试
        output_path = self.cache_dir / 'downloaded.zip'
        success = self.client._download_package('stock-trading-data-pro', output_path)
        
        # 调试信息
        print(f"Mock response status: {mock_response.status}")
        print(f"Status type: {type(mock_response.status)}")
        print(f"Status == 200: {mock_response.status == 200}")
        print(f"Success: {success}")
        
        self.assertTrue(success)
        self.assertTrue(output_path.exists())
        
        # 验证下载的zip文件
        with zipfile.ZipFile(output_path, 'r') as zf:
            files = zf.namelist()
            self.assertIn('test.csv', files)
        
        # 验证HTTP调用
        expected_url = '/package/stock-trading-data-pro.zip'
        mock_conn.request.assert_called_once_with('GET', expected_url)
    
    @patch('sync_client.http.client.HTTPSConnection')
    def test_download_package_404(self, mock_https_connection):
        """测试下载数据包（404错误）"""
        mock_response = Mock()
        mock_response.status = 404
        mock_response.reason = "Not Found"
        
        mock_conn = Mock()
        mock_conn.getresponse.return_value = mock_response
        mock_https_connection.return_value.__enter__.return_value = mock_conn
        
        output_path = self.cache_dir / 'downloaded.zip'
        success = self.client._download_package('stock-trading-data-pro', output_path)
        
        self.assertFalse(success)
        self.assertFalse(output_path.exists())
    
    def test_extract_package_success(self):
        """测试解压数据包（成功）"""
        # 创建测试zip文件
        test_zip_path = self.cache_dir / 'test.zip'
        with zipfile.ZipFile(test_zip_path, 'w') as zf:
            zf.writestr('data1.csv', 'symbol,date\nAAPL,2025-02-04\n')
            zf.writestr('data2.csv', 'symbol,price\nAAPL,150\n')
        
        # 创建目标目录
        target_dir = self.data_dir / 'test-dataset'
        target_dir.mkdir(parents=True, exist_ok=True)
        
        # 执行解压
        success = self.client._extract_package(test_zip_path, target_dir)
        
        self.assertTrue(success)
        
        # 验证文件已解压
        self.assertTrue((target_dir / 'data1.csv').exists())
        self.assertTrue((target_dir / 'data2.csv').exists())
        
        # 验证文件内容
        with open(target_dir / 'data1.csv', 'r') as f:
            content = f.read()
            self.assertIn('AAPL,2025-02-04', content)
    
    def test_extract_package_invalid_zip(self):
        """测试解压数据包（无效zip）"""
        # 创建无效zip文件
        invalid_zip_path = self.cache_dir / 'invalid.zip'
        with open(invalid_zip_path, 'w') as f:
            f.write('not a zip file')
        
        target_dir = self.data_dir / 'test-dataset'
        target_dir.mkdir(parents=True, exist_ok=True)
        
        success = self.client._extract_package(invalid_zip_path, target_dir)
        self.assertFalse(success)
    
    @patch.object(DataSyncClient, '_fetch_datasets')
    @patch.object(DataSyncClient, '_download_package')
    @patch.object(DataSyncClient, '_extract_package')
    def test_sync_dataset_success(self, mock_extract, mock_download, mock_fetch):
        """测试同步单个数据集（成功）"""
        # 模拟远程数据
        mock_fetch.return_value = [
            {
                'name': 'stock-trading-data-pro',
                'last_updated': '2025-02-04T20:15:00Z',
                'package_ready': True
            }
        ]
        
        # 模拟下载成功
        mock_download.return_value = True
        
        # 模拟解压成功
        mock_extract.return_value = True
        
        # 执行同步
        result = self.client.sync_dataset('stock-trading-data-pro')
        
        # 验证结果
        self.assertTrue(result.success)
        self.assertEqual(result.dataset_name, 'stock-trading-data-pro')
        self.assertIsNone(result.error)
        
        # 验证调用
        mock_fetch.assert_called_once()
        mock_download.assert_called_once()
        mock_extract.assert_called_once()
        
        # 验证状态已更新
        updated_state = self.client._load_sync_state()
        self.assertEqual(
            updated_state['stock-trading-data-pro'],
            '2025-02-04T20:15:00Z'
        )
    
    @patch.object(DataSyncClient, '_fetch_datasets')
    def test_sync_dataset_up_to_date(self, mock_fetch):
        """测试同步单个数据集（已是最新）"""
        # 模拟远程数据
        mock_fetch.return_value = [
            {
                'name': 'stock-trading-data-pro',
                'last_updated': '2025-02-04T20:15:00Z',
                'package_ready': True
            }
        ]
        
        # 设置本地状态为最新
        self.client._save_sync_state({
            'stock-trading-data-pro': '2025-02-04T20:15:00Z'
        })
        
        # 执行同步
        result = self.client.sync_dataset('stock-trading-data-pro')
        
        # 验证结果
        self.assertTrue(result.success)
        self.assertEqual(result.status, 'up_to_date')
        
        # 验证未调用下载
        self.assertEqual(mock_fetch.call_count, 1)  # 只调用了一次fetch来获取状态
    
    @patch.object(DataSyncClient, '_fetch_datasets')
    @patch.object(DataSyncClient, '_download_package')
    def test_sync_dataset_download_failed(self, mock_download, mock_fetch):
        """测试同步单个数据集（下载失败）"""
        # 模拟远程数据
        mock_fetch.return_value = [
            {
                'name': 'stock-trading-data-pro',
                'last_updated': '2025-02-04T20:15:00Z',
                'package_ready': True
            }
        ]
        
        # 模拟下载失败
        mock_download.return_value = False
        
        # 执行同步
        result = self.client.sync_dataset('stock-trading-data-pro')
        
        # 验证结果
        self.assertFalse(result.success)
        self.assertEqual(result.status, 'download_failed')
        self.assertIsNotNone(result.error)
    
    @patch.object(DataSyncClient, 'sync_dataset')
    def test_sync_all_datasets(self, mock_sync_dataset):
        """测试同步所有数据集"""
        # 模拟单个同步结果
        mock_sync_dataset.side_effect = [
            SyncResult('stock-trading-data-pro', True, 'success', None),
            SyncResult('stock-fin-data-xbx', True, 'success', None)
        ]
        
        # 执行同步
        results = self.client.sync_all()
        
        # 验证结果
        self.assertEqual(len(results), 2)
        self.assertTrue(results[0].success)
        self.assertTrue(results[1].success)
        
        # 验证调用
        self.assertEqual(mock_sync_dataset.call_count, 2)
        mock_sync_dataset.assert_any_call('stock-trading-data-pro')
        mock_sync_dataset.assert_any_call('stock-fin-data-xbx')


class TestSyncResult(unittest.TestCase):
    """测试同步结果类"""
    
    def test_sync_result_creation(self):
        """测试同步结果创建"""
        result = SyncResult('test-dataset', True, 'success', None)
        
        self.assertEqual(result.dataset_name, 'test-dataset')
        self.assertTrue(result.success)
        self.assertEqual(result.status, 'success')
        self.assertIsNone(result.error)
    
    def test_sync_result_with_error(self):
        """测试带错误的同步结果"""
        error_msg = "Connection timeout"
        result = SyncResult('test-dataset', False, 'failed', error_msg)
        
        self.assertEqual(result.dataset_name, 'test-dataset')
        self.assertFalse(result.success)
        self.assertEqual(result.status, 'failed')
        self.assertEqual(result.error, error_msg)
    
    def test_sync_result_str_representation(self):
        """测试同步结果字符串表示"""
        result = SyncResult('test-dataset', True, 'success', None)
        str_repr = str(result)
        
        self.assertIn('test-dataset', str_repr)
        self.assertIn('success', str_repr)


if __name__ == '__main__':
    unittest.main()