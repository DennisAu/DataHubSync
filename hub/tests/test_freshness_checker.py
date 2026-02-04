"""
TestFreshnessChecker - 新鲜度检测器单元测试
"""

import os
import time
import tempfile
import shutil
import unittest
from datetime import datetime, timedelta
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from freshness_checker import FreshnessChecker, FreshnessResult


class TestFreshnessResult(unittest.TestCase):
    """测试 FreshnessResult 数据类"""
    
    def test_is_fresh_with_default_threshold(self):
        """测试默认阈值(0.85)的新鲜度判断"""
        # 新鲜度 90% > 85%，应该返回True
        result = FreshnessResult(
            total_count=100,
            fresh_count=90,
            fresh_ratio=0.90,
            last_updated=datetime.now().isoformat()
        )
        self.assertTrue(result.is_fresh())
        
        # 新鲜度 80% < 85%，应该返回False
        result = FreshnessResult(
            total_count=100,
            fresh_count=80,
            fresh_ratio=0.80,
            last_updated=datetime.now().isoformat()
        )
        self.assertFalse(result.is_fresh())
        
        # 新鲜度正好85%，应该返回True（>=）
        result = FreshnessResult(
            total_count=100,
            fresh_count=85,
            fresh_ratio=0.85,
            last_updated=datetime.now().isoformat()
        )
        self.assertTrue(result.is_fresh())
    
    def test_is_fresh_with_custom_threshold(self):
        """测试自定义阈值的新鲜度判断"""
        result = FreshnessResult(
            total_count=100,
            fresh_count=75,
            fresh_ratio=0.75,
            last_updated=datetime.now().isoformat()
        )
        # 75% < 80%，应该返回False
        self.assertFalse(result.is_fresh(threshold=0.80))
        # 75% > 70%，应该返回True
        self.assertTrue(result.is_fresh(threshold=0.70))
    
    def test_to_dict(self):
        """测试转换为字典"""
        result = FreshnessResult(
            total_count=100,
            fresh_count=85,
            fresh_ratio=0.85,
            last_updated="2024-01-15T10:30:00"
        )
        data = result.to_dict()
        
        self.assertEqual(data['total_count'], 100)
        self.assertEqual(data['fresh_count'], 85)
        self.assertEqual(data['fresh_ratio'], 0.85)
        self.assertEqual(data['last_updated'], "2024-01-15T10:30:00")
        self.assertTrue(data['is_fresh'])


class TestFreshnessChecker(unittest.TestCase):
    """测试 FreshnessChecker 类"""
    
    def setUp(self):
        """每个测试前创建临时目录"""
        self.temp_dir = tempfile.mkdtemp()
        self.data_root = Path(self.temp_dir) / "data"
        self.data_root.mkdir()
        
        # 创建测试数据集目录
        self.dataset1_path = self.data_root / "stock-trading-data-pro"
        self.dataset2_path = self.data_root / "stock-fin-data-xbx"
        self.dataset1_path.mkdir()
        self.dataset2_path.mkdir()
        
        # 数据集配置
        self.datasets_config = [
            {'name': 'stock-trading-data-pro', 'path': 'stock-trading-data-pro', 'freshness_threshold': 0.85},
            {'name': 'stock-fin-data-xbx', 'path': 'stock-fin-data-xbx', 'freshness_threshold': 0.85}
        ]
        
        # 创建检测器实例
        self.checker = FreshnessChecker(
            data_root=str(self.data_root),
            datasets_config=self.datasets_config
        )
    
    def tearDown(self):
        """每个测试后清理临时目录"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _create_test_file(self, path: Path, content: str = "test data"):
        """辅助方法：创建测试文件"""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path
    
    def _set_file_mtime(self, path: Path, days_ago: float):
        """辅助方法：设置文件的修改时间（几天前）"""
        mtime = time.time() - (days_ago * 86400)
        os.utime(path, (mtime, mtime))
        return mtime
    
    def test_check_with_no_files(self):
        """测试无文件时的检查"""
        result = self.checker.check("2024-01-15")
        
        self.assertEqual(result.total_count, 0)
        self.assertEqual(result.fresh_count, 0)
        self.assertEqual(result.fresh_ratio, 0.0)
        self.assertFalse(result.is_fresh())
    
    def test_check_with_fresh_files(self):
        """测试所有文件都新鲜的情况"""
        trade_date = "2024-01-15"
        
        # 创建10个新鲜文件（修改时间在24小时内）
        for i in range(10):
            file_path = self.dataset1_path / f"{trade_date}_data_{i}.csv"
            self._create_test_file(file_path)
            # 文件默认创建时间是当前时间，所以是新鲜的
        
        result = self.checker.check(trade_date)
        
        self.assertEqual(result.total_count, 10)
        self.assertEqual(result.fresh_count, 10)
        self.assertEqual(result.fresh_ratio, 1.0)
        self.assertTrue(result.is_fresh())
    
    def test_check_with_stale_files(self):
        """测试有陈旧文件的情况"""
        trade_date = "2024-01-15"
        
        # 创建10个文件
        for i in range(10):
            file_path = self.dataset1_path / f"{trade_date}_data_{i}.csv"
            self._create_test_file(file_path)
            
            # 前5个设置为2天前（不新鲜）
            if i < 5:
                self._set_file_mtime(file_path, days_ago=2)
            # 后5个保持当前时间（新鲜）
        
        result = self.checker.check(trade_date)
        
        self.assertEqual(result.total_count, 10)
        self.assertEqual(result.fresh_count, 5)
        self.assertEqual(result.fresh_ratio, 0.5)
        self.assertFalse(result.is_fresh())
    
    def test_check_with_threshold_85_percent(self):
        """测试85%阈值边界情况"""
        trade_date = "2024-01-15"
        
        # 创建100个文件，85个新鲜
        for i in range(100):
            file_path = self.dataset1_path / f"{trade_date}_data_{i}.csv"
            self._create_test_file(file_path)
            
            if i >= 85:  # 15个不新鲜
                self._set_file_mtime(file_path, days_ago=2)
        
        result = self.checker.check(trade_date)
        
        self.assertEqual(result.total_count, 100)
        self.assertEqual(result.fresh_count, 85)
        self.assertEqual(result.fresh_ratio, 0.85)
        self.assertTrue(result.is_fresh())  # 正好85%也算新鲜
    
    def test_check_85th_percentile_mtime(self):
        """测试85%分位数mtime计算"""
        trade_date = "2024-01-15"
        mtimes = []
        base_time = time.time()
        
        # 创建100个文件，分别设置不同的mtime
        for i in range(100):
            file_path = self.dataset1_path / f"{trade_date}_data_{i}.csv"
            self._create_test_file(file_path)
            # 设置mtime为i*100秒前，确保有明显差异
            mtime = base_time - (i * 100)
            os.utime(file_path, (mtime, mtime))
            mtimes.append(mtime)
        
        result = self.checker.check(trade_date)
        
        # 验证last_updated是有效的ISO格式时间
        actual_dt = datetime.fromisoformat(result.last_updated)
        self.assertIsNotNone(actual_dt)
        
        # 验证85%分位数的逻辑：取排序后第85个元素（索引84）
        # 由于我们设置的是递减的mtime（0, -100, -200...），
        # 85%分位数应该接近最早创建的那些文件的mtime
        expected_85th_mtime = sorted(mtimes)[84]
        actual_timestamp = actual_dt.timestamp()
        
        # 验证时间戳是合理的（在文件创建时间范围内）
        min_mtime = min(mtimes)
        max_mtime = max(mtimes)
        self.assertGreaterEqual(actual_timestamp, min_mtime - 1)
        self.assertLessEqual(actual_timestamp, max_mtime + 1)
        
        # 验证85%分位数位置正确（应该比约15%的文件mtime更旧或相等）
        files_older_or_equal = sum(1 for m in mtimes if m <= actual_timestamp + 1)
        self.assertGreaterEqual(files_older_or_equal, 84)  # 至少84个文件<=分位点
        self.assertLessEqual(files_older_or_equal, 90)     # 但不超过90个
    
    def test_check_date_format_variations(self):
        """测试不同日期格式的处理"""
        trade_date_dash = "2024-01-15"
        trade_date_nodash = "20240115"
        
        # 使用带横杠的日期格式创建文件
        file_path = self.dataset1_path / f"{trade_date_dash}_data.csv"
        self._create_test_file(file_path)
        
        # 用两种格式检查应该都能匹配
        result1 = self.checker.check(trade_date_dash)
        result2 = self.checker.check(trade_date_nodash)
        
        # 至少一个能匹配到文件
        self.assertTrue(result1.total_count > 0 or result2.total_count > 0)
    
    def test_check_across_multiple_datasets(self):
        """测试跨多个数据集的检查"""
        trade_date = "2024-01-15"
        
        # 在第一个数据集创建5个文件
        for i in range(5):
            file_path = self.dataset1_path / f"{trade_date}_data_{i}.csv"
            self._create_test_file(file_path)
        
        # 在第二个数据集创建3个文件
        for i in range(3):
            file_path = self.dataset2_path / f"{trade_date}_fin_{i}.csv"
            self._create_test_file(file_path)
        
        result = self.checker.check(trade_date)
        
        self.assertEqual(result.total_count, 8)
        self.assertEqual(result.fresh_count, 8)
    
    def test_check_stable_with_stable_data(self):
        """测试防抖检查 - 数据稳定的情况"""
        trade_date = "2024-01-15"
        
        # 创建一些文件
        for i in range(10):
            file_path = self.dataset1_path / f"{trade_date}_data_{i}.csv"
            self._create_test_file(file_path)
        
        # 使用很短的防抖时间进行测试
        result = self.checker.check_stable(trade_date, debounce_seconds=1)
        
        # 数据应该稳定，返回结果
        self.assertIsNotNone(result)
        self.assertEqual(result.total_count, 10)
    
    def test_check_stable_with_changing_data(self):
        """测试防抖检查 - 数据变化的情况"""
        trade_date = "2024-01-15"
        
        # 先创建少量文件
        for i in range(5):
            file_path = self.dataset1_path / f"{trade_date}_data_{i}.csv"
            self._create_test_file(file_path)
        
        class MockChecker(FreshnessChecker):
            """模拟数据变化的检测器"""
            check_count = 0
            
            def check(self, trade_date):
                self.check_count += 1
                # 第一次检查只有5个文件
                if self.check_count == 1:
                    return FreshnessResult(
                        total_count=5,
                        fresh_count=5,
                        fresh_ratio=0.5,  # 50%
                        last_updated=datetime.now().isoformat()
                    )
                # 第二次检查有10个文件
                else:
                    return FreshnessResult(
                        total_count=10,
                        fresh_count=10,
                        fresh_ratio=1.0,  # 100%
                        last_updated=datetime.now().isoformat()
                    )
        
        mock_checker = MockChecker(
            data_root=str(self.data_root),
            datasets_config=self.datasets_config
        )
        
        result = mock_checker.check_stable(trade_date, debounce_seconds=0.5)
        
        # 数据变化超过1%，应该返回None
        self.assertIsNone(result)
    
    def test_is_fresh_quick_check(self):
        """测试快速新鲜度检查"""
        trade_date = "2024-01-15"
        
        # 创建85个新鲜文件（共100个，前85个新鲜）
        for i in range(100):
            file_path = self.dataset1_path / f"{trade_date}_data_{i}.csv"
            self._create_test_file(file_path)
            # 后15个设置为陈旧（i >= 85）
            if i >= 85:
                self._set_file_mtime(file_path, days_ago=2)
        
        # 快速检查: 85/100 = 85%，刚好达到阈值
        is_fresh = self.checker.is_fresh(trade_date, threshold=0.85)
        self.assertTrue(is_fresh)
        
        # 添加更多陈旧文件，使比例低于85%
        for i in range(20):
            file_path = self.dataset1_path / f"{trade_date}_extra_{i}.csv"
            self._create_test_file(file_path)
            self._set_file_mtime(file_path, days_ago=2)
        
        # 85/120 = 70.8% < 85%
        is_fresh = self.checker.is_fresh(trade_date, threshold=0.85)
        self.assertFalse(is_fresh)
    
    def test_get_stats(self):
        """测试获取详细统计信息"""
        trade_date = "2024-01-15"
        
        # 创建3个文件，不同mtime
        for i in range(3):
            file_path = self.dataset1_path / f"{trade_date}_data_{i}.csv"
            self._create_test_file(file_path, content=f"data {i}")
            # 设置不同的mtime
            self._set_file_mtime(file_path, days_ago=i * 0.5)
        
        stats = self.checker.get_stats(trade_date)
        
        self.assertEqual(stats['trade_date'], trade_date)
        self.assertIn('summary', stats)
        self.assertIn('datasets', stats)
        self.assertIn('files', stats)
        self.assertEqual(len(stats['files']), 3)
        self.assertEqual(len(stats['datasets']), 2)
    
    def test_empty_datasets_config(self):
        """测试空数据集配置"""
        empty_checker = FreshnessChecker(
            data_root=str(self.data_root),
            datasets_config=[]
        )
        
        result = empty_checker.check("2024-01-15")
        
        self.assertEqual(result.total_count, 0)
        self.assertEqual(result.fresh_ratio, 0.0)
    
    def test_nonexistent_dataset_path(self):
        """测试不存在的数据集路径"""
        checker_with_bad_path = FreshnessChecker(
            data_root=str(self.data_root),
            datasets_config=[
                {'name': 'nonexistent', 'path': 'does-not-exist', 'freshness_threshold': 0.85}
            ]
        )
        
        result = checker_with_bad_path.check("2024-01-15")
        
        self.assertEqual(result.total_count, 0)
        self.assertEqual(result.fresh_ratio, 0.0)


class TestFreshnessCheckerIntegration(unittest.TestCase):
    """集成测试 - 测试真实场景"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.data_root = Path(self.temp_dir) / "data"
        self.data_root.mkdir()
        
        # 创建多层级目录结构
        self.trading_path = self.data_root / "stock-trading-data-pro" / "2024" / "01"
        self.fin_path = self.data_root / "stock-fin-data-xbx" / "2024" / "01"
        self.trading_path.mkdir(parents=True)
        self.fin_path.mkdir(parents=True)
        
        self.datasets_config = [
            {'name': 'stock-trading-data-pro', 'path': 'stock-trading-data-pro', 'freshness_threshold': 0.85},
            {'name': 'stock-fin-data-xbx', 'path': 'stock-fin-data-xbx', 'freshness_threshold': 0.85}
        ]
        
        self.checker = FreshnessChecker(
            data_root=str(self.data_root),
            datasets_config=self.datasets_config
        )
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_realistic_scenario(self):
        """测试真实场景：模拟实际数据目录结构"""
        trade_date = "2024-01-15"
        
        # 创建交易数据文件
        trading_files = [
            self.trading_path / f"{trade_date}_sh.csv",
            self.trading_path / f"{trade_date}_sz.csv",
            self.trading_path / f"{trade_date}_bj.csv",
        ]
        
        # 创建财务数据文件
        fin_files = [
            self.fin_path / f"{trade_date}_balance.csv",
            self.fin_path / f"{trade_date}_income.csv",
        ]
        
        all_files = trading_files + fin_files
        
        # 所有文件新鲜
        for f in all_files:
            f.write_text("test data")
        
        result = self.checker.check(trade_date)
        
        self.assertEqual(result.total_count, 5)
        self.assertEqual(result.fresh_count, 5)
        self.assertTrue(result.is_fresh())
        
        # 模拟部分文件陈旧（2天前）
        for f in trading_files[:2]:
            mtime = time.time() - (2 * 86400)
            os.utime(f, (mtime, mtime))
        
        result = self.checker.check(trade_date)
        
        self.assertEqual(result.total_count, 5)
        self.assertEqual(result.fresh_count, 3)  # 只有财务数据 + 1个交易数据新鲜
        self.assertEqual(result.fresh_ratio, 0.6)
        self.assertFalse(result.is_fresh())


def run_tests():
    """运行所有测试"""
    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # 添加测试类
    suite.addTests(loader.loadTestsFromTestCase(TestFreshnessResult))
    suite.addTests(loader.loadTestsFromTestCase(TestFreshnessChecker))
    suite.addTests(loader.loadTestsFromTestCase(TestFreshnessCheckerIntegration))
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
