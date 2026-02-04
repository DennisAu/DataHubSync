"""
测试客户端配置管理
"""

import os
import json
import yaml
import unittest
from pathlib import Path
from unittest.mock import patch, mock_open

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from sync_client import DataSyncClient


class TestClientConfig(unittest.TestCase):
    """测试客户端配置管理"""
    
    def setUp(self):
        """设置测试环境"""
        self.test_dir = Path(__file__).parent / 'test_data' / 'client_config'
        self.test_dir.mkdir(parents=True, exist_ok=True)
    
    def tearDown(self):
        """清理测试环境"""
        if self.test_dir.exists():
            import shutil
            shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_load_config_from_yaml(self):
        """测试从YAML文件加载配置"""
        config_content = {
            'hub': {
                'url': 'https://test.datahub.com',
                'timeout': 300
            },
            'datasets': [
                {
                    'name': 'stock-trading-data-pro',
                    'local_dir': '/data/stock-trading-data-pro'
                },
                {
                    'name': 'stock-fin-data-xbx',
                    'local_dir': '/data/stock-fin-data-xbx'
                }
            ],
            'logging': {
                'level': 'INFO',
                'file': 'logs/sync.log'
            }
        }
        
        config_file = self.test_dir / 'config.yaml'
        with open(config_file, 'w', encoding='utf-8') as f:
            yaml.dump(config_content, f)
        
        # 模拟命令行参数
        with patch('sys.argv', ['sync_client.py', str(config_file)]):
            # 加载配置
            with open(config_file, 'r', encoding='utf-8') as f:
                loaded_config = yaml.safe_load(f)
        
        self.assertEqual(loaded_config['hub']['url'], 'https://test.datahub.com')
        self.assertEqual(loaded_config['hub']['timeout'], 300)
        self.assertEqual(len(loaded_config['datasets']), 2)
        self.assertEqual(loaded_config['datasets'][0]['name'], 'stock-trading-data-pro')
    
    def test_config_validation_missing_hub(self):
        """测试配置验证（缺少hub配置）"""
        config_content = {
            'datasets': [
                {
                    'name': 'stock-trading-data-pro',
                    'local_dir': '/data/stock-trading-data-pro'
                }
            ]
        }
        
        config_file = self.test_dir / 'config_invalid.yaml'
        with open(config_file, 'w', encoding='utf-8') as f:
            yaml.dump(config_content, f)
        
        # 加载配置
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # 验证缺少hub配置
        with self.assertRaises(KeyError):
            client = DataSyncClient(config, str(self.test_dir / '.last_sync.json'))
    
    def test_config_validation_missing_datasets(self):
        """测试配置验证（缺少datasets配置）"""
        config_content = {
            'hub': {
                'url': 'https://test.datahub.com',
                'timeout': 300
            }
        }
        
        config_file = self.test_dir / 'config_invalid.yaml'
        with open(config_file, 'w', encoding='utf-8') as f:
            yaml.dump(config_content, f)
        
        # 加载配置
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # 创建客户端（应该允许空datasets）
        client = DataSyncClient(config, str(self.test_dir / '.last_sync.json'))
        self.assertEqual(len(client.datasets), 0)
    
    def test_config_default_values(self):
        """测试配置默认值"""
        config_content = {
            'hub': {
                'url': 'https://test.datahub.com'
            },
            'datasets': [
                {
                    'name': 'stock-trading-data-pro',
                    'local_dir': '/data/stock-trading-data-pro'
                }
            ]
        }
        
        # 创建客户端
        client = DataSyncClient(config_content, str(self.test_dir / '.last_sync.json'))
        
        # 验证默认值
        self.assertEqual(client.timeout, 300)  # 默认timeout
    
    def test_sync_state_file_creation(self):
        """测试同步状态文件创建"""
        config_content = {
            'hub': {
                'url': 'https://test.datahub.com'
            },
            'datasets': [
                {
                    'name': 'stock-trading-data-pro',
                    'local_dir': '/data/stock-trading-data-pro'
                }
            ]
        }
        
        sync_state_file = self.test_dir / '.last_sync.json'
        
        # 创建客户端
        client = DataSyncClient(config_content, str(sync_state_file))
        
        # 验证状态文件已创建（目录存在）
        self.assertTrue(sync_state_file.parent.exists())
        
        # 验证初始状态为空
        state = client._load_sync_state()
        self.assertEqual(state, {})
    
    def test_sync_state_persistence(self):
        """测试同步状态持久化"""
        config_content = {
            'hub': {
                'url': 'https://test.datahub.com'
            },
            'datasets': [
                {
                    'name': 'stock-trading-data-pro',
                    'local_dir': '/data/stock-trading-data-pro'
                }
            ]
        }
        
        sync_state_file = self.test_dir / '.last_sync.json'
        
        # 创建客户端
        client = DataSyncClient(config_content, str(sync_state_file))
        
        # 保存状态
        test_state = {
            'stock-trading-data-pro': '2025-02-04T20:15:00Z'
        }
        client._save_sync_state(test_state)
        
        # 验证文件已创建
        self.assertTrue(sync_state_file.exists())
        
        # 验证文件内容
        with open(sync_state_file, 'r', encoding='utf-8') as f:
            saved_state = json.load(f)
        self.assertEqual(saved_state, test_state)
        
        # 创建新客户端实例，验证状态加载
        client2 = DataSyncClient(config_content, str(sync_state_file))
        loaded_state = client2._load_sync_state()
        self.assertEqual(loaded_state, test_state)
    
    def test_url_parsing(self):
        """测试URL解析"""
        test_cases = [
            ('https://data.quantrade.fun', 'data.quantrade.fun', 443),
            ('http://localhost:8080', 'localhost', 8080),
            ('https://test.example.com:9000', 'test.example.com', 9000)
        ]
        
        config_content = {
            'hub': {
                'url': 'https://data.quantrade.fun'
            },
            'datasets': []
        }
        
        for url, expected_host, expected_port in test_cases:
            config_content['hub']['url'] = url
            client = DataSyncClient(config_content, str(self.test_dir / '.last_sync.json'))
            
            self.assertEqual(client.hub_host, expected_host)
            self.assertEqual(client.hub_port, expected_port)
    
    def test_logging_configuration(self):
        """测试日志配置"""
        config_content = {
            'hub': {
                'url': 'https://test.datahub.com'
            },
            'datasets': [],
            'logging': {
                'level': 'DEBUG',
                'file': str(self.test_dir / 'test.log')
            }
        }
        
        # 创建客户端
        client = DataSyncClient(config_content, str(self.test_dir / '.last_sync.json'))
        
        # 验证日志级别
        self.assertEqual(client.logger.level, 10)  # DEBUG级别
        
        # 验证日志文件handler
        log_file = Path(config_content['logging']['file'])
        self.assertTrue(log_file.parent.exists())
    
    def test_logging_default_configuration(self):
        """测试日志默认配置"""
        config_content = {
            'hub': {
                'url': 'https://test.datahub.com'
            },
            'datasets': []
        }
        
        # 创建客户端（无logging配置）
        client = DataSyncClient(config_content, str(self.test_dir / '.last_sync.json'))
        
        # 验证默认日志级别
        self.assertEqual(client.logger.level, 20)  # INFO级别
        
        # 验证只有console handler
        self.assertEqual(len(client.logger.handlers), 1)
    
    def test_config_with_full_paths(self):
        """测试包含完整路径的配置"""
        config_content = {
            'hub': {
                'url': 'https://test.datahub.com',
                'timeout': 600
            },
            'datasets': [
                {
                    'name': 'test-dataset',
                    'local_dir': str(self.test_dir / 'data' / 'test-dataset')
                }
            ],
            'logging': {
                'level': 'WARNING',
                'file': str(self.test_dir / 'logs' / 'sync.log')
            }
        }
        
        # 创建客户端
        client = DataSyncClient(config_content, str(self.test_dir / '.last_sync.json'))
        
        # 验证配置加载
        self.assertEqual(client.timeout, 600)
        self.assertEqual(len(client.datasets), 1)
        self.assertEqual(client.datasets[0]['local_dir'], str(self.test_dir / 'data' / 'test-dataset'))
        
        # 验证日志级别
        self.assertEqual(client.logger.level, 30)  # WARNING级别
    
    def test_multiple_datasets_config(self):
        """测试多数据集配置"""
        config_content = {
            'hub': {
                'url': 'https://test.datahub.com'
            },
            'datasets': [
                {
                    'name': 'stock-trading-data-pro',
                    'local_dir': '/data/stock-trading-data-pro'
                },
                {
                    'name': 'stock-fin-data-xbx',
                    'local_dir': '/data/stock-fin-data-xbx'
                },
                {
                    'name': 'stock-etf-trading-data',
                    'local_dir': '/data/stock-etf-trading-data'
                }
            ]
        }
        
        # 创建客户端
        client = DataSyncClient(config_content, str(self.test_dir / '.last_sync.json'))
        
        # 验证数据集数量
        self.assertEqual(len(client.datasets), 3)
        
        # 验证数据集名称
        dataset_names = [ds['name'] for ds in client.datasets]
        expected_names = ['stock-trading-data-pro', 'stock-fin-data-xbx', 'stock-etf-trading-data']
        self.assertEqual(dataset_names, expected_names)


if __name__ == '__main__':
    unittest.main()