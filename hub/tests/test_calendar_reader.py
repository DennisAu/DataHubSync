"""CalendarReader 测试模块"""

import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta

# 添加 src 目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from calendar_reader import CalendarReader


class TestCalendarReader(unittest.TestCase):
    """CalendarReader 测试类"""
    
    def setUp(self):
        """创建临时测试CSV文件"""
        self.test_csv_content = """交易日期,备注
2024-01-02,新年首个交易日
2024-01-03,交易日
2024-01-04,交易日
2024-01-05,交易日
2024-01-08,周一交易日
2024-01-09,交易日
2024-01-10,交易日
2024-01-11,交易日
2024-01-12,周五交易日
2024-01-15,周一交易日
"""
        # 创建临时文件
        self.temp_file = tempfile.NamedTemporaryFile(
            mode='w', 
            suffix='.csv', 
            delete=False,
            encoding='utf-8'
        )
        self.temp_file.write(self.test_csv_content)
        self.temp_file.close()
        
        # 预期交易日列表
        self.expected_dates = [
            '2024-01-02', '2024-01-03', '2024-01-04', '2024-01-05',
            '2024-01-08', '2024-01-09', '2024-01-10', '2024-01-11',
            '2024-01-12', '2024-01-15'
        ]
    
    def tearDown(self):
        """清理临时文件"""
        if os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)
    
    def test_init(self):
        """测试初始化"""
        reader = CalendarReader(self.temp_file.name)
        self.assertEqual(reader.csv_path, self.temp_file.name)
        self.assertIsNotNone(reader._trade_dates)
    
    def test_get_trade_dates(self):
        """测试获取所有交易日列表"""
        reader = CalendarReader(self.temp_file.name)
        dates = reader.get_trade_dates()
        
        # 验证返回正确的交易日列表
        self.assertEqual(dates, self.expected_dates)
        self.assertEqual(len(dates), 10)
        
        # 验证返回的是副本，修改不影响原数据
        dates.append('2099-12-31')
        self.assertEqual(len(reader.get_trade_dates()), 10)
    
    def test_get_last_trade_date_basic(self):
        """测试获取上一个交易日 - 基本功能"""
        reader = CalendarReader(self.temp_file.name)
        
        # 2024-01-10 的上一个交易日应该是 2024-01-09
        last_date = reader.get_last_trade_date('2024-01-10')
        self.assertEqual(last_date, '2024-01-09')
    
    def test_get_last_trade_date_weekend(self):
        """测试获取上一个交易日 - 跨越周末"""
        reader = CalendarReader(self.temp_file.name)
        
        # 2024-01-15(周一) 的上一个交易日应该是 2024-01-12(周五)
        last_date = reader.get_last_trade_date('2024-01-15')
        self.assertEqual(last_date, '2024-01-12')
    
    def test_get_last_trade_date_holiday(self):
        """测试获取上一个交易日 - 假期后"""
        reader = CalendarReader(self.temp_file.name)
        
        # 2024-01-06(周六，非交易日) 的上一个交易日应该是 2024-01-05
        last_date = reader.get_last_trade_date('2024-01-06')
        self.assertEqual(last_date, '2024-01-05')
    
    def test_get_last_trade_date_first_day(self):
        """测试获取上一个交易日 - 第一个交易日之前"""
        reader = CalendarReader(self.temp_file.name)
        
        # 2024-01-01(在第一个交易日之前) 应该返回第一个交易日
        last_date = reader.get_last_trade_date('2024-01-01')
        self.assertEqual(last_date, '2024-01-02')
    
    def test_get_last_trade_date_none(self):
        """测试获取上一个交易日 - 使用当前日期"""
        reader = CalendarReader(self.temp_file.name)
        
        # 不传入参数，使用当前日期
        last_date = reader.get_last_trade_date()
        # 由于测试数据都是过去的日期，应该返回最后一个交易日
        self.assertEqual(last_date, '2024-01-15')
    
    def test_get_last_trade_date_same_day(self):
        """测试获取上一个交易日 - 当天是交易日"""
        reader = CalendarReader(self.temp_file.name)
        
        # 2024-01-10 本身是交易日，应该返回前一个交易日 2024-01-09
        last_date = reader.get_last_trade_date('2024-01-10')
        self.assertEqual(last_date, '2024-01-09')
    
    def test_is_trade_date(self):
        """测试检查是否为交易日"""
        reader = CalendarReader(self.temp_file.name)
        
        # 是交易日
        self.assertTrue(reader.is_trade_date('2024-01-02'))
        self.assertTrue(reader.is_trade_date('2024-01-15'))
        
        # 不是交易日（周末）
        self.assertFalse(reader.is_trade_date('2024-01-06'))  # 周六
        self.assertFalse(reader.is_trade_date('2024-01-07'))  # 周日
        
        # 不是交易日（不在列表中）
        self.assertFalse(reader.is_trade_date('2024-01-01'))
    
    def test_invalid_date_format(self):
        """测试无效日期格式"""
        reader = CalendarReader(self.temp_file.name)
        
        with self.assertRaises(ValueError):
            reader.get_last_trade_date('2024/01/10')
        
        with self.assertRaises(ValueError):
            reader.get_last_trade_date('01-10-2024')
        
        with self.assertRaises(ValueError):
            reader.is_trade_date('invalid-date')
    
    def test_file_not_found(self):
        """测试文件不存在"""
        with self.assertRaises(FileNotFoundError):
            CalendarReader('/nonexistent/path/file.csv')
    
    def test_missing_column(self):
        """测试CSV缺少交易日期列"""
        # 创建错误的CSV文件
        bad_csv = """日期,备注
2024-01-02,test
"""
        temp_bad = tempfile.NamedTemporaryFile(
            mode='w', 
            suffix='.csv', 
            delete=False,
            encoding='utf-8'
        )
        temp_bad.write(bad_csv)
        temp_bad.close()
        
        try:
            with self.assertRaises(ValueError) as context:
                CalendarReader(temp_bad.name)
            self.assertIn('交易日期', str(context.exception))
        finally:
            os.unlink(temp_bad.name)
    
    def test_reload(self):
        """测试重新加载功能"""
        reader = CalendarReader(self.temp_file.name)
        
        # 初始状态
        self.assertEqual(len(reader.get_trade_dates()), 10)
        
        # 修改文件内容
        new_content = """交易日期,备注
2024-01-02,test
2024-01-03,test
"""
        with open(self.temp_file.name, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        # 重新加载
        reader.reload()
        
        # 验证数据已更新
        self.assertEqual(len(reader.get_trade_dates()), 2)
        self.assertEqual(reader.get_trade_dates(), ['2024-01-02', '2024-01-03'])


class TestCalendarReaderEdgeCases(unittest.TestCase):
    """边界情况测试"""
    
    def test_empty_csv(self):
        """测试空CSV文件"""
        temp = tempfile.NamedTemporaryFile(
            mode='w', 
            suffix='.csv', 
            delete=False,
            encoding='utf-8'
        )
        temp.write('交易日期,备注\n')
        temp.close()
        
        try:
            reader = CalendarReader(temp.name)
            self.assertEqual(reader.get_trade_dates(), [])
            self.assertIsNone(reader.get_last_trade_date('2024-01-01'))
        finally:
            os.unlink(temp.name)
    
    def test_single_date(self):
        """测试只有一个交易日的CSV"""
        temp = tempfile.NamedTemporaryFile(
            mode='w', 
            suffix='.csv', 
            delete=False,
            encoding='utf-8'
        )
        temp.write('交易日期,备注\n2024-01-02,only\n')
        temp.close()
        
        try:
            reader = CalendarReader(temp.name)
            self.assertEqual(reader.get_trade_dates(), ['2024-01-02'])
            self.assertEqual(reader.get_last_trade_date('2024-01-03'), '2024-01-02')
        finally:
            os.unlink(temp.name)
    
    def test_unordered_csv(self):
        """测试日期无序的CSV"""
        temp = tempfile.NamedTemporaryFile(
            mode='w', 
            suffix='.csv', 
            delete=False,
            encoding='utf-8'
        )
        temp.write('交易日期\n2024-01-05\n2024-01-02\n2024-01-03\n')
        temp.close()
        
        try:
            reader = CalendarReader(temp.name)
            # 应该按升序返回
            self.assertEqual(
                reader.get_trade_dates(), 
                ['2024-01-02', '2024-01-03', '2024-01-05']
            )
        finally:
            os.unlink(temp.name)


if __name__ == '__main__':
    unittest.main()
