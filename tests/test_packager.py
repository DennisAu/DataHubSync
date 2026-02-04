"""
TestPackager - 打包器单元测试
"""

import os
import time
import tempfile
import shutil
import zipfile
import unittest
from datetime import datetime
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from packager import Packager


class TestPackager(unittest.TestCase):
    """测试 Packager 类"""
    
    def setUp(self):
        """每个测试前创建临时目录"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.cache_dir = self.temp_dir / "cache"
        self.data_dir = self.temp_dir / "data"
        self.cache_dir.mkdir()
        self.data_dir.mkdir()
        
        # 创建打包器实例
        self.packager = Packager(
            cache_dir=str(self.cache_dir),
            keep_versions=3
        )
    
    def tearDown(self):
        """每个测试后清理临时目录"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _create_test_file(self, path: Path, content: str = "test data"):
        """辅助方法：创建测试文件"""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path
    
    def test_init_creates_cache_dir(self):
        """测试初始化时创建缓存目录"""
        new_cache_dir = self.temp_dir / "new_cache"
        self.assertFalse(new_cache_dir.exists())
        
        packager = Packager(cache_dir=str(new_cache_dir))
        
        self.assertTrue(new_cache_dir.exists())
        self.assertTrue(new_cache_dir.is_dir())
    
    def test_package_success(self):
        """测试正常打包"""
        dataset_name = "test_dataset"
        
        # 创建测试文件
        test_files = [
            self.data_dir / "file1.csv",
            self.data_dir / "file2.csv",
            self.data_dir / "subdir" / "file3.csv"
        ]
        for i, f in enumerate(test_files):
            self._create_test_file(f, f"content {i}")
        
        result = self.packager.package(dataset_name, str(self.data_dir))
        
        # 验证结果
        self.assertTrue(result['success'])
        self.assertIsNotNone(result['zip_path'])
        self.assertEqual(result['file_count'], 3)
        self.assertGreater(result['zip_size'], 0)
        self.assertIsNone(result['error'])
        
        # 验证 zip 文件存在
        zip_path = Path(result['zip_path'])
        self.assertTrue(zip_path.exists())
        
        # 验证 zip 内容 - 保留相对路径结构
        with zipfile.ZipFile(zip_path, 'r') as zf:
            namelist = zf.namelist()
            self.assertEqual(len(namelist), 3)
            # 根目录文件
            self.assertIn("file1.csv", namelist)
            self.assertIn("file2.csv", namelist)
            # 子目录文件保留相对路径
            self.assertIn("subdir/file3.csv", namelist)
    
    def test_package_uses_deflated_compression(self):
        """测试使用 ZIP_DEFLATED 压缩"""
        dataset_name = "test_dataset"
        
        # 创建一个内容较多的文件
        large_content = "x" * 10000
        self._create_test_file(self.data_dir / "large.txt", large_content)
        
        result = self.packager.package(dataset_name, str(self.data_dir))
        
        self.assertTrue(result['success'])
        
        # 验证压缩
        zip_path = result['zip_path']
        with zipfile.ZipFile(zip_path, 'r') as zf:
            for info in zf.infolist():
                self.assertEqual(info.compress_type, zipfile.ZIP_DEFLATED)
    
    def test_package_generates_correct_filename_format(self):
        """测试生成的文件名格式正确"""
        dataset_name = "my_dataset"
        
        self._create_test_file(self.data_dir / "test.csv")
        
        result = self.packager.package(dataset_name, str(self.data_dir))
        
        zip_path = Path(result['zip_path'])
        filename = zip_path.name
        
        # 格式: {dataset_name}_{YYYYMMDD_HHMMSS}.zip
        self.assertTrue(filename.startswith(f"{dataset_name}_"))
        self.assertTrue(filename.endswith(".zip"))
        
        # 验证时间戳部分
        timestamp_part = filename[len(dataset_name)+1:-4]
        self.assertEqual(len(timestamp_part), 15)  # YYYYMMDD_HHMMSS
        self.assertEqual(timestamp_part[8], '_')
    
    def test_package_empty_directory(self):
        """测试打包空目录"""
        dataset_name = "empty_dataset"
        
        # data_dir 已经存在且为空
        result = self.packager.package(dataset_name, str(self.data_dir))
        
        self.assertTrue(result['success'])
        self.assertEqual(result['file_count'], 0)
        
        # 验证 zip 文件存在但为空
        zip_path = Path(result['zip_path'])
        self.assertTrue(zip_path.exists())
        
        with zipfile.ZipFile(zip_path, 'r') as zf:
            self.assertEqual(len(zf.namelist()), 0)
    
    def test_package_nonexistent_directory(self):
        """测试打包不存在的目录"""
        dataset_name = "test_dataset"
        nonexistent_dir = str(self.data_dir / "does_not_exist")
        
        result = self.packager.package(dataset_name, nonexistent_dir)
        
        self.assertFalse(result['success'])
        self.assertIsNone(result['zip_path'])
        self.assertEqual(result['file_count'], 0)
        self.assertEqual(result['zip_size'], 0)
        self.assertIn("does not exist", result['error'].lower())
    
    def test_package_file_not_directory(self):
        """测试打包路径是文件而不是目录"""
        dataset_name = "test_dataset"
        
        # 创建一个文件而不是目录
        file_path = self.temp_dir / "not_a_dir.txt"
        file_path.write_text("I am a file")
        
        result = self.packager.package(dataset_name, str(file_path))
        
        self.assertFalse(result['success'])
        self.assertIn("not a directory", result['error'].lower())
    
    def test_cleanup_old_versions(self):
        """测试清理旧版本"""
        dataset_name = "test_dataset"
        
        # 创建 5 个版本（每个使用不同的数据目录以避免文件名冲突）
        for i in range(5):
            # 为每个版本创建独立的子目录
            version_dir = self.temp_dir / f"data_v{i}"
            version_dir.mkdir()
            (version_dir / f"file{i}.csv").write_text(f"content {i}")
            result = self.packager.package(dataset_name, str(version_dir))
            self.assertTrue(result['success'])
            time.sleep(1.1)  # 确保时间戳不同（秒级时间戳变化）
        
        # 验证缓存目录中只有 3 个文件（keep_versions=3）
        zip_files = list(self.cache_dir.glob(f"{dataset_name}_*.zip"))
        self.assertEqual(len(zip_files), 3)  # 只保留 3 个
        
        # 验证最新版本存在
        versions = self.packager.list_versions(dataset_name)
        self.assertEqual(len(versions), 3)
    
    def test_get_latest_package(self):
        """测试获取最新包"""
        dataset_name = "test_dataset"
        
        # 初始时应该返回 None
        latest = self.packager.get_latest_package(dataset_name)
        self.assertIsNone(latest)
        
        # 创建第一个版本
        data_dir1 = self.temp_dir / "data_v1"
        data_dir1.mkdir()
        (data_dir1 / "v1.csv").write_text("v1")
        result1 = self.packager.package(dataset_name, str(data_dir1))
        time.sleep(1.1)  # 确保时间戳不同（秒级）
        
        # 创建第二个版本
        data_dir2 = self.temp_dir / "data_v2"
        data_dir2.mkdir()
        (data_dir2 / "v2.csv").write_text("v2")
        result2 = self.packager.package(dataset_name, str(data_dir2))
        
        # 获取最新版本
        latest = self.packager.get_latest_package(dataset_name)
        
        self.assertEqual(latest, result2['zip_path'])
        self.assertNotEqual(latest, result1['zip_path'])
    
    def test_list_versions(self):
        """测试列出所有版本"""
        dataset_name = "test_dataset"
        
        # 创建 3 个版本（使用不同目录确保唯一时间戳）
        for i in range(3):
            version_dir = self.temp_dir / f"data_v{i}"
            version_dir.mkdir()
            (version_dir / f"file{i}.csv").write_text(f"content {i}")
            self.packager.package(dataset_name, str(version_dir))
            time.sleep(1.1)  # 确保时间戳不同（秒级）
        
        versions = self.packager.list_versions(dataset_name)
        
        self.assertEqual(len(versions), 3)
        
        # 验证每个版本的字段
        for v in versions:
            self.assertIn('path', v)
            self.assertIn('filename', v)
            self.assertIn('size', v)
            self.assertIn('created', v)
            self.assertTrue(v['size'] > 0)
        
        # 验证按时间倒序排列
        for i in range(len(versions) - 1):
            self.assertGreater(
                versions[i]['created'],
                versions[i+1]['created']
            )
    
    def test_delete_package(self):
        """测试删除包"""
        dataset_name = "test_dataset"
        
        self._create_test_file(self.data_dir / "test.csv")
        result = self.packager.package(dataset_name, str(self.data_dir))
        zip_path = result['zip_path']
        
        # 验证文件存在
        self.assertTrue(Path(zip_path).exists())
        
        # 删除
        success = self.packager.delete_package(zip_path)
        self.assertTrue(success)
        
        # 验证文件已删除
        self.assertFalse(Path(zip_path).exists())
    
    def test_delete_package_nonexistent(self):
        """测试删除不存在的包"""
        nonexistent_path = str(self.cache_dir / "nonexistent.zip")
        
        success = self.packager.delete_package(nonexistent_path)
        self.assertFalse(success)
    
    def test_multiple_datasets(self):
        """测试多个数据集独立管理"""
        # 创建数据集 A
        data_dir_a = self.temp_dir / "data_a"
        data_dir_a.mkdir()
        (data_dir_a / "a.csv").write_text("A")
        
        # 创建数据集 B
        data_dir_b = self.temp_dir / "data_b"
        data_dir_b.mkdir()
        (data_dir_b / "b.csv").write_text("B")
        
        # 打包两个数据集
        result_a = self.packager.package("dataset_a", str(data_dir_a))
        result_b = self.packager.package("dataset_b", str(data_dir_b))
        
        self.assertTrue(result_a['success'])
        self.assertTrue(result_b['success'])
        
        # 验证各自独立
        latest_a = self.packager.get_latest_package("dataset_a")
        latest_b = self.packager.get_latest_package("dataset_b")
        
        self.assertEqual(latest_a, result_a['zip_path'])
        self.assertEqual(latest_b, result_b['zip_path'])
        self.assertNotEqual(latest_a, latest_b)
        
        # 验证版本列表
        versions_a = self.packager.list_versions("dataset_a")
        versions_b = self.packager.list_versions("dataset_b")
        
        self.assertEqual(len(versions_a), 1)
        self.assertEqual(len(versions_b), 1)
    
    def test_package_preserves_relative_path(self):
        """测试 zip 中保留相对路径结构，避免同名文件覆盖"""
        dataset_name = "test_dataset"
        
        # 创建嵌套目录结构
        subdir1 = self.data_dir / "level1" / "level2"
        subdir1.mkdir(parents=True)
        
        self._create_test_file(self.data_dir / "root.txt", "root")
        self._create_test_file(self.data_dir / "level1" / "level1.txt", "level1")
        self._create_test_file(subdir1 / "level2.txt", "level2")
        
        result = self.packager.package(dataset_name, str(self.data_dir))
        
        # 验证 zip 内容 - 保留相对路径结构
        with zipfile.ZipFile(result['zip_path'], 'r') as zf:
            namelist = zf.namelist()
            self.assertEqual(len(namelist), 3)
            
            # 根目录文件
            self.assertIn("root.txt", namelist)
            # 子目录文件保留相对路径
            self.assertIn("level1/level1.txt", namelist)
            self.assertIn("level1/level2/level2.txt", namelist)


class TestPackagerIntegration(unittest.TestCase):
    """集成测试"""
    
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.cache_dir = self.temp_dir / "cache"
        self.data_dir = self.temp_dir / "data"
        self.cache_dir.mkdir()
        self.data_dir.mkdir()
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_full_workflow(self):
        """测试完整工作流"""
        packager = Packager(cache_dir=str(self.cache_dir), keep_versions=2)
        dataset_name = "stock_data"
        
        # 第1次打包
        data1 = self.temp_dir / "data1"
        data1.mkdir()
        (data1 / "day1.csv").write_text("day1 data")
        result1 = packager.package(dataset_name, str(data1))
        self.assertTrue(result1['success'])
        time.sleep(1.1)  # 确保时间戳不同（秒级）
        
        # 第2次打包
        data2 = self.temp_dir / "data2"
        data2.mkdir()
        (data2 / "day2.csv").write_text("day2 data")
        result2 = packager.package(dataset_name, str(data2))
        self.assertTrue(result2['success'])
        time.sleep(1.1)
        
        # 验证有两个版本
        versions = packager.list_versions(dataset_name)
        self.assertEqual(len(versions), 2)
        
        # 第3次打包（应该触发清理）
        data3 = self.temp_dir / "data3"
        data3.mkdir()
        (data3 / "day3.csv").write_text("day3 data")
        result3 = packager.package(dataset_name, str(data3))
        self.assertTrue(result3['success'])
        
        # 验证仍然只有两个版本
        versions = packager.list_versions(dataset_name)
        self.assertEqual(len(versions), 2)
        
        # 验证最新的是 result3
        latest = packager.get_latest_package(dataset_name)
        self.assertEqual(latest, result3['zip_path'])
        
        # 验证最早的 result1 已被删除
        self.assertFalse(Path(result1['zip_path']).exists())


def run_tests():
    """运行所有测试"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestPackager))
    suite.addTests(loader.loadTestsFromTestCase(TestPackagerIntegration))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
