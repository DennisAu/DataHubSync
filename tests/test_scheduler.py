"""
Tests for Scheduler
"""

import os
import csv
import time
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from scheduler import Scheduler
from state_manager import StateManager


class TestScheduler(unittest.TestCase):
    """测试 Scheduler 功能"""
    
    def setUp(self):
        """测试前创建临时目录和配置"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.data_root = self.temp_dir / 'data'
        self.cache_dir = self.temp_dir / 'cache'
        self.state_file = self.temp_dir / '.state.json'
        self.calendar_file = self.temp_dir / 'calendar.csv'
        
        self.data_root.mkdir()
        self.cache_dir.mkdir()
        
        # 创建测试日历文件
        with open(self.calendar_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['交易日期'])
            writer.writerow(['2024-01-10'])
            writer.writerow(['2024-01-11'])
            writer.writerow(['2024-01-12'])
        
        # 创建测试配置
        self.config = {
            'server': {
                'data_root': str(self.data_root),
                'cache_dir': str(self.cache_dir)
            },
            'check': {
                'interval_minutes': 0.1,  # 6秒，用于测试
                'debounce_seconds': 1     # 1秒，用于测试
            },
            'calendar': {
                'period_offset_file': str(self.calendar_file)
            },
            'packaging': {
                'keep_versions': 2
            },
            'datasets': [
                {
                    'name': 'test-dataset',
                    'path': 'test-dataset',
                    'freshness_threshold': 0.85
                }
            ]
        }
        
        # 创建状态管理器
        self.state_manager = StateManager(str(self.state_file))
        
        # 创建测试数据
        test_dataset_dir = self.data_root / 'test-dataset'
        test_dataset_dir.mkdir()
        
        # 创建测试文件
        test_file = test_dataset_dir / 'data_20240112.csv'
        test_file.write_text('test,data\n1,2\n')
        # 设置文件修改时间为最近（新鲜）
        os.utime(test_file, (time.time(), time.time()))
    
    def tearDown(self):
        """测试后清理"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_init(self):
        """测试调度器初始化"""
        scheduler = Scheduler(self.config, self.state_manager)
        
        self.assertEqual(scheduler.data_root, str(self.data_root))
        self.assertEqual(scheduler.cache_dir, str(self.cache_dir))
        self.assertEqual(scheduler.interval_minutes, 0.1)
        self.assertEqual(scheduler.debounce_seconds, 1)
        self.assertFalse(scheduler.is_running())
    
    def test_start_stop(self):
        """测试启动和停止"""
        scheduler = Scheduler(self.config, self.state_manager)
        
        # 启动
        scheduler.start()
        self.assertTrue(scheduler.is_running())
        
        # 再次启动应该被忽略
        scheduler.start()
        self.assertTrue(scheduler.is_running())
        
        # 停止
        scheduler.stop()
        self.assertFalse(scheduler.is_running())
        
        # 再次停止应该被忽略
        scheduler.stop()
        self.assertFalse(scheduler.is_running())
    
    @patch('freshness_checker.FreshnessChecker.check_stable')
    @patch('freshness_checker.FreshnessChecker.check')
    def test_check_dataset_not_fresh(self, mock_check, mock_check_stable):
        """测试数据集不够新鲜的情况"""
        from freshness_checker import FreshnessResult
        
        # Mock 返回不够新鲜的结果
        mock_check.return_value = FreshnessResult(
            total_count=10,
            fresh_count=5,
            fresh_ratio=0.5,
            last_updated='2024-01-12T10:00:00'
        )
        
        scheduler = Scheduler(self.config, self.state_manager)
        
        # 执行检查
        scheduler._check_dataset('test-dataset', 'test-dataset', '20240112', 0.85)
        
        # 验证状态
        state = self.state_manager.get('test-dataset')
        self.assertEqual(state['status'], 'not_fresh')
        self.assertEqual(state['freshness']['fresh_ratio'], 0.5)
        
        # 防抖检查不应该被调用
        mock_check_stable.assert_not_called()
    
    @patch('freshness_checker.FreshnessChecker.check_stable')
    @patch('freshness_checker.FreshnessChecker.check')
    def test_check_dataset_fresh_but_unstable(self, mock_check, mock_check_stable):
        """测试数据集新鲜但不稳定的情况"""
        from freshness_checker import FreshnessResult
        
        # Mock 返回新鲜的结果
        mock_check.return_value = FreshnessResult(
            total_count=10,
            fresh_count=9,
            fresh_ratio=0.9,
            last_updated='2024-01-12T10:00:00'
        )
        
        # Mock 防抖检查返回 None（不稳定）
        mock_check_stable.return_value = None
        
        scheduler = Scheduler(self.config, self.state_manager)
        
        # 执行检查
        scheduler._check_dataset('test-dataset', 'test-dataset', '20240112', 0.85)
        
        # 验证状态
        state = self.state_manager.get('test-dataset')
        self.assertEqual(state['status'], 'unstable')
        
        # 防抖检查应该被调用
        mock_check_stable.assert_called_once_with('20240112', debounce_seconds=1)
    
    @patch('packager.Packager.package')
    @patch('freshness_checker.FreshnessChecker.check_stable')
    @patch('freshness_checker.FreshnessChecker.check')
    def test_check_dataset_fresh_and_stable(self, mock_check, mock_check_stable, mock_package):
        """测试数据集新鲜且稳定的情况"""
        from freshness_checker import FreshnessResult
        
        # Mock 返回新鲜的结果
        mock_check.return_value = FreshnessResult(
            total_count=10,
            fresh_count=9,
            fresh_ratio=0.9,
            last_updated='2024-01-12T10:00:00'
        )
        
        # Mock 防抖检查返回稳定结果
        mock_check_stable.return_value = FreshnessResult(
            total_count=10,
            fresh_count=9,
            fresh_ratio=0.9,
            last_updated='2024-01-12T10:00:00'
        )
        
        # Mock 打包返回成功
        mock_package.return_value = {
            'success': True,
            'zip_path': str(self.cache_dir / 'test-dataset_20240112_120000.zip'),
            'file_count': 10,
            'zip_size': 1024,
            'error': None
        }
        
        scheduler = Scheduler(self.config, self.state_manager)
        
        # 执行检查
        scheduler._check_dataset('test-dataset', 'test-dataset', '20240112', 0.85)
        
        # 验证状态
        state = self.state_manager.get('test-dataset')
        self.assertEqual(state['status'], 'ready')
        self.assertIn('last_packaged_at', state)
        
        # 打包应该被调用
        mock_package.assert_called_once()
    
    @patch('packager.Packager.package')
    @patch('freshness_checker.FreshnessChecker.check_stable')
    @patch('freshness_checker.FreshnessChecker.check')
    def test_check_dataset_packaging_failed(self, mock_check, mock_check_stable, mock_package):
        """测试打包失败的情况"""
        from freshness_checker import FreshnessResult
        
        # Mock 返回新鲜的结果
        mock_check.return_value = FreshnessResult(
            total_count=10,
            fresh_count=9,
            fresh_ratio=0.9,
            last_updated='2024-01-12T10:00:00'
        )
        
        # Mock 防抖检查返回稳定结果
        mock_check_stable.return_value = FreshnessResult(
            total_count=10,
            fresh_count=9,
            fresh_ratio=0.9,
            last_updated='2024-01-12T10:00:00'
        )
        
        # Mock 打包返回失败
        mock_package.return_value = {
            'success': False,
            'zip_path': None,
            'file_count': 0,
            'zip_size': 0,
            'error': 'Packaging failed'
        }
        
        scheduler = Scheduler(self.config, self.state_manager)
        
        # 执行检查
        scheduler._check_dataset('test-dataset', 'test-dataset', '20240112', 0.85)
        
        # 验证状态为错误
        state = self.state_manager.get('test-dataset')
        self.assertEqual(state['status'], 'error')
        self.assertEqual(state['error'], 'Packaging failed')
    
    def test_check_all_datasets(self):
        """测试检查所有数据集"""
        scheduler = Scheduler(self.config, self.state_manager)
        
        # Mock _check_dataset 方法
        scheduler._check_dataset = Mock()
        
        # 执行检查
        scheduler._check_all_datasets()
        
        # 验证 _check_dataset 被调用
        scheduler._check_dataset.assert_called_once()
    
    def test_force_check(self):
        """测试强制检查"""
        scheduler = Scheduler(self.config, self.state_manager)
        
        # Mock _check_all_datasets 方法
        scheduler._check_all_datasets = Mock()
        
        # 强制检查
        scheduler.force_check()
        
        # 等待线程完成
        time.sleep(0.1)
        
        # 验证 _check_all_datasets 被调用
        scheduler._check_all_datasets.assert_called_once()


if __name__ == '__main__':
    unittest.main()
