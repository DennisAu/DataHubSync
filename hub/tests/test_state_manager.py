"""
Tests for StateManager
"""

import os
import json
import tempfile
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from state_manager import StateManager


class TestStateManager(unittest.TestCase):
    """测试 StateManager 功能"""
    
    def setUp(self):
        """测试前创建临时状态文件"""
        self.temp_dir = tempfile.mkdtemp()
        self.state_file = Path(self.temp_dir) / '.state.json'
        self.state_manager = StateManager(str(self.state_file))
    
    def tearDown(self):
        """测试后清理"""
        if self.state_file.exists():
            self.state_file.unlink()
        os.rmdir(self.temp_dir)
    
    def test_init_creates_empty_state(self):
        """测试初始化创建空状态"""
        self.assertEqual(self.state_manager.get_all(), {})
    
    def test_update_and_get(self):
        """测试更新和获取状态"""
        # 更新状态
        result = self.state_manager.update(
            'test-dataset',
            last_updated='2024-01-15T10:30:00',
            fresh_ratio=0.92,
            status='ready'
        )
        
        # 验证返回值
        self.assertEqual(result['last_updated'], '2024-01-15T10:30:00')
        self.assertEqual(result['fresh_ratio'], 0.92)
        self.assertEqual(result['status'], 'ready')
        self.assertIn('state_updated_at', result)
        
        # 验证获取
        state = self.state_manager.get('test-dataset')
        self.assertEqual(state['last_updated'], '2024-01-15T10:30:00')
        self.assertEqual(state['status'], 'ready')
    
    def test_get_nonexistent(self):
        """测试获取不存在的数据集状态"""
        state = self.state_manager.get('nonexistent')
        self.assertEqual(state, {})
    
    def test_get_all(self):
        """测试获取所有状态"""
        self.state_manager.update('dataset1', status='ready')
        self.state_manager.update('dataset2', status='pending')
        
        all_states = self.state_manager.get_all()
        self.assertEqual(len(all_states), 2)
        self.assertEqual(all_states['dataset1']['status'], 'ready')
        self.assertEqual(all_states['dataset2']['status'], 'pending')
    
    def test_persistence(self):
        """测试状态持久化到文件"""
        # 创建状态
        self.state_manager.update('test-dataset', status='ready', fresh_ratio=0.9)
        
        # 创建新的 StateManager 实例读取同一个文件
        new_manager = StateManager(str(self.state_file))
        
        # 验证状态被正确加载
        state = new_manager.get('test-dataset')
        self.assertEqual(state['status'], 'ready')
        self.assertEqual(state['fresh_ratio'], 0.9)
    
    def test_delete(self):
        """测试删除状态"""
        self.state_manager.update('test-dataset', status='ready')
        
        # 删除
        result = self.state_manager.delete('test-dataset')
        self.assertTrue(result)
        
        # 验证已删除
        self.assertEqual(self.state_manager.get('test-dataset'), {})
        
        # 删除不存在的
        result = self.state_manager.delete('nonexistent')
        self.assertFalse(result)
    
    def test_clear(self):
        """测试清空所有状态"""
        self.state_manager.update('dataset1', status='ready')
        self.state_manager.update('dataset2', status='pending')
        
        self.state_manager.clear()
        
        self.assertEqual(self.state_manager.get_all(), {})
    
    def test_get_last_updated(self):
        """测试获取最后更新时间"""
        self.state_manager.update('test-dataset', last_updated='2024-01-15T10:30:00')
        
        last_updated = self.state_manager.get_last_updated('test-dataset')
        self.assertEqual(last_updated, '2024-01-15T10:30:00')
        
        # 不存在的数据集
        last_updated = self.state_manager.get_last_updated('nonexistent')
        self.assertIsNone(last_updated)
    
    def test_set_status(self):
        """测试设置状态"""
        result = self.state_manager.set_status('test-dataset', 'packaging')
        
        self.assertEqual(result['status'], 'packaging')
        
        state = self.state_manager.get('test-dataset')
        self.assertEqual(state['status'], 'packaging')
    
    def test_is_packaged(self):
        """测试检查是否已打包"""
        # 未打包
        self.assertFalse(self.state_manager.is_packaged('test-dataset'))
        
        # 状态为 ready 但没有 last_packaged_at
        self.state_manager.set_status('test-dataset', 'ready')
        self.assertFalse(self.state_manager.is_packaged('test-dataset'))
        
        # 状态为 ready 且有 last_packaged_at
        self.state_manager.update('test-dataset', last_packaged_at='2024-01-15T10:30:00')
        self.assertTrue(self.state_manager.is_packaged('test-dataset'))
    
    def test_update_merges(self):
        """测试更新合并字段"""
        self.state_manager.update('test-dataset', field1='value1')
        self.state_manager.update('test-dataset', field2='value2')
        
        state = self.state_manager.get('test-dataset')
        self.assertEqual(state['field1'], 'value1')
        self.assertEqual(state['field2'], 'value2')


if __name__ == '__main__':
    unittest.main()
