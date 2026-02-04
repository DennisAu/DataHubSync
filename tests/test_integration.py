#!/usr/bin/env python3
"""
集成测试 - DataHubSync Hub 完整流程测试

测试完整流程:
1. 数据更新 → 新鲜度检测 → 打包 → HTTP服务
2. 使用临时目录模拟真实场景

运行:
    pytest tests/test_integration.py -v
    python tests/test_integration.py
"""

import os
import sys
import time
import json
import shutil
import signal
import tempfile
import threading
import unittest
from pathlib import Path
from http.client import HTTPConnection

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))
# 添加项目根目录到路径（用于导入 server 模块）
sys.path.insert(0, str(Path(__file__).parent.parent))

from state_manager import StateManager
from scheduler import Scheduler
from http_server import DataHubServer, DataHubHandler
from freshness_checker import FreshnessResult


class TestIntegration(unittest.TestCase):
    """集成测试类"""
    
    def setUp(self):
        """测试前准备 - 创建临时目录和测试数据"""
        self.test_dir = Path(tempfile.mkdtemp(prefix="datahub_test_"))
        self.data_root = self.test_dir / "data"
        self.cache_dir = self.test_dir / "cache"
        self.state_file = self.test_dir / "state.json"
        
        self.data_root.mkdir()
        self.cache_dir.mkdir()
        
        # 创建测试数据集
        self.dataset_name = "test-dataset"
        self.dataset_path = self.data_root / self.dataset_name
        self.dataset_path.mkdir()
        
        # 创建测试数据文件
        (self.dataset_path / "data.csv").write_text("date,value\n2024-01-01,100\n")
        
        # 创建配置
        self.config = {
            'server': {
                'host': '127.0.0.1',
                'port': 0,  # 自动分配端口
                'data_root': str(self.data_root),
                'cache_dir': str(self.cache_dir)
            },
            'datasets': [
                {
                    'name': self.dataset_name,
                    'path': self.dataset_name,
                    'freshness_threshold': 0.5  # 降低阈值以便测试
                }
            ],
            'calendar': {
                'period_offset_file': str(self.test_dir / "calendar.csv")
            },
            'check': {
                'interval_minutes': 1,  # 短间隔用于测试
                'debounce_seconds': 1   # 短防抖用于测试
            },
            'packaging': {
                'format': 'zip',
                'keep_versions': 2
            },
            'logging': {
                'level': 'WARNING',  # 减少日志输出
                'file': None
            }
        }
        
        # 创建日历文件 (符合 CalendarReader 格式要求)
        calendar_content = "交易日期,offset\n2024-01-01,0\n2024-01-02,1\n"
        (self.test_dir / "calendar.csv").write_text(calendar_content)
    
    def tearDown(self):
        """测试后清理 - 删除临时目录"""
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_state_manager_initialization(self):
        """测试1: StateManager 初始化"""
        state_manager = StateManager(str(self.state_file))
        
        self.assertEqual(state_manager.get_all(), {})
        
        # 测试更新状态
        state_manager.update(self.dataset_name, status="testing")
        self.assertEqual(state_manager.get(self.dataset_name)['status'], 'testing')
        
        # 验证状态已保存到文件
        self.assertTrue(self.state_file.exists())
        saved_state = json.loads(self.state_file.read_text())
        self.assertEqual(saved_state[self.dataset_name]['status'], 'testing')
    
    def test_scheduler_initialization(self):
        """测试2: Scheduler 初始化"""
        state_manager = StateManager(str(self.state_file))
        scheduler = Scheduler(self.config, state_manager)
        
        self.assertFalse(scheduler.is_running())
        
        scheduler.start()
        time.sleep(0.3)  # 等待启动
        
        self.assertTrue(scheduler.is_running())
        
        scheduler.stop()
        time.sleep(0.2)
        
        self.assertFalse(scheduler.is_running())
    
    def test_http_server_initialization(self):
        """测试3: HTTP Server 初始化"""
        state_manager = StateManager(str(self.state_file))
        
        # 更新一些状态
        state_manager.update(self.dataset_name, status="ready")
        
        # 创建服务器
        server = DataHubServer(self.config, state_manager.get_all())
        
        self.assertIsNotNone(server)
        self.assertEqual(server.host, '127.0.0.1')
    
    def test_server_api_health(self):
        """测试4: HTTP API 健康检查端点"""
        state_manager = StateManager(str(self.state_file))
        state_manager.update(self.dataset_name, status="ready")
        
        # 创建并启动服务器
        server = DataHubServer(self.config, state_manager.get_all())
        
        # 获取实际分配的端口
        port = server.server.server_address[1]
        
        # 在后台线程运行服务器（处理单个请求）
        def run_server():
            try:
                server.run_once()
            except Exception:
                pass
        
        # 测试健康检查
        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
        time.sleep(0.2)
        
        conn = HTTPConnection('127.0.0.1', port, timeout=3)
        try:
            conn.request('GET', '/health')
            response = conn.getresponse()
            self.assertEqual(response.status, 200)
            data = json.loads(response.read().decode())
            self.assertEqual(data['status'], 'ok')
        finally:
            conn.close()
    
    def test_server_api_datasets(self):
        """测试5: HTTP API 数据集列表端点"""
        state_manager = StateManager(str(self.state_file))
        state_manager.update(self.dataset_name, status="ready")
        
        # 创建服务器
        server = DataHubServer(self.config, state_manager.get_all())
        port = server.server.server_address[1]
        
        # 在后台线程运行服务器
        def run_server():
            try:
                server.run_once()
            except Exception:
                pass
        
        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
        time.sleep(0.2)
        
        conn = HTTPConnection('127.0.0.1', port, timeout=3)
        try:
            conn.request('GET', '/api/datasets')
            response = conn.getresponse()
            self.assertEqual(response.status, 200)
            data = json.loads(response.read().decode())
            self.assertIn('datasets', data)
            
            # 验证数据集信息
            datasets = data['datasets']
            self.assertTrue(len(datasets) > 0)
            self.assertEqual(datasets[0]['name'], self.dataset_name)
        finally:
            conn.close()
    
    def test_state_persistence(self):
        """测试6: 状态持久化"""
        # 第一个实例创建状态
        state_manager1 = StateManager(str(self.state_file))
        state_manager1.update(self.dataset_name, status="packaging", fresh_ratio=0.95)
        
        # 第二个实例加载状态
        state_manager2 = StateManager(str(self.state_file))
        state = state_manager2.get(self.dataset_name)
        
        self.assertEqual(state['status'], 'packaging')
        self.assertEqual(state['fresh_ratio'], 0.95)


class TestServerModule(unittest.TestCase):
    """测试 server.py 模块功能"""
    
    def setUp(self):
        """导入 server 模块"""
        import importlib.util
        spec = importlib.util.spec_from_file_location("server", str(Path(__file__).parent.parent / "server.py"))
        self.server_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.server_module)
    
    def test_load_config(self):
        """测试配置加载"""
        # 创建临时配置文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("server:\n  port: 9090\n")
            config_path = f.name
        
        try:
            config = self.server_module.load_config(config_path)
            self.assertEqual(config['server']['port'], 9090)
        finally:
            os.unlink(config_path)
    
    def test_load_config_not_found(self):
        """测试配置文件不存在"""
        with self.assertRaises(FileNotFoundError):
            self.server_module.load_config("/nonexistent/config.yaml")
    
    def test_setup_logging(self):
        """测试日志配置"""
        import logging
        
        config = {
            'logging': {
                'level': 'DEBUG',
                'format': '%(levelname)s: %(message)s',
                'file': None  # 不写入文件
            }
        }
        
        logger = self.server_module.setup_logging(config)
        self.assertIsInstance(logger, logging.Logger)
        # 检查根日志器的级别是否设置为 DEBUG
        root_logger = logging.getLogger()
        self.assertEqual(root_logger.level, logging.DEBUG)


def run_integration_tests():
    """运行集成测试并生成报告"""
    print("=" * 60)
    print("DataHubSync Hub 集成测试")
    print("=" * 60)
    
    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # 添加测试
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestServerModule))
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # 打印总结
    print("\n" + "=" * 60)
    print("测试总结:")
    print(f"  运行测试: {result.testsRun}")
    print(f"  通过: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"  失败: {len(result.failures)}")
    print(f"  错误: {len(result.errors)}")
    print("=" * 60)
    
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(run_integration_tests())
